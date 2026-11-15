# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RotanaMaintenanceExpense(models.Model):
    _name = 'rotana.maintenance.expense'
    _description = 'Maintenance Expense'
    _order = 'id'

    request_id = fields.Many2one(
        'rotana.maintenance.request', string='Maintenance Request',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Vendor')
    account_id = fields.Many2one(
        'account.account', string='Expense Account',
        compute='_compute_account_id', store=True, readonly=False, precompute=True,
        help='Debit account of the bill line. Default: the spare parts expense account of the company settings.',
    )
    name = fields.Char(string='Description', required=True)
    amount = fields.Monetary(string='Amount', required=True)
    # The bill created for this line: its presence means the line is invoiced and is never invoiced again
    move_id = fields.Many2one(
        'account.move', string='Bill', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null',
        groups='account.group_account_invoice',
    )
    is_invoiced = fields.Boolean(string='Invoiced', compute='_compute_is_invoiced')

    @api.depends('request_id.company_id')
    def _compute_account_id(self):
        for expense in self:
            if not expense.account_id:
                expense.account_id = expense.request_id.company_id.maintenance_expense_account_id

    def _compute_is_invoiced(self):
        for expense in self:
            expense.is_invoiced = bool(expense.sudo().move_id)

    def write(self, vals):
        if set(vals) - {'move_id'} and any(e.sudo().move_id for e in self):
            raise UserError(_('An expense that already has a bill cannot be modified.'))
        return super().write(vals)

    def unlink(self):
        if any(e.sudo().move_id for e in self):
            raise UserError(_('An expense that already has a bill cannot be deleted.'))
        return super().unlink()
