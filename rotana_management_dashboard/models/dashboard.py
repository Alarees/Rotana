# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MAX_DAILY_DAYS = 92      # أكثر من ذلك نجمّع شهرياً
MAX_RANGE_DAYS = 3660
TOP_N = 7
DASHBOARD_GROUP = 'rotana_management_dashboard.group_rotana_dashboard_manager'


class RotanaManagementDashboard(models.AbstractModel):
    """مصدر بيانات لوحة الإدارة.

    - المبيعات = أوامر البيع المؤكدة (sale.order بالحالة sale).
    - المبالغ = amount_total (شاملة الضريبة) محوّلة إلى عملة الشركة الحالية للمستخدم.
    - المديونيات = رصيد حسابات الذمم المدينة (asset_receivable) المرحّلة حتى نهاية الفترة (من القيود، لا من الفواتير).
    - السداد = صافي دائن حسابات الذمم من القيود العامة (move_type = entry: دفعات/كشوف بنك/تسويات)
      خلال الفترة، دون اشتراط مطابقة الفواتير.
    - العرض الموحّد: الشركة الأم تُظهر مبيعاتها + مبيعات كل فروعها (دون تكرار في الإجماليات).
    - القراءة بـ sudo بعد التحقق من الصلاحية وتقييد الشركات بشركات المستخدم المسموحة.
    """
    _name = 'rotana.management.dashboard'
    _description = 'Rotana Management Dashboard Data'

    # ------------------------------------------------------------------ helpers
    def _check_dashboard_access(self):
        user = self.env.user
        if not (user.has_group('base.group_system') or user.has_group(DASHBOARD_GROUP)):
            raise AccessError(_("ليست لديك صلاحية الوصول إلى لوحة الإدارة."))

    def _allowed_companies(self, company_ids=None):
        companies = self.env.user.company_ids
        if company_ids:
            wanted = set(company_ids)
            companies = companies.filtered(lambda c: c.id in wanted)
        return companies

    def _parse_dates(self, date_from, date_to):
        d_from = fields.Date.to_date(date_from) or fields.Date.context_today(self)
        d_to = fields.Date.to_date(date_to) or d_from
        if d_to < d_from:
            d_from, d_to = d_to, d_from
        if (d_to - d_from).days > MAX_RANGE_DAYS:
            raise UserError(_("الفترة المحددة طويلة جداً."))
        tz = pytz.timezone(self.env.user.tz or 'UTC')

        def to_utc(day):
            return tz.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)

        return d_from, d_to, to_utc(d_from), to_utc(d_to + timedelta(days=1))

    @staticmethod
    def _make_buckets(d_from, d_to, granularity):
        buckets = []
        if granularity == 'day':
            day = d_from
            while day <= d_to:
                buckets.append(day)
                day += timedelta(days=1)
        else:
            day = d_from.replace(day=1)
            while day <= d_to:
                buckets.append(day)
                day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        return buckets

    def _rate_getter(self, target_currency, at_date):
        cache = {}
        Currency = self.env['res.currency']

        def get(from_currency, company):
            key = (from_currency.id, company.id)
            if key not in cache:
                cache[key] = Currency._get_conversion_rate(
                    from_currency, target_currency, company, at_date)
            return cache[key]

        return get

    @staticmethod
    def _children_map(companies):
        """خريطة {id الشركة الأم: [ids الفروع المباشرة]} ضمن الشركات المسموحة فقط."""
        allowed_ids = set(companies.ids)
        children = defaultdict(list)
        for company in companies:
            parent = company.parent_id
            if parent and parent.id in allowed_ids:
                children[parent.id].append(company.id)
        return children

    @staticmethod
    def _descendants(children, company_id):
        result, stack = [], list(children.get(company_id, []))
        while stack:
            cid = stack.pop()
            result.append(cid)
            stack.extend(children.get(cid, []))
        return result

    def _scope(self, company_ids, consolidated):
        """الشركات المطلوبة (+ فروعها في العرض الموحّد). يرجع (scope, children)."""
        allowed = self.env.user.company_ids.sorted('id')
        selected = self._allowed_companies(company_ids)
        children = self._children_map(allowed)
        scope_ids = set(selected.ids)
        if consolidated:
            for cid in selected.ids:
                scope_ids.update(self._descendants(children, cid))
        return allowed.filtered(lambda c: c.id in scope_ids), children, allowed

    @staticmethod
    def _sum_stats(stats, ids):
        total = sum((stats.get(i) or {}).get('total', 0.0) for i in ids)
        orders = sum((stats.get(i) or {}).get('orders', 0) for i in ids)
        return total, orders

    def _orders_domain(self, companies, start, end):
        return [
            ('state', '=', 'sale'),
            ('company_id', 'in', companies.ids),
            ('date_order', '>=', start),
            ('date_order', '<', end),
        ]

    def _aggregate(self, companies, start, end, rate, granularity=None):
        """يرجع (totals, series):
        totals[company_id] = {'total', 'orders'}
        series[company_id][bucket_date] = amount
        """
        Order = self.env['sale.order'].sudo().with_context(tz=self.env.user.tz or 'UTC')
        domain = self._orders_domain(companies, start, end)

        totals = defaultdict(lambda: {'total': 0.0, 'orders': 0})
        rows = Order._read_group(
            domain, ['company_id', 'currency_id'], ['amount_total:sum', '__count'])
        for company, currency, amount, count in rows:
            item = totals[company.id]
            item['total'] += (amount or 0.0) * rate(currency, company)
            item['orders'] += count

        series = defaultdict(lambda: defaultdict(float))
        if granularity:
            rows = Order._read_group(
                domain, ['company_id', 'currency_id', 'date_order:%s' % granularity],
                ['amount_total:sum'])
            for company, currency, bucket, amount in rows:
                if not bucket:
                    continue
                key = bucket.date() if isinstance(bucket, datetime) else bucket
                series[company.id][key] += (amount or 0.0) * rate(currency, company)
        return totals, series

    @staticmethod
    def _growth(current, previous):
        if not previous:
            return None
        return round((current - previous) / abs(previous) * 100.0, 1)

    def _currency_info(self, currency):
        return {
            'symbol': currency.symbol,
            'name': currency.name,
            'position': currency.position,
            'decimals': currency.decimal_places,
        }

    # ------------------------------------------------------------- public API
    @api.model
    def get_sales_overview(self, date_from, date_to, company_ids=None, consolidated=True):
        """consolidated=True: بطاقة الشركة الأم تجمع مبيعاتها مع كل فروعها.
        الإجماليات العامة والرسوم (own_*) لا تكرر الحساب أبداً."""
        self._check_dashboard_access()
        scope, children, all_companies = self._scope(company_ids, consolidated)

        d_from, d_to, start, end = self._parse_dates(date_from, date_to)
        granularity = 'day' if ((d_to - d_from).days + 1) <= MAX_DAILY_DAYS else 'month'
        buckets = self._make_buckets(d_from, d_to, granularity)

        target_currency = self.env.company.currency_id
        rate = self._rate_getter(target_currency, d_to)

        current, series = self._aggregate(scope, start, end, rate, granularity)
        previous, _unused = self._aggregate(scope, start - (end - start), start, rate)

        # الإجماليات = مبيعات كل شركة بذاتها (بدون تكرار)
        grand_total, grand_orders = self._sum_stats(current, scope.ids)
        prev_total, _o = self._sum_stats(previous, scope.ids)

        scope_ids = set(scope.ids)
        rows = []
        for company in scope:
            if consolidated:
                ids = [company.id] + [i for i in self._descendants(children, company.id) if i in scope_ids]
            else:
                ids = [company.id]
            total, orders = self._sum_stats(current, ids)
            prev, _o = self._sum_stats(previous, ids)
            own_total, own_orders = self._sum_stats(current, [company.id])
            rows.append({
                'id': company.id,
                'name': company.name,
                'is_parent': len(ids) > 1,
                'branches': len(ids) - 1,
                'total': round(total, 2),
                'orders': orders,
                'avg': round(total / orders, 2) if orders else 0.0,
                'share': round(total / grand_total * 100.0, 1) if grand_total else 0.0,
                'prev_total': round(prev, 2),
                'growth': self._growth(total, prev),
                'series': [round(sum(series[i].get(b, 0.0) for i in ids), 2) for b in buckets],
                # مبيعات الشركة بذاتها فقط (للمخطط الدائري ومخطط المقارنة)
                'own_total': round(own_total, 2),
                'own_orders': own_orders,
                'own_series': [round(series[company.id].get(b, 0.0), 2) for b in buckets],
            })

        return {
            'currency': self._currency_info(target_currency),
            'all_companies': [{'id': c.id, 'name': c.name} for c in all_companies],
            'consolidated': bool(consolidated),
            'companies': rows,
            'granularity': granularity,
            'buckets': [b.isoformat() for b in buckets],
            'totals': {
                'total': round(grand_total, 2),
                'orders': grand_orders,
                'avg': round(grand_total / grand_orders, 2) if grand_orders else 0.0,
                'prev_total': round(prev_total, 2),
                'growth': self._growth(grand_total, prev_total),
            },
        }

    @api.model
    def get_company_details(self, company_id, date_from, date_to, consolidated=True):
        self._check_dashboard_access()
        scope, children, _all = self._scope([company_id], consolidated)
        company = scope.filtered(lambda c: c.id == company_id)
        if not company:
            raise AccessError(_("لا تملك صلاحية على هذه الشركة."))

        d_from, d_to, start, end = self._parse_dates(date_from, date_to)
        granularity = 'day' if ((d_to - d_from).days + 1) <= MAX_DAILY_DAYS else 'month'
        buckets = self._make_buckets(d_from, d_to, granularity)

        target_currency = self.env.company.currency_id
        rate = self._rate_getter(target_currency, d_to)

        current, series = self._aggregate(scope, start, end, rate, granularity)
        previous, _unused = self._aggregate(scope, start - (end - start), start, rate)
        total, orders = self._sum_stats(current, scope.ids)
        prev, _o = self._sum_stats(previous, scope.ids)

        Order = self.env['sale.order'].sudo()
        domain = self._orders_domain(scope, start, end)

        def top(rows, name_fn):
            acc = {}
            for comp, rec, currency, amount, count in rows:
                item = acc.setdefault(rec.id or 0, {'name': name_fn(rec), 'value': 0.0, 'count': 0})
                item['value'] += (amount or 0.0) * rate(currency, comp)
                item['count'] += count
            items = sorted(acc.values(), key=lambda i: i['value'], reverse=True)[:TOP_N]
            for item in items:
                item['value'] = round(item['value'], 2)
            return items

        def name_of(rec):
            return rec.display_name if rec else _("غير محدد")

        customers = top(Order._read_group(
            domain, ['company_id', 'partner_id', 'currency_id'], ['amount_total:sum', '__count']), name_of)
        salespeople = top(Order._read_group(
            domain, ['company_id', 'user_id', 'currency_id'], ['amount_total:sum', '__count']), name_of)

        Line = self.env['sale.order.line'].sudo()
        line_domain = [
            ('order_id.state', '=', 'sale'),
            ('order_id.company_id', 'in', scope.ids),
            ('order_id.date_order', '>=', start),
            ('order_id.date_order', '<', end),
            ('display_type', '=', False),
        ]
        products = top(Line._read_group(
            line_domain, ['company_id', 'product_id', 'currency_id'], ['price_total:sum', '__count']),
            lambda rec: rec.display_name if rec else _("بدون منتج"))

        return {
            'company': {'id': company.id, 'name': company.name, 'branches': len(scope) - 1},
            'currency': self._currency_info(target_currency),
            'granularity': granularity,
            'buckets': [b.isoformat() for b in buckets],
            'series': [round(sum(series[i].get(b, 0.0) for i in scope.ids), 2) for b in buckets],
            'totals': {
                'total': round(total, 2),
                'orders': orders,
                'avg': round(total / orders, 2) if orders else 0.0,
                'prev_total': round(prev, 2),
                'growth': self._growth(total, prev),
            },
            'products': products,
            'customers': customers,
            'salespeople': salespeople,
        }

    # ------------------------------------------------------------ branches screen
    def _ar_domain(self, companies):
        return [
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('company_id', 'in', companies.ids),
        ]

    def _branch_figures(self, companies, d_from, d_to, start, end, rate):
        """يرجع (sales, debt, paid) لكل شركة بعملة التقرير.
        sales/paid خلال الفترة، debt رصيد حتى d_to."""
        Line = self.env['account.move.line'].sudo()
        sales, _unused = self._aggregate(companies, start, end, rate)

        debt = defaultdict(float)
        domain = self._ar_domain(companies) + [('date', '<=', d_to)]
        for company, balance in Line._read_group(domain, ['company_id'], ['balance:sum']):
            debt[company.id] += (balance or 0.0) * rate(company.currency_id, company)

        paid = defaultdict(float)
        domain = self._ar_domain(companies) + [
            ('move_id.move_type', '=', 'entry'),
            ('date', '>=', d_from),
            ('date', '<=', d_to),
        ]
        for company, credit, debit in Line._read_group(
                domain, ['company_id'], ['credit:sum', 'debit:sum']):
            paid[company.id] += ((credit or 0.0) - (debit or 0.0)) * rate(company.currency_id, company)
        return sales, debt, paid

    def _recent_activity(self, companies, rate, limit=12):
        """آخر أوامر البيع المؤكدة وآخر السدادات (للشريط الحي)."""
        events = []
        Order = self.env['sale.order'].sudo()
        for order in Order.search(
                [('state', '=', 'sale'), ('company_id', 'in', companies.ids)],
                order='date_order desc, id desc', limit=limit):
            events.append({
                'id': 's%d' % order.id,
                'type': 'sale',
                'company': order.company_id.name,
                'partner': order.partner_id.display_name or '',
                'ref': order.name,
                'amount': round(order.amount_total * rate(order.currency_id, order.company_id), 2),
                'ts': order.date_order.isoformat() + 'Z' if order.date_order else '',
            })
        Line = self.env['account.move.line'].sudo()
        domain = self._ar_domain(companies) + [
            ('move_id.move_type', '=', 'entry'), ('credit', '>', 0)]
        for line in Line.search(domain, order='create_date desc, id desc', limit=limit):
            events.append({
                'id': 'p%d' % line.id,
                'type': 'payment',
                'company': line.company_id.name,
                'partner': line.partner_id.display_name or '',
                'ref': line.move_id.name or '',
                'amount': round(line.credit * rate(line.company_id.currency_id, line.company_id), 2),
                'ts': line.create_date.isoformat() + 'Z' if line.create_date else '',
            })
        events.sort(key=lambda e: e['ts'], reverse=True)
        return events[:limit]

    @api.model
    def get_branches_overview(self, date_from, date_to, company_ids=None):
        self._check_dashboard_access()
        all_companies = self.env.user.company_ids.sorted('id')
        companies = self._allowed_companies(company_ids).sorted('id')

        d_from, d_to, start, end = self._parse_dates(date_from, date_to)
        days = (d_to - d_from).days + 1
        prev_to = d_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        p_from, p_to, p_start, p_end = self._parse_dates(prev_from, prev_to)

        target_currency = self.env.company.currency_id
        rate = self._rate_getter(target_currency, d_to)

        sales, debt, paid = self._branch_figures(companies, d_from, d_to, start, end, rate)
        p_sales, p_debt, p_paid = self._branch_figures(companies, p_from, p_to, p_start, p_end, rate)

        rows = []
        for company in companies:
            cid = company.id
            s_val = (sales.get(cid) or {}).get('total', 0.0)
            s_prev = (p_sales.get(cid) or {}).get('total', 0.0)
            d_val, d_prev = debt.get(cid, 0.0), p_debt.get(cid, 0.0)
            p_val, p_prev = paid.get(cid, 0.0), p_paid.get(cid, 0.0)
            rows.append({
                'id': cid,
                'name': company.name,
                'sales': round(s_val, 2),
                'debt': round(d_val, 2),
                'paid': round(p_val, 2),
                'sales_growth': self._growth(s_val, s_prev),
                'debt_growth': self._growth(d_val, d_prev),
                'paid_growth': self._growth(p_val, p_prev),
                'collection_rate': round(p_val / s_val * 100.0, 1) if s_val else None,
            })

        tot_s = sum(r['sales'] for r in rows)
        tot_d = sum(r['debt'] for r in rows)
        tot_p = sum(r['paid'] for r in rows)
        prev_s = sum((p_sales.get(c.id) or {}).get('total', 0.0) for c in companies)
        prev_d = sum(p_debt.get(c.id, 0.0) for c in companies)
        prev_p = sum(p_paid.get(c.id, 0.0) for c in companies)

        return {
            'currency': self._currency_info(target_currency),
            'all_companies': [{'id': c.id, 'name': c.name} for c in all_companies],
            'companies': rows,
            'totals': {
                'sales': round(tot_s, 2),
                'debt': round(tot_d, 2),
                'paid': round(tot_p, 2),
                'sales_growth': self._growth(tot_s, prev_s),
                'debt_growth': self._growth(tot_d, prev_d),
                'paid_growth': self._growth(tot_p, prev_p),
                'collection_rate': round(tot_p / tot_s * 100.0, 1) if tot_s else None,
            },
            'feed': self._recent_activity(companies, rate),
        }
