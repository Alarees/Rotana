# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.audit_review_mixin import audit_models

GROUP = 'rotana_audit_review.group_audit_reviewer'


class AuditReviewWizard(models.TransientModel):
    _name = 'audit.review.wizard'
    _description = 'معالج مراجعة Audit Trail'

    action_type = fields.Selection(
        [('reviewed', 'تمت المراجعة'), ('rejected', 'رفض'), ('task', 'إضافة مهمة')],
        required=True)
    targets = fields.Char(help='JSON: {model: [ids]}')
    targets_count = fields.Integer(string='عدد السجلات', compute='_compute_targets_count')
    note = fields.Text(string='الملاحظة / سبب الرفض')
    # بيانات المهمة
    activity_type_id = fields.Many2one(
        'mail.activity.type', string='نوع المهمة',
        default=lambda self: self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False))
    summary = fields.Char(string='ملخص المهمة')
    date_deadline = fields.Date(
        string='تاريخ الاستحقاق',
        default=lambda self: fields.Date.context_today(self) + timedelta(days=3))
    user_id = fields.Many2one('res.users', string='المكلّف', default=lambda self: self.env.user)
    activity_note = fields.Text(string='تفاصيل المهمة')

    @api.model
    def _open(self, action_type, targets):
        names = {'reviewed': 'تمت المراجعة', 'rejected': 'رفض المعاملة', 'task': 'إضافة مهمة'}
        return {
            'type': 'ir.actions.act_window',
            'name': names[action_type],
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_action_type': action_type,
                'default_targets': json.dumps(targets),
            },
        }

    @api.depends('targets')
    def _compute_targets_count(self):
        for wiz in self:
            data = json.loads(wiz.targets or '{}')
            wiz.targets_count = sum(len(ids) for ids in data.values())

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(GROUP):
            raise AccessError('هذه العملية متاحة لمجموعة «مراجع داخلي» فقط.')
        if self.action_type == 'rejected' and not (self.note or '').strip():
            raise UserError('سبب الرفض إلزامي.')
        data = json.loads(self.targets or '{}')
        done = 0
        for model, ids in data.items():
            if model not in audit_models(self.env):
                continue
            # search بدل browse لتطبيق قواعد الصلاحيات وتعدد الشركات
            records = self.env[model].with_context(active_test=False).search([('id', 'in', ids)])
            records = records.filtered('audit_trail_enabled')
            if not records:
                continue
            if self.action_type == 'task':
                records.sudo().activity_schedule(
                    activity_type_id=self.activity_type_id.id,
                    summary=self.summary,
                    note=self.activity_note or '',
                    date_deadline=self.date_deadline,
                    user_id=self.user_id.id,
                )
            else:
                records._audit_set_state(self.action_type, self.note)
            done += len(records)
        if not done:
            raise UserError('لا توجد سجلات مفعّل لها Audit Trail في إعدادات الشركة.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'المراجعة',
                'message': 'تم التنفيذ على %s سجل.' % done,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
