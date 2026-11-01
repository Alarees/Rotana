# -*- coding: utf-8 -*-
"""نموذج سائقي النقل لشركة روتانا."""
from odoo import _, api, fields, models


class RotanaTransportDriver(models.Model):
    _name = 'rotana.transport.driver'
    _description = 'Transport Driver'
    _order = 'name'
    _rec_names_search = ['name', 'license_number']

    name = fields.Char(
        string='Driver Name',
        required=True,
        index=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        index=True,
    )

    license_number = fields.Char(
        string='Driving License Number',
        index=True,
    )

    license_expiry_date = fields.Date(
        string='License Expiry Date',
    )

    phone = fields.Char(string='Phone Number')

    is_license_expired = fields.Boolean(
        string='License Expired',
        compute='_compute_is_license_expired',
        store=True,
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

    @api.depends('license_expiry_date')
    def _compute_is_license_expired(self):
        for driver in self:
            driver.is_license_expired = bool(
                driver.license_expiry_date
                and driver.license_expiry_date < fields.Date.context_today(driver)
            )
