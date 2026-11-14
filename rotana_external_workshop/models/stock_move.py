# -*- coding: utf-8 -*-
from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_maintenance_receipt_percent(self):
        percent = super()._get_maintenance_receipt_percent()
        if percent is not None or not self.picking_id or not self.is_in:
            return percent
        workshop = self.env['rotana.external.workshop'].sudo().search(
            [('picking_id', '=', self.picking_id.id)], limit=1)
        return self.company_id.maintenance_rehab_value_percent if workshop else None
