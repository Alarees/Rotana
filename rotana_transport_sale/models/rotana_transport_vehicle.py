# -*- coding: utf-8 -*-
"""نموذج مركبات النقل لشركة روتانا.

يُدير بيانات المركبات المستخدمة في خدمات النقل،
بما في ذلك الموقع الحالي للمركبة الذي يُحدَّث تلقائياً
عند اكتمال الرحلة.
"""
from odoo import _, api, fields, models


class RotanaTransportVehicle(models.Model):
    _name = 'rotana.transport.vehicle'
    _description = 'Transport Vehicle'
    _order = 'name'
    _rec_names_search = ['name', 'license_plate']

    name = fields.Char(
        string='Vehicle Name',
        required=True,
        index=True,
    )

    license_plate = fields.Char(
        string='License Plate',
        required=True,
        index=True,
    )

    vehicle_type = fields.Selection(
        selection=[
            ('truck', 'Truck'),
            ('trailer', 'Trailer'),
            ('van', 'Van'),
            ('pickup', 'Pickup'),
            ('bus', 'Bus'),
            ('other', 'Other'),
        ],
        string='Vehicle Type',
        default='truck',
        required=True,
    )

    current_location_id = fields.Many2one(
        'rotana.transport.location',
        string='Current Location',
        index=True,
        help='Current location of the vehicle. Updated automatically when a trip is completed.',
    )

    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Fleet Vehicle',
        index=True,
        help='Link to the Fleet module if it is enabled.',
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        index=True,
        help="This vehicle's analytic account for financial tracking.",
    )

    capacity_ton = fields.Float(string='Capacity (Tons)')

    notes = fields.Text(string='Notes')

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    _license_plate_company_unique = models.Constraint(
        'UNIQUE(license_plate, company_id)',
        'The vehicle license plate must be unique per company.',
    )

    @api.depends('name', 'license_plate')
    def _compute_display_name(self):
        for vehicle in self:
            vehicle.display_name = (
                f'[{vehicle.license_plate}] {vehicle.name}'
                if vehicle.license_plate else vehicle.name
            )
