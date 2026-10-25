# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import api, fields, models


class PurchaseRequestLine(models.Model):
    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    description = fields.Char(string="Description", tracking=True)
    product_qty = fields.Float(string="Quantity", tracking=True, digits="Product Unit")
    request_id = fields.Many2one(
        comodel_name="purchase.request",
        string="Purchase Request",
        ondelete="cascade",
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="request_id.company_id",
        string="Company",
        store=True,
        index=True,
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        related="request_id.requested_by",
        string="Requested by",
        store=True,
    )
    assigned_to = fields.Many2one(
        comodel_name="res.users",
        related="request_id.assigned_to",
        string="Assigned to",
        store=True,
    )
    date_start = fields.Date(related="request_id.date_start", store=True)
    origin = fields.Char(
        related="request_id.origin", string="Source Document", store=True
    )
    date_required = fields.Date(
        string="Request Date",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        tracking=True,
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_price_subtotal",
        store=True,
    )
    cancelled = fields.Boolean(readonly=True, default=False, copy=False)

    @api.depends("product_qty", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    def do_cancel(self):
        """Actions to perform when cancelling a purchase request line."""
        self.write({"cancelled": True})

    def do_uncancel(self):
        """Actions to perform when uncancelling a purchase request line."""
        self.write({"cancelled": False})

    def write(self, vals):
        res = super().write(vals)
        if vals.get("cancelled"):
            requests = self.mapped("request_id")
            requests.check_auto_reject()
        return res
