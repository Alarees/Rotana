# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.addons.rotana_audit_review.models.audit_review_mixin import audit_models

from .hr_models import HR_AUDIT_MODELS


def _company_domain(path):
    return lambda operator, value: [(path + '.restrictive_audit_trail', operator, value)]


# شروط "Audit Trail مفعّل" لكل موديل HR (مثل DOMAINS القياسي في account)
HR_DOMAINS = {model: _company_domain('company_id') for model in HR_AUDIT_MODELS}
HR_DOMAINS['hr.attendance'] = _company_domain('employee_id.company_id')
HR_DOMAINS['hr.leave.allocation'] = _company_domain('employee_id.company_id')


class MailMessage(models.Model):
    _inherit = 'mail.message'

    audit_model_name = fields.Char(string='نوع السجل', compute='_compute_audit_record')
    audit_record_name = fields.Char(string='السجل', compute='_compute_audit_record')

    @api.depends('model', 'res_id')
    def _compute_audit_record(self):
        audit = audit_models(self.env)
        by_model = defaultdict(set)
        for msg in self:
            if msg.model in audit and msg.res_id:
                by_model[msg.model].add(msg.res_id)
        kinds, names = {}, {}
        for model, ids in by_model.items():
            kinds[model] = self.env['ir.model']._get(model).name
            records = self.env[model].sudo().with_context(active_test=False).browse(ids).exists()
            for rec in records:
                names[(model, rec.id)] = rec.display_name
        for msg in self:
            msg.audit_model_name = kinds.get(msg.model) or False
            msg.audit_record_name = names.get((msg.model, msg.res_id)) or False

    # ------------------------------------------------------------------
    # حماية السجل (Restricted Audit Trail) لموديلات HR
    # القياسي يغطي 5 موديلات فقط، فنوسّعه دون تعديل قاموس account العام
    # ------------------------------------------------------------------
    def _search_account_audit_log_restricted(self, operator, value):
        domain = super()._search_account_audit_log_restricted(operator, value)
        if domain is NotImplemented:
            return domain
        extra = [
            Domain('model', '=', model)
            & Domain('res_id', 'in', self.env[model].sudo()._search(factory(operator, value)))
            for model, factory in HR_DOMAINS.items() if model in self.env
        ]
        if not extra:
            return domain
        return Domain(domain) | (Domain('message_type', '=', 'notification') & Domain.OR(extra))

    def _compute_account_audit_log_restricted(self):
        super()._compute_account_audit_log_restricted()
        hr_messages = self.filtered(lambda m: m.model in HR_DOMAINS and m.model in self.env)
        if hr_messages:
            restricted = self.sudo().search(
                Domain('id', 'in', hr_messages.ids)
                & self._search_account_audit_log_restricted('in', [True]))
            restricted.account_audit_log_restricted = True
