# -*- coding: utf-8 -*-
"""نموذج مركبات النقل لشركة روتانا.

يُدير بيانات المركبات المستخدمة في خدمات النقل،
بما في ذلك الموقع الحالي للمركبة الذي يُحدَّث تلقائياً
عند اكتمال الرحلة.
"""
from odoo import _, api, fields, models


class RotanaTransportVehicle(models.Model):
    _name = 'rotana.transport.vehicle'
    _description = 'مركبة النقل'
    _order = 'name'
    _rec_names_search = ['name', 'license_plate']

    name = fields.Char(
        string='اسم المركبة',
        required=True,
        index=True,
    )

    license_plate = fields.Char(
        string='رقم اللوحة',
        required=True,
        index=True,
    )

    vehicle_type = fields.Selection(
        selection=[
            ('truck', 'شاحنة'),
            ('trailer', 'مقطورة'),
            ('van', 'فان'),
            ('pickup', 'بيك أب'),
            ('bus', 'حافلة'),
            ('other', 'أخرى'),
        ],
        string='نوع المركبة',
        default='truck',
        required=True,
    )

    current_location_id = fields.Many2one(
        'rotana.transport.location',
        string='الموقع الحالي',
        index=True,
        help='الموقع الحالي للمركبة. يُحدَّث تلقائياً عند اكتمال الرحلة.',
    )

    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='مركبة الأسطول',
        index=True,
        help='الربط مع مديول الأسطول إذا كان مُفعَّلاً.',
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='الحساب التحليلي',
        index=True,
        help='الحساب التحليلي الخاص بهذه المركبة للتتبع المالي.',
    )

    capacity_kg = fields.Float(string='الطاقة الاستيعابية (كغ)')

    notes = fields.Text(string='ملاحظات')

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    _license_plate_company_unique = models.Constraint(
        'UNIQUE(license_plate, company_id)',
        'رقم لوحة المركبة يجب أن يكون فريداً لكل شركة.',
    )

    @api.depends('name', 'license_plate')
    def _compute_display_name(self):
        for vehicle in self:
            vehicle.display_name = (
                f'[{vehicle.license_plate}] {vehicle.name}'
                if vehicle.license_plate else vehicle.name
            )
