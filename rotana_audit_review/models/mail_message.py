# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from .audit_review_mixin import AUDIT_MODELS, REVIEW_STATES


class MailMessage(models.Model):
    _inherit = 'mail.message'

    audit_review_state = fields.Selection(
        REVIEW_STATES, string='حالة المراجعة',
        compute='_compute_audit_review', search='_search_audit_review_state')
    audit_reviewer_id = fields.Many2one(
        'res.users', string='المراجع', compute='_compute_audit_review')
    audit_review_date = fields.Datetime(string='تاريخ المراجعة', compute='_compute_audit_review')
    audit_review_note = fields.Text(string='ملاحظة المراجعة', compute='_compute_audit_review')

    # ------------------------------------------------------------------
    # حقول العرض في شاشة Audit Trail
    # ------------------------------------------------------------------
    @api.depends('model', 'res_id')
    def _compute_audit_review(self):
        by_model = defaultdict(set)
        for msg in self:
            if msg.model in AUDIT_MODELS and msg.res_id:
                by_model[msg.model].add(msg.res_id)
        records = {}
        for model, ids in by_model.items():
            for rec in self.env[model].sudo().with_context(active_test=False).browse(ids).exists():
                if rec.audit_trail_enabled:
                    records[(model, rec.id)] = rec
        for msg in self:
            rec = records.get((msg.model, msg.res_id))
            msg.audit_review_state = rec.audit_review_state if rec else False
            msg.audit_reviewer_id = rec.audit_reviewer_id if rec else False
            msg.audit_review_date = rec.audit_review_date if rec else False
            msg.audit_review_note = rec.audit_review_note if rec else False

    def _search_audit_review_state(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            return NotImplemented
        domains = []
        for model in AUDIT_MODELS:
            records = self.env[model].sudo().with_context(active_test=False)
            query = records._search(
                Domain('audit_review_state', operator, value) & Domain(records._audit_enabled_domain()))
            domains.append(Domain('model', '=', model) & Domain('res_id', 'in', query))
        return Domain('message_type', '=', 'notification') & Domain.OR(domains)

    # ------------------------------------------------------------------
    # أزرار قائمة Audit Trail
    # ------------------------------------------------------------------
    def _audit_targets(self):
        targets = defaultdict(set)
        for msg in self.sudo():
            if msg.model in AUDIT_MODELS and msg.res_id:
                targets[msg.model].add(msg.res_id)
        if not targets:
            raise UserError('حدد سطراً واحداً على الأقل من سجل المراجعة.')
        return {model: sorted(ids) for model, ids in targets.items()}

    def action_audit_mark_reviewed(self):
        return self.env['audit.review.wizard']._open('reviewed', self._audit_targets())

    def action_audit_mark_rejected(self):
        return self.env['audit.review.wizard']._open('rejected', self._audit_targets())

    def action_audit_add_task(self):
        return self.env['audit.review.wizard']._open('task', self._audit_targets())

    # ------------------------------------------------------------------
    # إعادة الحالة إلى "بانتظار المراجعة" عند أي تعديل مسجَّل بعد المراجعة
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        messages._audit_reset_reviews()
        return messages

    def _audit_reset_reviews(self):
        if self.env.context.get('audit_review_no_reset'):
            return
        todo = defaultdict(set)
        for msg in self.sudo():
            if (msg.model in AUDIT_MODELS and msg.res_id
                    and msg.message_type == 'notification' and msg.tracking_value_ids):
                todo[msg.model].add(msg.res_id)
        for model, ids in todo.items():
            records = self.env[model].sudo().with_context(active_test=False).browse(ids).exists()
            records = records.filtered(
                lambda r: r.audit_trail_enabled and r.audit_review_state != 'pending')
            if records:
                records._audit_set_state('pending', reset=True)
