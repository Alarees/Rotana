# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# الأقسام المسموحة فقط (لا يُقبل أي قيمة أخرى في الرابط)
MODULES = ('sales', 'purchase', 'accounting', 'inventory', 'manufacturing')
MANAGER_GROUP = 'rotana_kpi_dashboard.group_rotana_kpi_manager'


class RotanaKpiController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def _check_manager(self):
        if not request.env.user.has_group(MANAGER_GROUP):
            raise AccessError('هذه اللوحات متاحة لمديري مؤشرات الأداء فقط.')

    def _allowed_company_ids(self):
        """الشركات المسموحة للمستخدم الحالي فقط، مقيّدة بما يطلبه الرابط (إن وُجد)."""
        user_companies = request.env.user.company_ids.ids
        raw = request.httprequest.args.get('company_ids', '')
        requested = [int(x) for x in raw.split(',') if x.strip().isdigit()]
        if requested:
            return [cid for cid in requested if cid in user_companies]
        return user_companies

    def _get_params(self):
        date_from = request.httprequest.args.get('date_from') or None
        date_to = request.httprequest.args.get('date_to') or None
        return date_from, date_to, self._allowed_company_ids()

    def _engine(self, company_ids):
        # القراءة بصلاحيات المستخدم نفسه (بدون sudo) وبسياق شركاته المسموحة فقط
        return request.env['rotana.kpi.engine'].with_context(allowed_company_ids=company_ids)

    def _kpi_response(self, method):
        try:
            self._check_manager()
            date_from, date_to, company_ids = self._get_params()
            if not company_ids:
                return self._json({'employees': []})
            data = getattr(self._engine(company_ids), method)(date_from, date_to, company_ids)
            return self._json(data)
        except (AccessError, UserError) as exc:
            return self._json({'error': str(exc)}, status=403)
        except Exception:
            _logger.exception('KPI dashboard request failed')
            return self._json({'error': 'تعذر تحميل البيانات، راجع سجل الخادم.'}, status=500)

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------
    @http.route('/rotana_kpi/companies', type='http', auth='user', methods=['GET'], csrf=False)
    def get_companies(self, **kw):
        try:
            self._check_manager()
        except AccessError as exc:
            return self._json({'error': str(exc)}, status=403)
        companies = [{'id': c.id, 'name': c.name} for c in request.env.user.company_ids]
        return self._json(companies)

    @http.route('/rotana_kpi/data/sales', type='http', auth='user', methods=['GET'], csrf=False)
    def sales_data(self, **kw):
        return self._kpi_response('get_sales_kpis')

    @http.route('/rotana_kpi/data/purchase', type='http', auth='user', methods=['GET'], csrf=False)
    def purchase_data(self, **kw):
        return self._kpi_response('get_purchase_kpis')

    @http.route('/rotana_kpi/data/accounting', type='http', auth='user', methods=['GET'], csrf=False)
    def accounting_data(self, **kw):
        return self._kpi_response('get_accounting_kpis')

    @http.route('/rotana_kpi/data/inventory', type='http', auth='user', methods=['GET'], csrf=False)
    def inventory_data(self, **kw):
        return self._kpi_response('get_inventory_kpis')

    @http.route('/rotana_kpi/data/manufacturing', type='http', auth='user', methods=['GET'], csrf=False)
    def manufacturing_data(self, **kw):
        return self._kpi_response('get_manufacturing_kpis')

    # ------------------------------------------------------------------
    # Dashboard page (one shared template, module passed as query param)
    # ------------------------------------------------------------------
    @http.route('/rotana_kpi/dashboard', type='http', auth='user', website=False)
    def dashboard(self, module='sales', **kw):
        if not request.env.user.has_group(MANAGER_GROUP):
            raise http.request.not_found()
        if module not in MODULES:
            module = 'sales'
        return request.render('rotana_kpi_dashboard.dashboard_template', {
            'module': module,
        })
