# -*- coding: utf-8 -*-
from odoo import models


class MaintenanceRequestPart(models.Model):
    _inherit = 'maintenance.request.part'

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals:
            # تغيير الاسبير في سطر الصيانة ينتقل إلى طلبات الورشة التي لم تُرسل بعد
            workshops = self.env['rotana.external.workshop'].sudo().search([
                ('part_line_id', 'in', self.ids),
                ('state', 'in', ('draft', 'confirmed')),
            ])
            if workshops:
                workshops.write({'product_id': vals['product_id']})
        return res
