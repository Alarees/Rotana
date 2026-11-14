# -*- coding: utf-8 -*-
from odoo import models


# حقول إعدادات الشركة (الخطة الأم، العجز المسموح، حساب ودفتر العهدة)
# انتقلت إلى المديول الأساسي rotana_base_transport.
class ResUser(models.Model):
    _name = 'res.users'
    _inherit = ['res.users', 'mail.thread', 'mail.activity.mixin']
