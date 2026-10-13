# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class RotanaKpiController(http.Controller):

    # ------------------------------------------------------------------
    # Data endpoints (called by the React/FusionCharts front-end)
    # ------------------------------------------------------------------
    def _parse_company_ids(self):
        raw = request.httprequest.args.get('company_ids', '')
        if not raw:
            return []
        return [int(x) for x in raw.split(',') if x.strip().isdigit()]

    def _get_params(self):
        date_from = request.httprequest.args.get('date_from') or None
        date_to = request.httprequest.args.get('date_to') or None
        company_ids = self._parse_company_ids()
        return date_from, date_to, company_ids

    @http.route('/rotana_kpi/companies', type='http', auth='user', methods=['GET'], csrf=False)
    def get_companies(self, **kw):
        companies = request.env['res.company'].search_read([], ['id', 'name'])
        return request.make_response(
            json.dumps(companies),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/rotana_kpi/data/sales', type='http', auth='user', methods=['GET'], csrf=False)
    def sales_data(self, **kw):
        date_from, date_to, company_ids = self._get_params()
        data = request.env['rotana.kpi.engine'].sudo().get_sales_kpis(date_from, date_to, company_ids)
        return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json')])

    @http.route('/rotana_kpi/data/purchase', type='http', auth='user', methods=['GET'], csrf=False)
    def purchase_data(self, **kw):
        date_from, date_to, company_ids = self._get_params()
        data = request.env['rotana.kpi.engine'].sudo().get_purchase_kpis(date_from, date_to, company_ids)
        return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json')])

    @http.route('/rotana_kpi/data/accounting', type='http', auth='user', methods=['GET'], csrf=False)
    def accounting_data(self, **kw):
        date_from, date_to, company_ids = self._get_params()
        data = request.env['rotana.kpi.engine'].sudo().get_accounting_kpis(date_from, date_to, company_ids)
        return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json')])

    @http.route('/rotana_kpi/data/inventory', type='http', auth='user', methods=['GET'], csrf=False)
    def inventory_data(self, **kw):
        date_from, date_to, company_ids = self._get_params()
        data = request.env['rotana.kpi.engine'].sudo().get_inventory_kpis(date_from, date_to, company_ids)
        return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json')])

    @http.route('/rotana_kpi/data/manufacturing', type='http', auth='user', methods=['GET'], csrf=False)
    def manufacturing_data(self, **kw):
        date_from, date_to, company_ids = self._get_params()
        data = request.env['rotana.kpi.engine'].sudo().get_manufacturing_kpis(date_from, date_to, company_ids)
        return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json')])

    # ------------------------------------------------------------------
    # Dashboard page (one shared template, module passed as query param)
    # ------------------------------------------------------------------
    @http.route('/rotana_kpi/dashboard', type='http', auth='user', website=False)
    def dashboard(self, module='sales', **kw):
        return request.render('rotana_kpi_dashboard.dashboard_template', {
            'module': module,
        })
