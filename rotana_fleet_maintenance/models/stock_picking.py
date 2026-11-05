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


class StockMove(models.Model):
    _inherit = 'stock.move'

    maintenance_part_id = fields.Many2one(
        'maintenance.request.part',
        string='سطر قطعة الغيار',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
        help='سطر قطعة الغيار في طلب الصيانة المرتبط بهذا السطر في إذن التسليم.',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals:
            # تغيير المنتج في إذن التسليم ينتقل إلى سطر قطعة الغيار في طلب الصيانة
            for move in self.filtered('maintenance_part_id'):
                part = move.maintenance_part_id.sudo()
                if part.product_id != move.product_id:
                    part.with_context(skip_part_editable_check=True).write(
                        {'product_id': move.product_id.id})
        return res
