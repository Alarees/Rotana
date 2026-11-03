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
    fleet_id = fields.Many2one(
        'fleet.vehicle',
        string='المركبة',
        copy=False,
        index='btree_not_null',
        tracking=True,
    )
    is_fleet_operation = fields.Boolean(
        related='picking_type_id.is_fleet_operation',
        string='عملية مركبات',
    )
