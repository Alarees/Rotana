# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    rotana_request_id = fields.Many2one(
        'rotana.maintenance.request',
        string='Maintenance Request',
        copy=False,
        index='btree_not_null',
    )
    fleet_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        copy=False,
        index='btree_not_null',
        tracking=True,
    )
    is_fleet_operation = fields.Boolean(
        related='picking_type_id.is_fleet_operation',
        string='Fleet Operation',
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    rotana_part_id = fields.Many2one(
        'rotana.maintenance.part',
        string='Spare Part Line',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
        help='Spare part line of the maintenance request linked to this delivery line.',
    )

    def _get_rotana_part(self):
        """ Spare part line linked to the delivery line (directly, or by request and product). """
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
                        'The product cannot be changed on a picking line linked to a maintenance request. '
                        'Reset the confirmation in the maintenance request and edit the spare part there.'))
        return super().write(vals)
