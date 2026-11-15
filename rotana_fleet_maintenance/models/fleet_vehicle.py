# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # Plain field (no compute) so it is not recomputed and wiped on install or upgrade.
    # The account is created once, when the vehicle is created, under its analytic plan.
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        copy=False, readonly=True, index='btree_not_null')

    def _ensure_analytic_account(self):
        """Create the analytic account of vehicles that have a plan but no account (once per vehicle)."""
        Account = self.env['account.analytic.account'].sudo()
        for vehicle in self:
            if vehicle.analytic_account_id or not vehicle.analytic_plan_id:
                continue
            vehicle.analytic_account_id = Account.create({
                'name': vehicle.display_name,
                'plan_id': vehicle.analytic_plan_id.id,
                'company_id': vehicle.company_id.id,
            })
        return self

    @api.model_create_multi
    def create(self, vals_list):
        vehicles = super().create(vals_list)
        vehicles._ensure_analytic_account()
        return vehicles
