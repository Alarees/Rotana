from odoo import _, api, fields, models

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    _rec_names_search = ['name', 'driver_id.name', 'unit_number']
