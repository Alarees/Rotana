# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """ ربط أسطر أذون التسليم القديمة بسطور قطع الغيار في طلب الصيانة (بحث واحد لكل الأسطر). """
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['stock.move'].search([
        ('maintenance_part_id', '=', False),
        ('picking_id.maintenance_request_id', '!=', False),
        ('picking_id.picking_type_code', '=', 'outgoing'),
        ('state', 'not in', ('done', 'cancel')),
    ])
    if not moves:
        return
    parts = env['maintenance.request.part'].search([
        ('request_id', 'in', moves.picking_id.maintenance_request_id.ids),
    ])
    part_by_key = {}
    for part in parts:
        part_by_key.setdefault((part.request_id.id, part.product_id.id), part)
    for move in moves:
        part = part_by_key.get((move.picking_id.maintenance_request_id.id, move.product_id.id))
        if part:
            move.maintenance_part_id = part.id
