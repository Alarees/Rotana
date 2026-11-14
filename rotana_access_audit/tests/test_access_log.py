# -*- coding: utf-8 -*-
from odoo.addons.rotana_access_audit import uninstall_hook
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccessLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env['rotana.access.log']
        cls.user = cls.env['res.users'].create({'name': 'Audit target', 'login': 'audit_target'})
        # مجموعتان بالاسم نفسه تماماً
        cls.group_a = cls.env['res.groups'].create({'name': 'Same Name Group'})
        cls.group_b = cls.env['res.groups'].create({'name': 'Same Name Group'})

    def _group_logs(self, operation):
        return self.Log.search([
            ('target_user_id', '=', self.user.id), ('operation', '=', operation),
            ('res_model', '=', 'res.users')])

    def test_same_named_groups_are_tracked_by_id(self):
        self.assertEqual(self.group_a.display_name, self.group_b.display_name)
        self.user.write({'group_ids': [(4, self.group_a.id)]})
        self.user.write({'group_ids': [(4, self.group_b.id)]})
        self.assertEqual(len(self._group_logs('group_add')), 2)
        self.user.write({'group_ids': [(3, self.group_a.id)]})
        removed = self._group_logs('group_remove')
        self.assertEqual(len(removed), 1)
        self.assertIn('#%s' % self.group_a.id, removed.description)

    def test_log_is_read_only(self):
        self.user.write({'group_ids': [(4, self.group_a.id)]})
        log = self._group_logs('group_add')[:1]
        with self.assertRaises(UserError):
            log.write({'description': 'x'})
        with self.assertRaises(UserError):
            log.unlink()

    def test_uninstall_hook_saves_csv_backup(self):
        self.user.write({'group_ids': [(4, self.group_a.id)]})
        uninstall_hook(self.env)
        attachment = self.env['ir.attachment'].search(
            [('name', 'like', 'rotana_access_audit_backup_%')], order='id desc', limit=1)
        self.assertTrue(attachment)
        self.assertIn('Audit target', attachment.raw.decode('utf-8-sig'))
