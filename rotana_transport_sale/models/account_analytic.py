from odoo import _, api, fields, models

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        index=True,
        help='Sales order linked to this analytic account.',
    )