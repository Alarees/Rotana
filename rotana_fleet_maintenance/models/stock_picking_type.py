# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_fleet_operation = fields.Boolean(
        string='Fleet Operation',
        help='When enabled, the customer field is hidden on the pickings of this operation '
             'and the vehicle field is shown instead.',
    )
