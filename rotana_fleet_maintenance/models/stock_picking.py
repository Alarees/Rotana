# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='طلب الصيانة',
        copy=False,
        index='btree_not_null',
    )
