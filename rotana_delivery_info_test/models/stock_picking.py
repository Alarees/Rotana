# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_transport_type = fields.Selection(
        [('customer', 'العميل'), ('company', 'الشركة')],
        string='Transport Type',
        copy=False,
    )
    x_driver_name = fields.Char(string='Driver Name', copy=False)
    x_truck_plate_number = fields.Char(string='Truck Plate Number', copy=False)
    x_driver_phone = fields.Char(string='Driver Phone', copy=False)
    x_destination = fields.Char(string='Destination', copy=False)
    x_customer_tax_id = fields.Char(string='Customer Tax ID', copy=False)
    agent_customer_name = fields.Char(string='Agent Customer Name', copy=False)
