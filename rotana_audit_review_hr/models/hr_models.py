# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.rotana_audit_review.models.audit_review_mixin import AUDIT_MODELS

HR_AUDIT_MODELS = [
    'hr.employee',
    'hr.version',
    'hr.payslip',
    'hr.payslip.run',
    'hr.leave',
    'hr.leave.allocation',
    'hr.expense',
    'hr.attendance',
    'hr.department',
    'hr.job',
    'hr.appraisal',
]

# تسجيل موديلات HR ضمن نطاق المراجعة (القائمة مشتركة مع المديول الأساسي)
for _model in HR_AUDIT_MODELS:
    if _model not in AUDIT_MODELS:
        AUDIT_MODELS.append(_model)


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'audit.review.mixin']


class HrVersion(models.Model):
    _name = 'hr.version'
    _inherit = ['hr.version', 'audit.review.mixin']


class HrDepartment(models.Model):
    _name = 'hr.department'
    _inherit = ['hr.department', 'audit.review.mixin']


class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = ['hr.job', 'audit.review.mixin']


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'audit.review.mixin']

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', 'audit.review.mixin']

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrLeave(models.Model):
    _name = 'hr.leave'
    _inherit = ['hr.leave', 'audit.review.mixin']

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrLeaveAllocation(models.Model):
    _name = 'hr.leave.allocation'
    _inherit = ['hr.leave.allocation', 'audit.review.mixin']

    def _audit_companies(self):
        self.ensure_one()
        return self.employee_id.company_id or self.env.companies

    def _audit_enabled_domain(self):
        return [('employee_id.company_id.restrictive_audit_trail', '=', True)]

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrExpense(models.Model):
    _name = 'hr.expense'
    _inherit = ['hr.expense', 'audit.review.mixin']

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrAppraisal(models.Model):
    _name = 'hr.appraisal'
    _inherit = ['hr.appraisal', 'audit.review.mixin']

    def _audit_reset_ignored_fields(self):
        return {'state'}


class HrAttendance(models.Model):
    _name = 'hr.attendance'
    # الحضور لا يرث mail.activity.mixin افتراضياً، نضيفه لدعم المهام
    _inherit = ['hr.attendance', 'mail.activity.mixin', 'audit.review.mixin']

    def _audit_companies(self):
        self.ensure_one()
        return self.employee_id.company_id or self.env.companies

    def _audit_enabled_domain(self):
        return [('employee_id.company_id.restrictive_audit_trail', '=', True)]
