# -*- coding: utf-8 -*-
"""نموذج مركبات النقل لشركة روتانا.

يُدير بيانات المركبات المستخدمة في خدمات النقل،
بما في ذلك الموقع الحالي للمركبة الذي يُحدَّث تلقائياً
عند اكتمال الرحلة.
"""
from odoo import _, api, fields, models


class FleetVehicleNote(models.Model):
    _name = 'fleet.vehicle.note'
    _description = 'ملاحظات مركبة النقل'

    name = fields.Char(
        string='التعليق',
        required=True,
    )