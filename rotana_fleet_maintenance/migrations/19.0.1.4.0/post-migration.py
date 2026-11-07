# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """ ربط أسطر أذون التسليم القديمة بسطور قطع الغيار في طلب الصيانة. """
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['stock.move'].search([
        ('maintenance_part_id', '=', False),
        ('picking_id.maintenance_request_id', '!=', False),
        ('picking_id.picking_type_code', '=', 'outgoing'),
        ('state', 'not in', ('done', 'cancel')),
    ])
    Part = env['maintenance.request.part']
    for move in moves:
        part = Part.search([
            ('request_id', '=', move.picking_id.maintenance_request_id.id),
            ('product_id', '=', move.product_id.id),
        ], limit=1)
        if part:
            move.maintenance_part_id = part.id
