# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    parent_analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='Parent Analytic Plan',
        help='The parent analytic plan for transport vehicles. Each vehicle gets its own '
             'analytic plan under it, and fleet maintenance posts its costs on the vehicle '
             'accounts under this same plan.',
    )
    allowable_deficit = fields.Float(
        string='Default Allowable Deficit (Kg)',
        help='The default allowable deficit for transported weight.',
        default=0.0,
    )
    custody_account_id = fields.Many2one(
        'account.account',
        string='Custody Account',
        domain="[('account_type', 'in', ('liability_payable', 'asset_receivable'))]",
        help='Custody account (Custody Payable), of type Payable or Receivable, '
             'on which driver custodies are recorded.',
    )
    custody_journal_id = fields.Many2one(
        'account.journal',
        string='Custody Journal',
        domain="[('type', '=', 'general')]",
        help='Journal in which custody entries are created.',
    )
