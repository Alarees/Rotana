from odoo import _, api, fields, models

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='أمر البيع',
        index=True,
        help='أمر البيع المرتبط بهذا الحساب التحليلي.',
    )