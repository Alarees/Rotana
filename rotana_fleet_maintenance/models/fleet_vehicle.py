# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # حقل عادي (بدون compute) حتى لا يُعاد حسابه ويُمسح عند التثبيت أو الترقية.
    # يُنشأ الحساب مرة واحدة عند إنشاء المركبة تحت خطتها التحليلية.
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        copy=False, readonly=True, index='btree_not_null')

    def _ensure_analytic_account(self):
        """ينشئ الحساب التحليلي للمركبات التي لها خطة وليس لها حساب (مرة واحدة لكل مركبة)."""
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
