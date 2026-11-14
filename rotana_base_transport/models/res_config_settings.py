# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    parent_analytic_plan_id = fields.Many2one(
        related='company_id.parent_analytic_plan_id', readonly=False)
    allowable_deficit = fields.Float(
        related='company_id.allowable_deficit', readonly=False)
    custody_account_id = fields.Many2one(
        related='company_id.custody_account_id', readonly=False)
    custody_journal_id = fields.Many2one(
        related='company_id.custody_journal_id', readonly=False)
