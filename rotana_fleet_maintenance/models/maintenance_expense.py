# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaintenanceRequestExpense(models.Model):
    _name = 'maintenance.request.expense'
    _description = 'منصرف أثناء الصيانة'
    _order = 'id'

    request_id = fields.Many2one(
        'maintenance.request', string='طلب الصيانة',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='المورد')
    account_id = fields.Many2one(
        'account.account', string='حساب المصروف',
        compute='_compute_account_id', store=True, readonly=False, precompute=True,
        help='الحساب المدين لسطر الفاتورة. الافتراضي: حساب مصروف قطع الغيار في إعدادات الشركة.',
    )
    name = fields.Char(string='الوصف', required=True)
    amount = fields.Monetary(string='المبلغ', required=True)
    # الفاتورة التي أُنشئت لهذا السطر: وجودها يعني أنه فُوتِر ولا يُفوتَر مرة أخرى
    move_id = fields.Many2one(
        'account.move', string='الفاتورة', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null',
        groups='account.group_account_invoice',
    )
    is_invoiced = fields.Boolean(string='تمت الفوترة', compute='_compute_is_invoiced')

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
            raise UserError(_('لا يمكن تعديل منصرف تم إنشاء فاتورة له.'))
        return super().write(vals)

    def unlink(self):
        if any(e.sudo().move_id for e in self):
            raise UserError(_('لا يمكن حذف منصرف تم إنشاء فاتورة له.'))
        return super().unlink()
