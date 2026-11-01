# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    custody_id = fields.Many2one(
        'rotana.transport.trip.custody',
        string='Transport Custody',
        copy=False,
        index=True,
        ondelete='set null',
    )
    custody_payment_kind = fields.Selection(
        [
            ('advance', 'Custody Payment'),
            ('settlement', 'Custody Difference Settlement'),
        ],
        string='Custody Payment Type',
        copy=False,
    )

    @api.depends(
        'journal_id', 'partner_id', 'partner_type',
        'custody_payment_kind', 'company_id',
    )
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        # دفعات العهد تُقيَّد على حساب العهدة بدلاً من ذمم الشريك الافتراضية
        for pay in self.filtered('custody_payment_kind'):
            account = pay.company_id.custody_account_id
            if account:
                pay.destination_account_id = account

    def action_post(self):
        res = super().action_post()
        custodies = self.filtered('custody_payment_kind').custody_id.sudo()
        custodies._after_payment_posted()
        return res
