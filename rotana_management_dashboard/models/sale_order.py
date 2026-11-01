# -*- coding: utf-8 -*-
from odoo import api, models

BUS_CHANNEL = 'rotana_management_dashboard'
BUS_EVENT = 'rotana_dashboard_sales_updated'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _rotana_dashboard_notify(self):
        """يرسل إشارة «حدث تغيير» فقط (بدون أرقام) ليعيد المتصفح جلب البيانات
        بصلاحيات المستخدم الفعلية."""
        bus = self.env['bus.bus']
        for company_id in set(self.mapped('company_id').ids):
            bus._sendone(BUS_CHANNEL, BUS_EVENT, {'company_id': company_id})

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        confirmed = orders.filtered(lambda o: o.state == 'sale')
        if confirmed:
            confirmed._rotana_dashboard_notify()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if {'state', 'date_order', 'company_id', 'currency_id'} & set(vals):
            self._rotana_dashboard_notify()
        return res
