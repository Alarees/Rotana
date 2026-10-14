# -*- coding: utf-8 -*-
import io
import json

import xlsxwriter

from odoo import http
from odoo.http import content_disposition, request


class RotanaTransportDashboardController(http.Controller):

    @http.route('/rotana_transport/dashboard/export/<string:fmt>', type='http', auth='user', methods=['POST'])
    def export(self, fmt, section, filters='{}', **kwargs):
        filters = json.loads(filters or '{}')
        table = request.env['rotana.transport.dashboard'].get_export_table(section, filters)
        if fmt == 'xlsx':
            return self._xlsx(table, section)
        return self._pdf(table, section)

    def _xlsx(self, table, section):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet(table['title'][:31].replace('/', '-'))
        ws.right_to_left()
        head = wb.add_format({'bold': True, 'bg_color': '#3949AB', 'font_color': '#FFFFFF',
                              'border': 1, 'align': 'center'})
        title = wb.add_format({'bold': True, 'font_size': 14})
        num = wb.add_format({'num_format': '#,##0.00', 'border': 1})
        txt = wb.add_format({'border': 1})
        tot_num = wb.add_format({'num_format': '#,##0.00', 'border': 1, 'bold': True, 'bg_color': '#E8EAF6'})
        tot_txt = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#E8EAF6'})
        ws.write(0, 0, table['title'], title)
        if table['filters_text']:
            ws.write(1, 0, table['filters_text'])
        r0 = 3
        for c, label in enumerate(table['columns']):
            ws.write(r0, c, label, head)
            ws.set_column(c, c, 18)
        numeric = ('float', 'shortage', 'profit')
        for i, row in enumerate(table['rows'], start=r0 + 1):
            for c, val in enumerate(row):
                if table['types'][c] in numeric:
                    ws.write_number(i, c, val or 0.0, num)
                else:
                    ws.write(i, c, '' if val in (None, False) else val, txt)
        if table['total_row']:
            i = r0 + 1 + len(table['rows'])
            for c, val in enumerate(table['total_row']):
                if table['types'][c] in numeric and val != '':
                    ws.write_number(i, c, val or 0.0, tot_num)
                else:
                    ws.write(i, c, val, tot_txt)
        wb.close()
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('%s.xlsx' % section)),
        ])

    def _pdf(self, table, section):
        pdf, _fmt = request.env['ir.actions.report']._render_qweb_pdf(
            'rotana_transport_sale.action_report_rotana_dashboard',
            res_ids=[request.env.user.id], data={'table': table})
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition('%s.pdf' % section)),
        ])
