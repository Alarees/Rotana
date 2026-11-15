# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RotanaMaintenanceWork(models.Model):
    _name = 'rotana.maintenance.work'
    _description = 'عمل في طلب صيانة روتانا'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one(
        'rotana.maintenance.request', string='طلب الصيانة',
        required=True, ondelete='cascade', index=True)
    team_id = fields.Many2one(
        'rotana.maintenance.team', string='القسم',
        compute='_compute_team_id', store=True, readonly=False)
    name = fields.Text(string='وصف العمل', required=True)
    technician_id = fields.Many2one('hr.employee', string='الفني')

    @api.depends('request_id.team_id')
    def _compute_team_id(self):
        for work in self:
            work.team_id = work.team_id or work.request_id.team_id

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.technician_id and self.team_id and self.technician_id not in self.team_id.technician_ids:
            self.technician_id = False
