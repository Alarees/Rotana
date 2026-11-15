# -*- coding: utf-8 -*-
from odoo import fields, models


class RotanaMaintenanceStage(models.Model):
    _name = 'rotana.maintenance.stage'
    _description = 'مرحلة طلب صيانة روتانا'
    _order = 'sequence, id'

    name = fields.Char(string='المرحلة', required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string='مطوية في الكانبان')
    done = fields.Boolean(
        string='مرحلة الإكمال',
        help='عند نقل الطلب إلى هذه المرحلة يُسجَّل زمن الخروج ويُنشأ قيد قطع الغيار.')
