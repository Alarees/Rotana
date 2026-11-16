# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGateKeeper(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref('rotana_gate_keeper.group_rotana_gate_keeper')
        cls.gate_user = cls.env['res.users'].create({
            'name': 'Gate keeper',
            'login': 'gate_keeper_test',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id, group.id])],
        })
        cls.plain_user = cls.env['res.users'].create({
            'name': 'Plain user',
            'login': 'gate_plain_test',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })
        picking_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'), ('company_id', '=', cls.env.company.id)], limit=1)
        cls.product = cls.env['product.product'].create({
            'name': 'Gate test wheat', 'type': 'consu', 'weight': 2.5})
        cls.picking = cls.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'move_ids': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 4,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            })],
        })

    def test_access_denied_without_group(self):
        with self.assertRaises(AccessError):
            self.env['rotana.gate.keeper'].with_user(self.plain_user).search_picking(self.picking.name)

    def test_search_returns_weights(self):
        res = self.env['rotana.gate.keeper'].with_user(self.gate_user).search_picking(self.picking.name)
        self.assertEqual(res['id'], self.picking.id)
        self.assertFalse(res['is_done'])
        self.assertEqual(res['total_weight'], 10.0)
        self.assertEqual(res['moves'][0]['weight'], 10.0)

    def test_search_not_found(self):
        res = self.env['rotana.gate.keeper'].with_user(self.gate_user).search_picking('NO/SUCH/0001')
        self.assertFalse(res)

    def test_save_ignores_non_editable_fields(self):
        self.picking.origin = 'ORIGINAL'
        self.env['rotana.gate.keeper'].with_user(self.gate_user).save_delivery_info(
            self.picking.id, {'origin': 'CHANGED', 'partner_id': 1})
        self.assertEqual(self.picking.origin, 'ORIGINAL')

    def _other_company_picking(self):
        company = self.env['res.company'].create({'name': 'Gate test company B'})
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'), ('company_id', '=', company.id)], limit=1)
        return company, self.env['stock.picking'].with_company(company).create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        })

    def test_other_company_without_access_is_not_found(self):
        _company, other = self._other_company_picking()
        res = self.env['rotana.gate.keeper'].with_user(self.gate_user).search_picking(other.name)
        self.assertFalse(res)

    def test_other_company_with_access_but_not_selected(self):
        company, other = self._other_company_picking()
        self.gate_user.write({'company_ids': [Command.link(company.id)]})
        gate = self.env['rotana.gate.keeper'].with_user(self.gate_user).with_context(
            allowed_company_ids=[self.env.company.id])
        with self.assertRaises(UserError):
            gate.search_picking(other.name)
        with self.assertRaises(AccessError):
            gate.save_delivery_info(other.id, {})
