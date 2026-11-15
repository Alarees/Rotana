# -*- coding: utf-8 -*-
from odoo import fields, models


class RotanaMaintenanceTeam(models.Model):
    _name = 'rotana.maintenance.team'
    _description = 'فريق صيانة روتانا (قسم)'
    _order = 'sequence, name'

    name = fields.Char(string='اسم الفريق', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='اللون')
    company_id = fields.Many2one('res.company', string='الشركة', default=lambda self: self.env.company)
    technician_ids = fields.Many2many(
        'hr.employee', 'rotana_maintenance_team_employee_rel', 'team_id', 'employee_id',
        string='الفنيون')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # الوجه المعاكس لفنيي الفريق، يُستخدم لتصفية قائمة الفنيين حسب القسم
    rotana_team_ids = fields.Many2many(
        'rotana.maintenance.team', 'rotana_maintenance_team_employee_rel', 'employee_id', 'team_id',
        string='فرق الصيانة')
