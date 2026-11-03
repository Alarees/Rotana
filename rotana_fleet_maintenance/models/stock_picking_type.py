# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_fleet_operation = fields.Boolean(
        string='عملية مركبات',
        help='عند التفعيل يُخفى حقل العميل في أذون هذه العملية '
             'ويُعرض بدلاً منه حقل المركبة.',
    )
