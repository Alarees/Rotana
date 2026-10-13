# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    custody_account_id = fields.Many2one(
        'account.account',
        string='حساب العهد',
        domain="[('account_type', '=', 'asset_receivable')]",
        help='حساب من نوع (مدينة) تُقيَّد عليه عهد السائقين.',
    )
    custody_journal_id = fields.Many2one(
        'account.journal',
        string='دفتر يومية العهد',
        domain="[('type', '=', 'general')]",
        help='دفتر اليومية الذي تُنشأ فيه قيود العهد.',
    )
