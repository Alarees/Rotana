# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref('rotana_management_dashboard.group_rotana_dashboard_manager')
        cls.viewer = cls.env['res.users'].create({
            'name': 'Dashboard viewer', 'login': 'rmd_viewer',
            'group_ids': [(4, group.id)],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Dashboard outsider', 'login': 'rmd_outsider',
        })
        cls.model = cls.env['rotana.management.dashboard']

    def test_probe(self):
        self.assertTrue(self.model.with_user(self.viewer).has_dashboard_access())
        self.assertFalse(self.model.with_user(self.outsider).has_dashboard_access())

    def test_outsider_is_refused_everywhere(self):
        model = self.model.with_user(self.outsider)
        company = self.env.company
        with self.assertRaises(AccessError):
            model.get_sales_overview('2026-01-01', '2026-01-31')
        with self.assertRaises(AccessError):
            model.get_company_details(company.id, '2026-01-01', '2026-01-31')
        with self.assertRaises(AccessError):
            model.get_branches_overview('2026-01-01', '2026-01-31')

    def test_viewer_cannot_read_other_company(self):
        other = self.env['res.company'].create({'name': 'Not allowed company'})
        model = self.model.with_user(self.viewer)
        with self.assertRaises(AccessError):
            model.get_company_details(other.id, '2026-01-01', '2026-01-31')
        data = model.get_sales_overview('2026-01-01', '2026-01-31', [other.id])
        self.assertNotIn(other.id, [c['id'] for c in data['companies']])

    def test_invalid_input_is_a_clear_error(self):
        model = self.model.with_user(self.viewer)
        with self.assertRaises(UserError):
            model.get_sales_overview('not-a-date', '2026-01-31')
        with self.assertRaises(UserError):
            model.get_sales_overview('2026-01-01', '2026-01-31', 'abc')
        with self.assertRaises(UserError):
            model.get_sales_overview('2026-01-01', '2026-01-31', [{'x': 1}])
        with self.assertRaises(UserError):
            model.get_company_details('abc', '2026-01-01', '2026-01-31')
        with self.assertRaises(UserError):
            model.get_branches_overview('2026-01-01', 12345)
