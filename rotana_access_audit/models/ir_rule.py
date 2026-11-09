# -*- coding: utf-8 -*-
from odoo import api, models

# الحقول غير الموجودة في الإصدار تُتجاهل تلقائياً
RULE_FIELDS = ['name', 'model_id', 'groups', 'group_ids', 'domain_force',
               'perm_read', 'perm_write', 'perm_create', 'perm_unlink', 'active']


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for rec in records.sudo():
                Log._log(rec, 'create', 'إنشاء قاعدة سجلات %s' % rec.display_name,
                         new=Log._summary(rec, RULE_FIELDS))
        return records

    def write(self, vals):
        if self.env.context.get('install_mode') or not any(k in vals for k in RULE_FIELDS):
            return super().write(vals)
        Log = self.env['rotana.access.log']
        before = Log._snapshot(self, RULE_FIELDS)
        result = super().write(vals)
        Log._log_changes(self, before, RULE_FIELDS)
        return result

    def unlink(self):
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for rec in self.sudo():
                Log._log(rec, 'unlink', 'حذف قاعدة سجلات %s' % rec.display_name,
                         old=Log._summary(rec, RULE_FIELDS))
        return super().unlink()
