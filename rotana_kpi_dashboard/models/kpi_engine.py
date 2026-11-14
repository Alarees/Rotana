# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from odoo import api, models
from odoo.tools import float_round


def _hours_between(d1, d2):
    """Return positive hours between two datetimes, or 0 if any missing/invalid."""
    if not d1 or not d2:
        return 0.0
    delta = d2 - d1
    hours = delta.total_seconds() / 3600.0
    return round(hours, 2) if hours > 0 else 0.0


class RotanaKpiEngine(models.AbstractModel):
    """Central computation engine for all Rotana KPI dashboards.

    All methods take:
      - date_from, date_to: 'YYYY-MM-DD' strings (inclusive range)
      - company_ids: list[int] (branches). Empty/None = all allowed companies.

    All methods return a dict shaped for direct consumption by the
    dashboard front-end: {'employees': [...]}
    """
    _name = 'rotana.kpi.engine'
    _description = 'Rotana KPI Computation Engine'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _domain_dates(self, date_from, date_to, field='create_date'):
        domain = []
        if date_from:
            domain.append((field, '>=', f'{date_from} 00:00:00'))
        if date_to:
            domain.append((field, '<=', f'{date_to} 23:59:59'))
        return domain

    def _domain_company(self, company_ids, field='company_id'):
        # الشركات المسموحة دائماً تأتي من المتحكم؛ لا يُترك الحقل فارغاً أبداً
        company_ids = company_ids or self.env.user.company_ids.ids
        return [(field, 'in', company_ids)]

    def _get_sale_confirm_dates(self, orders):
        """لحظة تأكيد كل أمر بيع من رسالة التتبع (قراءة واحدة)، وإلا تاريخ الأمر إن لم تتوفر."""
        if not orders:
            return {}
        subtype = self.env.ref('sale.mt_order_confirmed', raise_if_not_found=False)
        dates = {}
        if subtype:
            rows = self.env['mail.message'].sudo().search_read(
                [('model', '=', 'sale.order'), ('res_id', 'in', orders.ids),
                 ('subtype_id', '=', subtype.id)],
                ['res_id', 'date'], order='date asc')
            for row in rows:
                dates.setdefault(row['res_id'], row['date'])
        for order in orders:
            if order.id not in dates and order.state in ('sale', 'done') and order.date_order:
                dates[order.id] = order.date_order
        return dates

    # ------------------------------------------------------------------
    # 1. SALES KPIs
    # ------------------------------------------------------------------
    @api.model
    def get_sales_kpis(self, date_from=None, date_to=None, company_ids=None):
        Sale = self.env['sale.order']
        # الفترة بتاريخ المستند (date_order) لا تاريخ الإنشاء، وتُستبعد الملغاة
        domain = self._domain_dates(date_from, date_to, 'date_order') + \
            self._domain_company(company_ids) + [('state', '!=', 'cancel')]
        orders = Sale.search(domain)
        confirm_dates = self._get_sale_confirm_dates(orders)

        by_user = {}
        for order in orders:
            user = order.user_id
            if not user:
                continue
            data = by_user.setdefault(user.id, {
                'employee': user.name,
                'quotations_count': 0,
                'confirmed_count': 0,
                'response_hours_sum': 0.0,
                'response_hours_n': 0,
                'new_customers': set(),
                'orders_no_invoice': 0,
                'orders_total_confirmed': 0,
            })
            data['quotations_count'] += 1
            if order.state in ('sale', 'done'):
                data['confirmed_count'] += 1
                data['orders_total_confirmed'] += 1
                # زمن الاستجابة: من إنشاء العرض حتى لحظة التأكيد الفعلية
                confirm_date = confirm_dates.get(order.id)
                hours = _hours_between(order.create_date, confirm_date) if confirm_date else 0.0
                if hours:
                    data['response_hours_sum'] += hours
                    data['response_hours_n'] += 1
                if order.invoice_status == 'no':
                    data['orders_no_invoice'] += 1
                if order.partner_id:
                    data['new_customers'].add(order.partner_id.id)

        # العملاء الجدد: أول أمر بيع للعميل (أي موظف) يقع داخل الفترة.
        # قراءة مجمّعة واحدة بدل بحث لكل عميل، وتعمل بتاريخ واحد أو بتاريخين.
        all_partner_ids = set()
        for d in by_user.values():
            all_partner_ids |= d['new_customers']
        first_order_date = {}
        if all_partner_ids:
            groups = Sale._read_group(
                [('partner_id', 'in', list(all_partner_ids)), ('state', '!=', 'cancel')],
                groupby=['partner_id'],
                aggregates=['date_order:min'],
            )
            first_order_date = {partner.id: first for partner, first in groups}

        def _in_period(value):
            if not value:
                return False
            day = value.strftime('%Y-%m-%d')
            return (not date_from or day >= date_from) and (not date_to or day <= date_to)

        result = []
        for uid, d in by_user.items():
            new_customers_count = sum(
                1 for partner_id in d['new_customers']
                if _in_period(first_order_date.get(partner_id))
            )
            avg_response = float_round(
                d['response_hours_sum'] / d['response_hours_n'], 2
            ) if d['response_hours_n'] else 0.0
            pct_no_invoice = float_round(
                (d['orders_no_invoice'] / d['orders_total_confirmed']) * 100, 2
            ) if d['orders_total_confirmed'] else 0.0

            result.append({
                'employee': d['employee'],
                'quotations_count': d['quotations_count'],
                'avg_response_time_hours': avg_response,
                'new_customers': new_customers_count,
                'pct_sales_without_invoice': pct_no_invoice,
            })

        result.sort(key=lambda r: r['quotations_count'], reverse=True)
        return {'employees': result}

    # ------------------------------------------------------------------
    # 2. PURCHASE KPIs
    # ------------------------------------------------------------------
    @api.model
    def get_purchase_kpis(self, date_from=None, date_to=None, company_ids=None):
        Purchase = self.env['purchase.order']
        domain = self._domain_dates(date_from, date_to, 'date_order') + \
            self._domain_company(company_ids) + [('state', '!=', 'cancel')]
        orders = Purchase.search(domain)

        by_user = {}
        for order in orders:
            user = order.user_id
            if not user:
                continue
            data = by_user.setdefault(user.id, {
                'employee': user.name,
                'po_count': 0,
                'lead_time_sum': 0.0,
                'lead_time_n': 0,
            })
            data['po_count'] += 1
            if order.state in ('purchase', 'done'):
                # Lead time: creation -> approval (date_approve)
                hours = _hours_between(order.create_date, order.date_approve)
                if hours:
                    data['lead_time_sum'] += hours
                    data['lead_time_n'] += 1

        result = []
        for uid, d in by_user.items():
            avg_lead_time = float_round(
                d['lead_time_sum'] / d['lead_time_n'], 2
            ) if d['lead_time_n'] else 0.0
            result.append({
                'employee': d['employee'],
                'po_count': d['po_count'],
                'avg_lead_time_hours': avg_lead_time,
            })
        result.sort(key=lambda r: r['po_count'], reverse=True)
        return {'employees': result}

    # ------------------------------------------------------------------
    # 3. ACCOUNTING KPIs
    # ------------------------------------------------------------------
    @api.model
    def get_accounting_kpis(self, date_from=None, date_to=None, company_ids=None):
        Move = self.env['account.move']
        domain = self._domain_dates(date_from, date_to, 'date') + self._domain_company(company_ids) + \
            [('move_type', 'in', ('out_invoice', 'out_refund')), ('state', '!=', 'cancel')]
        moves = Move.search(domain)

        by_user = {}
        for move in moves:
            user = move.invoice_user_id or move.create_uid
            if not user:
                continue
            data = by_user.setdefault(user.id, {
                'employee': user.name,
                'total_invoices': 0,
                'unposted_invoices': 0,
                'confirm_hours_sum': 0.0,
                'confirm_hours_n': 0,
            })
            data['total_invoices'] += 1
            if move.state == 'draft':
                data['unposted_invoices'] += 1
            if move.state == 'posted':
                hours = _hours_between(move.create_date, move.date)
                if hours:
                    data['confirm_hours_sum'] += hours
                    data['confirm_hours_n'] += 1

        result = []
        for uid, d in by_user.items():
            pct_unposted = float_round(
                (d['unposted_invoices'] / d['total_invoices']) * 100, 2
            ) if d['total_invoices'] else 0.0
            avg_confirm = float_round(
                d['confirm_hours_sum'] / d['confirm_hours_n'], 2
            ) if d['confirm_hours_n'] else 0.0
            result.append({
                'employee': d['employee'],
                'total_invoices': d['total_invoices'],
                'pct_unposted_invoices': pct_unposted,
                'avg_confirm_time_hours': avg_confirm,
            })
        result.sort(key=lambda r: r['total_invoices'], reverse=True)
        return {'employees': result}

    # ------------------------------------------------------------------
    # 4. INVENTORY KPIs
    # ------------------------------------------------------------------
    @api.model
    def get_inventory_kpis(self, date_from=None, date_to=None, company_ids=None):
        Picking = self.env['stock.picking']
        domain = self._domain_dates(date_from, date_to, 'scheduled_date') + \
            self._domain_company(company_ids) + [('state', '!=', 'cancel')]
        pickings = Picking.search(domain)

        by_user = {}
        for picking in pickings:
            user = picking.user_id or picking.create_uid
            if not user:
                continue
            data = by_user.setdefault(user.id, {
                'employee': user.name,
                'total_pickings': 0,
                'on_time': 0,
                'done_pickings': 0,
                'moves_processed': 0,
                'validation_hours_sum': 0.0,
                'validation_hours_n': 0,
            })
            data['total_pickings'] += 1
            data['moves_processed'] += len(picking.move_ids)
            if picking.state == 'done':
                data['done_pickings'] += 1
                if picking.date_done and picking.scheduled_date and picking.date_done <= picking.scheduled_date:
                    data['on_time'] += 1
                hours = _hours_between(picking.create_date, picking.date_done)
                if hours:
                    data['validation_hours_sum'] += hours
                    data['validation_hours_n'] += 1

        # Determine number of distinct days in period to average moves/day
        n_days = 1
        if date_from and date_to:
            d1 = datetime.strptime(date_from, '%Y-%m-%d')
            d2 = datetime.strptime(date_to, '%Y-%m-%d')
            n_days = max((d2 - d1).days + 1, 1)

        result = []
        for uid, d in by_user.items():
            pct_on_time = float_round(
                (d['on_time'] / d['done_pickings']) * 100, 2
            ) if d['done_pickings'] else 0.0
            avg_validation = float_round(
                d['validation_hours_sum'] / d['validation_hours_n'], 2
            ) if d['validation_hours_n'] else 0.0
            result.append({
                'employee': d['employee'],
                'total_pickings': d['total_pickings'],
                'pct_on_time_fulfillment': pct_on_time,
                'moves_per_day': float_round(d['moves_processed'] / n_days, 2),
                'avg_validation_time_hours': avg_validation,
            })
        result.sort(key=lambda r: r['total_pickings'], reverse=True)
        return {'employees': result}

    # ------------------------------------------------------------------
    # 5. MANUFACTURING KPIs
    # ------------------------------------------------------------------
    @api.model
    def get_manufacturing_kpis(self, date_from=None, date_to=None, company_ids=None):
        Production = self.env['mrp.production']
        domain = self._domain_dates(date_from, date_to, 'date_start') + \
            self._domain_company(company_ids) + [('state', '!=', 'cancel')]
        productions = Production.search(domain)

        by_user = {}
        for mo in productions:
            user = mo.user_id or mo.create_uid
            if not user:
                continue
            data = by_user.setdefault(user.id, {
                'employee': user.name,
                'total_mo': 0,
                'completed_mo': 0,
                'processing_hours_sum': 0.0,
                'processing_hours_n': 0,
            })
            data['total_mo'] += 1
            if mo.state == 'done':
                data['completed_mo'] += 1
            hours = _hours_between(mo.create_date, mo.date_start)
            if hours:
                data['processing_hours_sum'] += hours
                data['processing_hours_n'] += 1

        result = []
        for uid, d in by_user.items():
            pct_completed = float_round(
                (d['completed_mo'] / d['total_mo']) * 100, 2
            ) if d['total_mo'] else 0.0
            avg_processing = float_round(
                d['processing_hours_sum'] / d['processing_hours_n'], 2
            ) if d['processing_hours_n'] else 0.0
            result.append({
                'employee': d['employee'],
                'total_mo': d['total_mo'],
                'pct_completed_mo': pct_completed,
                'avg_processing_time_hours': avg_processing,
            })
        result.sort(key=lambda r: r['total_mo'], reverse=True)
        return {'employees': result}
