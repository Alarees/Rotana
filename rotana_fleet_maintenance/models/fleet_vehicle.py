from odoo import _, api, fields, models

class FleetVecicle(models.Model):
    _inherit = 'fleet.vehicle'

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='الحساب التحليلي', copy=False, readonly=True, store=True, compute='_compute_analytic_account')

    @api.depends('analytic_plan_id')
    def _compute_analytic_account(self):
        for rec in self:
            plan = rec.analytic_plan_id
            if plan:
                analytic = {
                    'name': rec.display_name,
                    'plan_id': plan.id,
                    'company_id': self.company_id.id,
                }
                rec.analytic_account_id = self.env['account.analytic.account'].sudo().create(analytic)