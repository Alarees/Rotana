# -*- coding: utf-8 -*-
from odoo import api, models

GROUP_FIELDS = ['name', 'implied_ids']


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _access_users_fname(self):
        # اسم الحقل يختلف بين الإصدارات (user_ids في 19، users سابقاً)
        return 'user_ids' if 'user_ids' in self._fields else 'users'

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for group in groups.sudo():
                Log._log(group, 'create', 'إنشاء مجموعة %s' % group.display_name,
                         new=Log._summary(group, GROUP_FIELDS))
        return groups

    def write(self, vals):
        ufield = self._access_users_fname()
        tracked = GROUP_FIELDS + [ufield]
        if self.env.context.get('install_mode') or not any(k in vals for k in tracked):
            return super().write(vals)
        Log = self.env['rotana.access.log']
        before = Log._snapshot(self, GROUP_FIELDS)
        before_users = {g.id: set(g.sudo()[ufield].ids) for g in self}
        result = super().write(vals)
        Log._log_changes(self, before, GROUP_FIELDS)
        Users = self.env['res.users'].sudo()
        for group in self.sudo():
            old_ids = before_users.get(group.id, set())
            new_ids = set(group[ufield].ids)
            for user in Users.browse(sorted(new_ids - old_ids)):
                Log._log(group, 'group_add',
                         'إضافة المستخدم %s إلى المجموعة %s' % (user.name, group.display_name),
                         'المجموعات', new=group.display_name, target_user=user)
            for user in Users.browse(sorted(old_ids - new_ids)):
                Log._log(group, 'group_remove',
                         'إزالة المستخدم %s من المجموعة %s' % (user.name, group.display_name),
                         'المجموعات', old=group.display_name, target_user=user)
        return result

    def unlink(self):
        if not self.env.context.get('install_mode'):
            Log = self.env['rotana.access.log']
            for group in self.sudo():
                Log._log(group, 'unlink', 'حذف مجموعة %s' % group.display_name,
                         old=Log._summary(group, GROUP_FIELDS))
        return super().unlink()
