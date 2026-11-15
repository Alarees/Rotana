# -*- coding: utf-8 -*-
from odoo import fields, models


class RotanaMaintenanceTeam(models.Model):
    _name = 'rotana.maintenance.team'
    _description = 'Rotana Maintenance Team (Section)'
    _order = 'sequence, name'

    name = fields.Char(string='Team Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    technician_ids = fields.Many2many(
        'hr.employee', 'rotana_maintenance_team_employee_rel', 'team_id', 'employee_id',
        string='Technicians')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Inverse side of the team technicians, used to filter the technicians list by section
    rotana_team_ids = fields.Many2many(
        'rotana.maintenance.team', 'rotana_maintenance_team_employee_rel', 'employee_id', 'team_id',
        string='Maintenance Teams')
