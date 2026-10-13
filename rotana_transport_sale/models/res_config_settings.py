from odoo import _, api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    parent_analytic_plan_id = fields.Many2one(
        comodel_name='account.analytic.plan',
        string="Parent Analytic Plan",
        config_parameter='rotana_transport_sale.parent_analytic_plan_id',
        help="The parent analytic plan for transport vehicles.",
    )

    allowable_deficit = fields.Float(
        string='Default Allowable Deficit (Kg)',
        config_parameter='rotana_transport_sale.allowable_deficit',
        help='The default allowable deficit percentage for transported weight.',
        default=0.0,
    )

    custody_account_id = fields.Many2one(
        related='company_id.custody_account_id',
        readonly=False,
        domain="[('account_type', '=', 'asset_receivable')]",
    )
    custody_journal_id = fields.Many2one(
        related='company_id.custody_journal_id',
        readonly=False,
        domain="[('type', '=', 'general')]",
    )
