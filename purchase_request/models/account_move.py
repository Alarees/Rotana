# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    purchase_request_id = fields.Many2one(
        comodel_name="purchase.request",
        string="Purchase Request",
        copy=False,
        readonly=True,
        index="btree_not_null",
        ondelete="set null",
    )
