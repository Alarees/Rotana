# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFleetMaintenance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.parent_plan = cls.env['account.analytic.plan'].create({'name': 'Test Vehicles Parent'})
        cls.company.parent_analytic_plan_id = cls.parent_plan
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'TestBrand'})
        cls.model = cls.env['fleet.vehicle.model'].create({'name': 'TestModel', 'brand_id': brand.id})

    def _new_vehicle(self, unit):
        return self.env['fleet.vehicle'].create({
            'model_id': self.model.id,
            'unit_number': unit,
            'license_plate': unit,
        })

    def _new_request(self, vehicle, **kw):
        return self.env['rotana.maintenance.request'].create(
            dict({'name': 'Test request', 'fleet_id': vehicle.id}, **kw))

    # ------------------------------------------------------------------
    # Vehicle and analytic account
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Request data
    # ------------------------------------------------------------------
    def test_request_defaults_and_downtime(self):
        vehicle = self._new_vehicle('T-010')
        request = self._new_request(vehicle)
        self.assertTrue(request.stage_id, 'A default stage must be set.')
        self.assertTrue(request.entry_datetime)
        self.assertFalse(request.exit_datetime)
        self.assertEqual(request.downtime_hours, 0.0)
        entry = fields.Datetime.now()
        request.write({'entry_datetime': entry, 'exit_datetime': entry + timedelta(hours=61, minutes=8)})
        self.assertAlmostEqual(request.downtime_hours, 61 + 8 / 60.0, places=3)
        with self.assertRaises(Exception):
            request.exit_datetime = entry - timedelta(hours=1)

    def test_work_lines_many_technicians(self):
        tech1 = self.env['hr.employee'].create({'name': 'Tech One'})
        tech2 = self.env['hr.employee'].create({'name': 'Tech Two'})
        team = self.env['rotana.maintenance.team'].create({
            'name': 'Electric', 'color': 4, 'technician_ids': [(6, 0, (tech1 | tech2).ids)]})
        self.assertEqual(tech1.rotana_team_ids, team)
        request = self._new_request(self._new_vehicle('T-011'))
        work = self.env['rotana.maintenance.work'].create({
            'request_id': request.id, 'team_id': team.id, 'name': 'Fix wiring',
            'technician_ids': [(6, 0, (tech1 | tech2).ids)]})
        self.assertEqual(work.technician_ids, tech1 | tech2)

    def test_request_has_no_job_card_or_team_fields(self):
        fields_ = self.env['rotana.maintenance.request']._fields
        for name in ('job_card_no', 'report_no', 'team_id', 'technician_id'):
            self.assertNotIn(name, fields_)

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------
    def test_expense_account_defaults_from_company(self):
        account = self.env['account.account'].search([
            ('account_type', '=', 'expense'), ('company_ids', 'in', self.company.id)], limit=1)
        if not account:
            self.skipTest('No expense account in the test chart of accounts.')
        self.company.maintenance_expense_account_id = account
        request = self._new_request(self._new_vehicle('T-003'))
        expense = self.env['rotana.maintenance.expense'].create({
            'request_id': request.id, 'name': 'Tyre', 'amount': 10.0})
        self.assertEqual(expense.account_id, account)

    # ------------------------------------------------------------------
    # Spare parts: confirm then complete
    # ------------------------------------------------------------------
    def test_confirm_without_parts(self):
        request = self._new_request(self._new_vehicle('T-020'))
        request.action_confirm_parts()
        self.assertEqual(request.parts_state, 'confirmed')
        self.assertFalse(request.picking_ids)
        done_stage = self.env['rotana.maintenance.stage'].search([('done', '=', True)], limit=1)
        request.stage_id = done_stage
        self.assertEqual(request.parts_state, 'done')

    def test_confirm_and_complete_flow(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.company.maintenance_scrap_picking_type_id = warehouse.in_type_id
        self.company.maintenance_rehab_picking_type_id = warehouse.in_type_id
        product = self.env['product.product'].create({
            'name': 'Test spare', 'type': 'consu', 'is_storable': True, 'standard_price': 10.0})
        self.env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 10.0)

        vehicle = self._new_vehicle('T-021')
        request = self._new_request(vehicle)
        self.env['rotana.maintenance.part'].create({
            'request_id': request.id, 'product_id': product.id, 'quantity': 2.0, 'spare_state': 'scrap'})
        request.action_confirm_parts()
        self.assertEqual(request.parts_state, 'confirmed')
        pickings = request.picking_ids
        self.assertTrue(pickings)
        self.assertTrue(all(p.rotana_request_id == request for p in pickings))

        # The request cannot be completed before the delivery orders are done
        done_stage = self.env['rotana.maintenance.stage'].search([('done', '=', True)], limit=1)
        with self.assertRaises(UserError):
            request.stage_id = done_stage

        for picking in pickings:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking._action_done()
        request.stage_id = done_stage
        self.assertEqual(request.parts_state, 'done')
        self.assertTrue(request.exit_datetime, 'Completing the request sets the exit time.')

    def test_warehouse_filter_on_catalog(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        product = self.env['product.product'].create({
            'name': 'Filtered spare', 'type': 'consu', 'is_storable': True})
        other = self.env['product.product'].create({
            'name': 'Not in stock', 'type': 'consu', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 3.0)
        found = self.env['product.product'].search([('maintenance_warehouse_id', '=', warehouse.id)])
        self.assertIn(product, found)
        self.assertNotIn(other, found)

    def test_rehab_line_creates_workshop_and_reset_removes_it(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.company.maintenance_scrap_picking_type_id = warehouse.in_type_id
        self.company.maintenance_rehab_picking_type_id = warehouse.in_type_id
        product = self.env['product.product'].create({
            'name': 'Rehab spare', 'type': 'consu', 'is_storable': True, 'standard_price': 4.0})
        self.env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 5.0)
        request = self._new_request(self._new_vehicle('T-030'))
        self.env['rotana.maintenance.part'].create({
            'request_id': request.id, 'product_id': product.id, 'quantity': 1.0, 'spare_state': 'rehab'})
        request.action_confirm_parts()
        self.assertEqual(len(request.workshop_ids), 1)
        self.assertFalse(
            request.picking_ids.filtered(lambda p: p.picking_type_code == 'incoming'),
            'Rehab lines get a workshop request instead of a receipt.')
        request.action_reset_parts()
        self.assertEqual(request.parts_state, 'draft')
        self.assertFalse(request.workshop_ids)

    def test_workshop_technicians_filled_from_request_works(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.company.maintenance_scrap_picking_type_id = warehouse.in_type_id
        self.company.maintenance_rehab_picking_type_id = warehouse.in_type_id
        tires = self.env['rotana.maintenance.team'].create({'name': 'Tires'})
        electric = self.env['rotana.maintenance.team'].create({'name': 'Electric'})
        tech_a = self.env['hr.employee'].create({'name': 'Tire Tech A'})
        tech_b = self.env['hr.employee'].create({'name': 'Tire Tech B'})
        tech_c = self.env['hr.employee'].create({'name': 'Electrician'})
        product = self.env['product.product'].create({
            'name': 'Rehab tyre', 'type': 'consu', 'is_storable': True, 'standard_price': 4.0})
        self.env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 5.0)
        request = self._new_request(self._new_vehicle('T-040'))
        Work = self.env['rotana.maintenance.work']
        Work.create({'request_id': request.id, 'team_id': tires.id, 'name': 'Change tyres',
                     'technician_ids': [(6, 0, (tech_a | tech_b).ids)]})
        Work.create({'request_id': request.id, 'team_id': electric.id, 'name': 'Wiring',
                     'technician_ids': [(6, 0, tech_c.ids)]})
        self.env['rotana.maintenance.part'].create({
            'request_id': request.id, 'product_id': product.id, 'quantity': 1.0,
            'spare_state': 'rehab', 'team_id': tires.id})
        request.action_confirm_parts()
        workshop = request.workshop_ids
        self.assertEqual(workshop.team_id, tires)
        self.assertEqual(workshop.technician_ids, tech_a | tech_b,
                         'Only the technicians of the works of the same section are filled.')
        # a technician added to the works is propagated while the request is not sent yet
        Work.search([('request_id', '=', request.id), ('team_id', '=', tires.id)]).technician_ids = tech_a
        self.assertEqual(workshop.technician_ids, tech_a)

    def test_completion_updates_vehicle_odometer(self):
        vehicle = self._new_vehicle('T-050')
        entry = fields.Datetime.now() - timedelta(days=2)
        request = self._new_request(vehicle, odometer=189116.0, entry_datetime=entry)
        done_stage = self.env['rotana.maintenance.stage'].search([('done', '=', True)], limit=1)
        request.action_confirm_parts()
        request.stage_id = done_stage
        self.assertTrue(request.odometer_log_id)
        self.assertEqual(vehicle.odometer, 189116.0)
        self.assertEqual(request.odometer_log_id.date, fields.Datetime.context_timestamp(request, entry).date())
        # the log is reused, not duplicated, when the reading changes
        log = request.odometer_log_id
        request.write({'stage_id': request.stage_id.id})
        request.odometer = 189200.0
        request._update_vehicle_odometer()
        self.assertEqual(request.odometer_log_id, log)
        self.assertEqual(log.value, 189200.0)
