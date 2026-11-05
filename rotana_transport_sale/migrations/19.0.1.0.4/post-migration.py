# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute the weight totals of transport orders after the weight logic fix."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['sale.order'].with_context(active_test=False).search(
        [('is_transport_order', '=', True)]
    )
    for field_name in ('total_weight_to_transport', 'total_transported_weight'):
        env.add_to_compute(env['sale.order']._fields[field_name], orders)
    env.flush_all()
