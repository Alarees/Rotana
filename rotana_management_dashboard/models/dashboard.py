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
        return round((current - previous) / previous * 100.0, 1)

    def _currency_info(self, currency):
        return {
            'symbol': currency.symbol,
            'name': currency.name,
            'position': currency.position,
            'decimals': currency.decimal_places,
        }

    # ------------------------------------------------------------- public API
    @api.model
    def get_sales_overview(self, date_from, date_to, company_ids=None):
        self._check_dashboard_access()
        all_companies = self.env.user.company_ids.sorted('id')
        companies = self._allowed_companies(company_ids).sorted('id')

        d_from, d_to, start, end = self._parse_dates(date_from, date_to)
        granularity = 'day' if ((d_to - d_from).days + 1) <= MAX_DAILY_DAYS else 'month'
        buckets = self._make_buckets(d_from, d_to, granularity)

        target_currency = self.env.company.currency_id
        rate = self._rate_getter(target_currency, d_to)

        current, series = self._aggregate(companies, start, end, rate, granularity)
        previous, _unused = self._aggregate(companies, start - (end - start), start, rate)

        grand_total = sum(v['total'] for v in current.values())
        grand_orders = sum(v['orders'] for v in current.values())
        prev_total = sum(v['total'] for v in previous.values())

        rows = []
        for company in companies:
            cur = current.get(company.id) or {'total': 0.0, 'orders': 0}
            prev = previous.get(company.id) or {'total': 0.0, 'orders': 0}
            rows.append({
                'id': company.id,
                'name': company.name,
                'total': round(cur['total'], 2),
                'orders': cur['orders'],
                'avg': round(cur['total'] / cur['orders'], 2) if cur['orders'] else 0.0,
                'share': round(cur['total'] / grand_total * 100.0, 1) if grand_total else 0.0,
                'prev_total': round(prev['total'], 2),
                'growth': self._growth(cur['total'], prev['total']),
                'series': [round(series[company.id].get(b, 0.0), 2) for b in buckets],
            })

        return {
            'currency': self._currency_info(target_currency),
            'all_companies': [{'id': c.id, 'name': c.name} for c in all_companies],
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
    def get_company_details(self, company_id, date_from, date_to):
        self._check_dashboard_access()
        company = self._allowed_companies([company_id])
        if not company:
            raise AccessError(_("لا تملك صلاحية على هذه الشركة."))

        d_from, d_to, start, end = self._parse_dates(date_from, date_to)
        granularity = 'day' if ((d_to - d_from).days + 1) <= MAX_DAILY_DAYS else 'month'
        buckets = self._make_buckets(d_from, d_to, granularity)

        target_currency = self.env.company.currency_id
        rate = self._rate_getter(target_currency, d_to)

        current, series = self._aggregate(company, start, end, rate, granularity)
        previous, _unused = self._aggregate(company, start - (end - start), start, rate)
        cur = current.get(company.id) or {'total': 0.0, 'orders': 0}
        prev = previous.get(company.id) or {'total': 0.0, 'orders': 0}

        Order = self.env['sale.order'].sudo()
        domain = self._orders_domain(company, start, end)

        def top(rows, name_fn):
            acc = {}
            for rec, currency, amount, count in rows:
                item = acc.setdefault(rec.id or 0, {'name': name_fn(rec), 'value': 0.0, 'count': 0})
                item['value'] += (amount or 0.0) * rate(currency, company)
                item['count'] += count
            items = sorted(acc.values(), key=lambda i: i['value'], reverse=True)[:TOP_N]
            for item in items:
                item['value'] = round(item['value'], 2)
            return items

        def name_of(rec):
            return rec.display_name if rec else _("غير محدد")

        customers = top(Order._read_group(
            domain, ['partner_id', 'currency_id'], ['amount_total:sum', '__count']), name_of)
        salespeople = top(Order._read_group(
            domain, ['user_id', 'currency_id'], ['amount_total:sum', '__count']), name_of)

        Line = self.env['sale.order.line'].sudo()
        line_domain = [
            ('order_id.state', '=', 'sale'),
            ('order_id.company_id', '=', company.id),
            ('order_id.date_order', '>=', start),
            ('order_id.date_order', '<', end),
            ('display_type', '=', False),
        ]
        products = top(Line._read_group(
            line_domain, ['product_id', 'currency_id'], ['price_total:sum', '__count']),
            lambda rec: rec.display_name if rec else _("بدون منتج"))

        return {
            'company': {'id': company.id, 'name': company.name},
            'currency': self._currency_info(target_currency),
            'granularity': granularity,
            'buckets': [b.isoformat() for b in buckets],
            'series': [round(series[company.id].get(b, 0.0), 2) for b in buckets],
            'totals': {
                'total': round(cur['total'], 2),
                'orders': cur['orders'],
                'avg': round(cur['total'] / cur['orders'], 2) if cur['orders'] else 0.0,
                'prev_total': round(prev['total'], 2),
                'growth': self._growth(cur['total'], prev['total']),
            },
            'products': products,
            'customers': customers,
            'salespeople': salespeople,
        }
