# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFleetMaintenance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.parent_plan = cls.env['account.analytic.plan'].create({'name': 'Test Vehicles Parent'})
        cls.company.parent_analytic_plan_id = cls.parent_plan
        brand = cls.env['fleet.vehicle.brand'].create({'name': 'TestBrand'})
        cls.model = cls.env['fleet.vehicle.model'].create({'name': 'TestModel', 'brand_id': brand.id})

    def _new_vehicle(self, unit):
        return self.env['fleet.vehicle'].create({
            'model_id': self.model.id,
            'unit_number': unit,
            'license_plate': unit,
        })

    def test_account_created_once_on_vehicle_creation(self):
        vehicle = self._new_vehicle('T-001')
        account = vehicle.analytic_account_id
        self.assertTrue(account, 'The vehicle must get an analytic account when created.')
        self.assertEqual(account.plan_id, vehicle.analytic_plan_id)
        vehicle._ensure_analytic_account()
        self.assertEqual(vehicle.analytic_account_id, account, 'The account must not be re-created.')

    def test_account_is_not_blanked_on_recompute(self):
        vehicle = self._new_vehicle('T-002')
        account = vehicle.analytic_account_id
        vehicle.write({'analytic_plan_id': vehicle.analytic_plan_id.id})
        self.assertEqual(vehicle.analytic_account_id, account)

    def test_expense_account_defaults_from_company(self):
        account = self.env['account.account'].search([
            ('account_type', '=', 'expense'), ('company_ids', 'in', self.company.id)], limit=1)
        if not account:
            self.skipTest('No expense account in the test chart of accounts.')
        self.company.maintenance_expense_account_id = account
        vehicle = self._new_vehicle('T-003')
        request = self.env['maintenance.request'].create({
            'name': 'Test request', 'maintenance_for': 'fleet', 'fleet_id': vehicle.id})
        expense = self.env['maintenance.request.expense'].create({
            'request_id': request.id, 'name': 'Tyre', 'amount': 10.0})
        self.assertEqual(expense.account_id, account)
