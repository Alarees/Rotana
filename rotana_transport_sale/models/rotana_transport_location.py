# -*- coding: utf-8 -*-
"""نموذج مواقع النقل.

يُستخدم لتحديد نقاط الانطلاق والوصول في رحلات النقل،
ويُربط بالعملاء لتسهيل اختيار المواقع في أوامر البيع.
"""
from odoo import _, fields, models


class RotanaTransportLocation(models.Model):
    _name = 'rotana.transport.location'
    _description = 'Transport Location'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Location Name',
        required=True,
        index=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer / Partner',
        index=True,
        help='Customer or partner linked to this location.',
    )

    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    state_id = fields.Many2one(
        'res.country.state',
        string='State / Province',
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
    )

    notes = fields.Text(string='Notes')

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    @property
    def _rec_names_search(self):
        return ['name', 'city']
