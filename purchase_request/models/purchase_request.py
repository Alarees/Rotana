# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

_STATES = [
    ("draft", "Draft"),
    ("dept_manager", "Department Manager"),
    ("accounts_head", "Head of Accounts"),
    ("internal_audit", "Internal Auditor"),
    ("general_manager", "General Manager"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

# Approval chain, in order: (state, xml id of the group allowed to approve).
_APPROVAL_CHAIN = [
    ("dept_manager", "group_pr_dept_manager"),
    ("accounts_head", "group_pr_accounts_head"),
    ("internal_audit", "group_pr_internal_auditor"),
    ("general_manager", "group_pr_general_manager"),
]
_PENDING_STATES = [state for state, _group in _APPROVAL_CHAIN]


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _mail_post_access = "read"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    @api.model
    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)

    @api.model
    def _get_default_name(self):
        return self.env["ir.sequence"].next_by_code("purchase.request")

    @api.depends("state")
    def _compute_is_editable(self):
        for rec in self:
            rec.is_editable = rec.state == "draft"

    name = fields.Char(
        string="Request Reference",
        required=True,
        default=lambda self: self.env._("New"),
        tracking=True,
    )
    date_start = fields.Date(
        string="Creation date",
        help="Date when the user initiated the request.",
        default=fields.Date.context_today,
        tracking=True,
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        required=True,
        copy=False,
        tracking=True,
        default=lambda self: self._get_default_requested_by(),
        index=True,
    )
    description = fields.Text()
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        tracking=True,
        index=True,
        help="Vendor used when creating the vendor bill of this request.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=lambda self: self._company_get(),
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name="purchase.request.line",
        inverse_name="request_id",
        string="Products to Purchase",
        readonly=False,
        copy=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        copy=False,
        default="draft",
    )
    dept_manager_user_id = fields.Many2one(
        "res.users", string="Approved by", readonly=True, copy=False, tracking=True
    )
    dept_manager_date = fields.Datetime(
        string="Approval Date", readonly=True, copy=False
    )
    accounts_head_user_id = fields.Many2one(
        "res.users", string="Approved by", readonly=True, copy=False, tracking=True
    )
    accounts_head_date = fields.Datetime(
        string="Approval Date", readonly=True, copy=False
    )
    internal_audit_user_id = fields.Many2one(
        "res.users", string="Approved by", readonly=True, copy=False, tracking=True
    )
    internal_audit_date = fields.Datetime(
        string="Approval Date", readonly=True, copy=False
    )
    general_manager_user_id = fields.Many2one(
        "res.users", string="Approved by", readonly=True, copy=False, tracking=True
    )
    general_manager_date = fields.Datetime(
        string="Approval Date", readonly=True, copy=False
    )
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    to_approve_allowed = fields.Boolean(compute="_compute_to_approve_allowed")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=True,
    )
    invoice_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="purchase_request_id",
        string="Vendor Bills",
        readonly=True,
        copy=False,
    )
    bill_count = fields.Integer(string="Vendor Bills", compute="_compute_bill_count")

    @api.depends("line_ids.price_subtotal", "line_ids.cancelled")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(
                rec.line_ids.filtered(lambda line: not line.cancelled).mapped(
                    "price_subtotal"
                )
            )

    def _get_active_bills(self):
        """Vendor bills of the request that are not cancelled (sudo: the
        request users do not necessarily have accounting access rights)."""
        self.ensure_one()
        return self.sudo().invoice_ids.filtered(lambda move: move.state != "cancel")

    @api.depends("invoice_ids.state")
    def _compute_bill_count(self):
        for rec in self:
            rec.bill_count = len(rec._get_active_bills())

    @api.depends("state", "line_ids.product_qty", "line_ids.cancelled")
    def _compute_to_approve_allowed(self):
        for rec in self:
            rec.to_approve_allowed = rec.state == "draft" and any(
                not line.cancelled and line.product_qty for line in rec.line_ids
            )

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({"state": "draft", "name": self._get_default_name()})
        return super().copy(default)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                vals["name"] = self._get_default_name()
        return super().create(vals_list)

    def _can_be_deleted(self):
        self.ensure_one()
        return self.state == "draft"

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        for request in self:
            if not request._can_be_deleted():
                raise UserError(
                    self.env._(
                        "You cannot delete a purchase request which is not draft."
                    )
                )

    def _clear_approvals(self):
        vals = {}
        for state, _group in _APPROVAL_CHAIN:
            vals[f"{state}_user_id"] = False
            vals[f"{state}_date"] = False
        return vals

    def button_draft(self):
        self.mapped("line_ids").do_uncancel()
        return self.write({"state": "draft", **self._clear_approvals()})

    def button_to_approve(self):
        self.to_approve_allowed_check()
        return self.write({"state": _PENDING_STATES[0]})

    def _approve_stage(self, stage):
        """Record the current user and time for ``stage`` and move the request
        to the next stage (or to ``approved`` after the last one)."""
        stages = _PENDING_STATES
        group = dict(_APPROVAL_CHAIN)[stage]
        if not self.env.user.has_group(f"purchase_request.{group}"):
            raise UserError(
                self.env._("You are not allowed to approve at this stage.")
            )
        for rec in self:
            if rec.state != stage:
                raise UserError(
                    self.env._(
                        "The request %(name)s is not waiting for this approval.",
                        name=rec.name,
                    )
                )
            index = stages.index(stage)
            next_state = stages[index + 1] if index + 1 < len(stages) else "approved"
            rec.write(
                {
                    f"{stage}_user_id": self.env.uid,
                    f"{stage}_date": fields.Datetime.now(),
                    "state": next_state,
                }
            )
        return True

    def button_approve_dept_manager(self):
        return self._approve_stage("dept_manager")

    def button_approve_accounts_head(self):
        return self._approve_stage("accounts_head")

    def button_approve_internal_audit(self):
        return self._approve_stage("internal_audit")

    def button_approve_general_manager(self):
        return self._approve_stage("general_manager")

    def button_rejected(self):
        if not any(
            self.env.user.has_group(f"purchase_request.{group}")
            for _state, group in _APPROVAL_CHAIN
        ):
            raise UserError(self.env._("You are not allowed to reject requests."))
        self.mapped("line_ids").do_cancel()
        return self.write({"state": "rejected"})

    def check_auto_reject(self):
        """When all lines are cancelled the purchase request should be
        auto-rejected."""
        for pr in self:
            if not pr.line_ids.filtered(lambda line: line.cancelled is False):
                pr.write({"state": "rejected"})

    def to_approve_allowed_check(self):
        for rec in self:
            if not rec.to_approve_allowed:
                raise UserError(
                    self.env._(
                        "You can't request an approval for a purchase request "
                        "which is empty. (%(name)s)",
                        name=rec.name,
                    )
                )

    def _prepare_vendor_bill_line_vals(self, line):
        self.ensure_one()
        return {
            "name": line.description or self.name,
            "quantity": line.product_qty,
            "price_unit": line.price_unit,
            "analytic_distribution": line.analytic_distribution or False,
        }

    def _prepare_vendor_bill_vals(self, lines):
        self.ensure_one()
        return {
            "move_type": "in_invoice",
            "partner_id": self.vendor_id.id,
            "invoice_origin": self.name,
            "purchase_request_id": self.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": [
                Command.create(self._prepare_vendor_bill_line_vals(line))
                for line in lines
            ],
        }

    def action_create_vendor_bill(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(
                self.env._(
                    "You can only create a vendor bill for an approved "
                    "purchase request. (%(name)s)",
                    name=self.name,
                )
            )
        if self._get_active_bills():
            raise UserError(
                self.env._(
                    "A vendor bill already exists for this purchase request. "
                    "(%(name)s)",
                    name=self.name,
                )
            )
        lines = self.line_ids.filtered(
            lambda line: not line.cancelled and line.product_qty
        )
        if not lines:
            raise UserError(
                self.env._(
                    "There are no lines to bill in this purchase request. (%(name)s)",
                    name=self.name,
                )
            )
        move_model = self.env["account.move"].with_company(
            self.company_id or self.env.company
        )
        bill = move_model.with_context(default_move_type="in_invoice").create(
            self._prepare_vendor_bill_vals(lines)
        )
        self.message_post(
            body=self.env._("A vendor bill was created from this request.")
        )
        return self.action_view_vendor_bills(bill)

    def action_view_vendor_bills(self, bills=None):
        self.ensure_one()
        bills = bills or self.sudo().invoice_ids
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        if len(bills) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = bills.id
        else:
            action["domain"] = [("id", "in", bills.ids)]
        return action
