# -*- coding: utf-8 -*-
from odoo import api, fields, models

USER_FIELDS = ['login', 'active', 'company_id', 'company_ids', 'group_ids']


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_log_ids = fields.One2many(
        'rotana.access.log', 'target_user_id', string='سجل الصلاحيات', readonly=True)

    def _access_tracking_needed(self, vals):
        if self.env.context.get('install_mode'):
            return False
        return any(
            key in USER_FIELDS or key.startswith(('in_group_', 'sel_groups_'))
            for key in vals)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for user in users.sudo():
                Log._log(
                    user, 'create', 'إنشاء مستخدم %s' % user.name,
                    field_label='المجموعات',
                    new=', '.join(sorted(user.group_ids.mapped('display_name'))),
                    target_user=user)
        return users

    def write(self, vals):
        if not self._access_tracking_needed(vals):
            return super().write(vals)
        Log = self.env['rotana.access.log']
        before = Log._snapshot(self, USER_FIELDS)
        result = super().write(vals)
        Log._log_changes(self, before, USER_FIELDS, target_user_of=lambda rec: rec)
        return result

    def unlink(self):
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for user in self.sudo():
                Log._log(user, 'unlink', 'حذف مستخدم %s' % user.name, target_user=user)
        return super().unlink()
