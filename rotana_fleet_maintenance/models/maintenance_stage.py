# -*- coding: utf-8 -*-
from odoo import fields, models


class RotanaMaintenanceStage(models.Model):
    _name = 'rotana.maintenance.stage'
    _description = 'Rotana Maintenance Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage', required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string='Folded in Kanban')
    done = fields.Boolean(
        string='Completion Stage',
        help='When a request is moved to this stage, the exit time is recorded and the spare parts entry is created.')
