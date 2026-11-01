# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    custody_account_id = fields.Many2one(
        'account.account',
        string='Custody Account',
        domain="[('account_type', 'in', ('liability_payable', 'asset_receivable'))]",
        help='Custody account (Custody Payable), of type Payable or Receivable, on which driver custodies are recorded.',
    )
    custody_journal_id = fields.Many2one(
        'account.journal',
        string='Custody Journal',
        domain="[('type', '=', 'general')]",
        help='Journal in which custody entries are created.',
    )
