# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import html_escape

# الموديلات التي يسجّلها Audit Trail القياسي في أودو
AUDIT_MODELS = ['account.move', 'account.account', 'account.tax', 'res.partner', 'res.company']

REVIEW_STATES = [
    ('pending', 'بانتظار المراجعة'),
    ('reviewed', 'تمت المراجعة'),
    ('rejected', 'مرفوضة'),
]

AUDIT_FIELDS = {'audit_review_state', 'audit_reviewer_id', 'audit_review_date', 'audit_review_note'}


class AuditReviewMixin(models.AbstractModel):
    _name = 'audit.review.mixin'
    _description = 'Audit Trail Review Mixin'

    audit_review_state = fields.Selection(
        REVIEW_STATES, string='حالة المراجعة', default='pending',
        copy=False, readonly=True, index=True)
    audit_reviewer_id = fields.Many2one('res.users', string='المراجع', copy=False, readonly=True)
    audit_review_date = fields.Datetime(string='تاريخ المراجعة', copy=False, readonly=True)
    audit_review_note = fields.Text(string='ملاحظة المراجعة / سبب الرفض', copy=False, readonly=True)
    audit_trail_enabled = fields.Boolean(
        string='Audit Trail مفعّل', compute='_compute_audit_trail_enabled')

    # ------------------------------------------------------------------
    # ربط الحالة بإعداد الشركة (restrictive_audit_trail)
    # ------------------------------------------------------------------
    def _audit_companies(self):
        """الشركات التي يحدد إعدادها تفعيل Audit Trail لهذا السجل."""
        self.ensure_one()
        if 'company_id' in self._fields and self.company_id:
            return self.company_id
        return self.env.companies

    @api.depends_context('allowed_company_ids')
    def _compute_audit_trail_enabled(self):
        for rec in self:
            companies = rec.sudo()._audit_companies()
            rec.audit_trail_enabled = any(companies.mapped('restrictive_audit_trail'))

    def _audit_enabled_domain(self):
        """Domain للسجلات التي يكون Audit Trail مفعلاً لها (للاستخدام في البحث)."""
        any_enabled = any(self.env.companies.mapped('restrictive_audit_trail'))
        if 'company_id' in self._fields:
            domain = [('company_id.restrictive_audit_trail', '=', True)]
            if any_enabled:
                domain = ['|', ('company_id', '=', False)] + domain
            return domain
        return [(1, '=', 1)] if any_enabled else [(0, '=', 1)]

    # ------------------------------------------------------------------
    # حماية حقول المراجعة من الكتابة المباشرة
    # ------------------------------------------------------------------
    def write(self, vals):
        if AUDIT_FIELDS & set(vals) and not self.env.su:
            raise AccessError('لا يمكن تعديل حالة المراجعة مباشرة، استخدم أزرار المراجعة.')
        return super().write(vals)

    # ------------------------------------------------------------------
    # تغيير الحالة
    # ------------------------------------------------------------------
    def _audit_set_state(self, state, note=False, reset=False):
        labels = dict(REVIEW_STATES)
        user = self.env.user
        for rec in self:
            vals = {
                'audit_review_state': state,
                'audit_review_note': note or False,
                'audit_reviewer_id': False if reset else user.id,
                'audit_review_date': False if reset else fields.Datetime.now(),
            }
            rec = rec.sudo().with_context(audit_review_no_reset=True, tracking_disable=True)
            rec.write(vals)
            if reset:
                body = Markup('أُعيدت حالة المراجعة إلى «بانتظار المراجعة» بسبب تعديل بعد المراجعة.')
            else:
                body = Markup('حالة المراجعة: <b>%s</b> — بواسطة %s') % (labels[state], user.name)
                if note:
                    body += Markup('<br/>الملاحظة: %s') % html_escape(note)
            rec.message_post(body=body, message_type='notification', subtype_xmlid='mail.mt_note')

    # ------------------------------------------------------------------
    # أزرار الشاشة (تفتح المعالج)
    # ------------------------------------------------------------------
    def action_audit_mark_reviewed(self):
        return self.env['audit.review.wizard']._open('reviewed', {self._name: self.ids})

    def action_audit_mark_rejected(self):
        return self.env['audit.review.wizard']._open('rejected', {self._name: self.ids})

    def action_audit_add_task(self):
        return self.env['audit.review.wizard']._open('task', {self._name: self.ids})
