# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RotanaMaintenanceWork(models.Model):
    _name = 'rotana.maintenance.work'
    _description = 'Rotana Maintenance Work'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one(
        'rotana.maintenance.request', string='Maintenance Request',
        required=True, ondelete='cascade', index=True)
    team_id = fields.Many2one('rotana.maintenance.team', string='Section')
    name = fields.Text(string='Work Description', required=True)
    technician_ids = fields.Many2many(
        'hr.employee', 'rotana_maintenance_work_employee_rel', 'work_id', 'employee_id',
        string='Technicians')

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            self.technician_ids = self.technician_ids.filtered(
                lambda t: t in self.team_id.technician_ids)
