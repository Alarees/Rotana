# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    custody_id = fields.Many2one(
        'rotana.transport.trip.custody',
        string='عهدة النقل',
        copy=False,
        index=True,
        ondelete='set null',
    )
    is_custody_settlement = fields.Boolean(
        string='دفعية تسوية عهدة',
        copy=False,
    )

    @api.depends(
        'journal_id', 'partner_id', 'partner_type',
        'is_custody_settlement', 'company_id',
    )
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        # دفعية فرق التصفية تُقيَّد على حساب العهدة بدلاً من ذمم الشريك
        for pay in self.filtered('is_custody_settlement'):
            account = pay.company_id.custody_account_id
            if account:
                pay.destination_account_id = account

    def action_post(self):
        res = super().action_post()
        custodies = self.filtered('is_custody_settlement').custody_id.sudo()
        custodies._reconcile_custody_lines()
        return res


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    @api.model_create_multi
    def create(self, vals_list):
        partials = super().create(vals_list)
        moves = (partials.debit_move_id | partials.credit_move_id).move_id
        custodies = self.env['rotana.transport.trip.custody'].sudo().search([
            ('confirm_move_id', 'in', moves.ids),
            ('state', 'in', ('confirmed', 'paid')),
        ])
        custodies._update_advance_payment()
        return partials
