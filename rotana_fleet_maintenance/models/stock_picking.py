# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rotana_request_id = fields.Many2one(
        'rotana.maintenance.request',
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

    rotana_part_id = fields.Many2one(
        'rotana.maintenance.part',
        string='سطر قطعة الغيار',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
        help='سطر قطعة الغيار في طلب الصيانة المرتبط بهذا السطر في إذن التسليم.',
    )

    def _get_rotana_part(self):
        """ سطر قطعة الغيار المرتبط بسطر إذن التسليم (بالربط المباشر أو بالطلب والمنتج). """
        self.ensure_one()
        if self.rotana_part_id:
            return self.rotana_part_id
        picking = self.picking_id
        if picking.rotana_request_id and picking.picking_type_code == 'outgoing':
            return self.env['rotana.maintenance.part'].sudo().search([
                ('request_id', '=', picking.rotana_request_id.id),
                ('product_id', '=', self.product_id.id),
            ], limit=1)
        return self.env['rotana.maintenance.part']

    def write(self, vals):
        if 'product_id' in vals:
            for move in self:
                if move.product_id.id != vals['product_id'] and move._get_rotana_part():
                    raise UserError(_(
                        'لا يمكن تغيير المنتج في سطر إذن مرتبط بطلب صيانة. '
                        'ألغِ التأكيد في طلب الصيانة وعدّل قطعة الغيار هناك.'))
        return super().write(vals)
