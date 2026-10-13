# -*- coding: utf-8 -*-
"""نموذج مواقع النقل.

يُستخدم لتحديد نقاط الانطلاق والوصول في رحلات النقل،
ويُربط بالعملاء لتسهيل اختيار المواقع في أوامر البيع.
"""
from odoo import _, fields, models


class RotanaTransportLocation(models.Model):
    _name = 'rotana.transport.location'
    _description = 'موقع النقل'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='اسم الموقع',
        required=True,
        index=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='العميل / الشريك',
        index=True,
        help='العميل أو الشريك المرتبط بهذا الموقع.',
    )

    street = fields.Char(string='الشارع')
    city = fields.Char(string='المدينة')
    state_id = fields.Many2one(
        'res.country.state',
        string='المنطقة / المحافظة',
    )
    country_id = fields.Many2one(
        'res.country',
        string='الدولة',
    )

    notes = fields.Text(string='ملاحظات')

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    @property
    def _rec_names_search(self):
        return ['name', 'city']
