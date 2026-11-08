# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'audit.review.mixin']


class AccountAccount(models.Model):
    _name = 'account.account'
    _inherit = ['account.account', 'audit.review.mixin']

    def _audit_companies(self):
        self.ensure_one()
        return self.company_ids or self.env.companies

    def _audit_enabled_domain(self):
        return [('company_ids.restrictive_audit_trail', '=', True)]


class AccountTax(models.Model):
    _name = 'account.tax'
    # الضريبة لا ترث mail.activity.mixin افتراضياً، نضيفه لدعم المهام
    _inherit = ['account.tax', 'mail.activity.mixin', 'audit.review.mixin']


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'audit.review.mixin']


class ResCompany(models.Model):
    _name = 'res.company'
    # الشركة لا ترث mail.activity.mixin افتراضياً، نضيفه لدعم المهام
    _inherit = ['res.company', 'mail.activity.mixin', 'audit.review.mixin']

    def _audit_companies(self):
        self.ensure_one()
        return self

    def _audit_enabled_domain(self):
        return [('restrictive_audit_trail', '=', True)]
