# -*- coding: utf-8 -*-
"""توسعة سطر أمر البيع لإضافة الحساب التحليلي الخاص بالمركبة.

عند تحديد المركبة في أمر البيع، يُملأ الحساب التحليلي
لكل سطر بالحساب التحليلي المرتبط بتلك المركبة.
"""
from odoo import _, api, fields, models


class RotanaTransportSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _compute_analytic_distribution(self):
        """تمرير الحساب التحليلي للمركبة إلى توزيع التحليل التلقائي."""
        super()._compute_analytic_distribution()
        for line in self:
            if line.order_id.is_transport_order:
                for trip in line.order_id.trip_ids:
                    if trip.account_analytic_id:
                        account = trip.account_analytic_id
                        # دمج الحساب التحليلي للمركبة مع التوزيع الموجود
                        distribution = dict(line.analytic_distribution or {})
                        str_account_id = str(account.id)
                        total_weight = line.order_id.total_weight_to_transport
                        vehicle_weight = trip.transported_weight
                        distribution_percent = (vehicle_weight / total_weight) * 100 if total_weight else 0.0
                        if str_account_id in distribution:
                            distribution[str_account_id] += distribution_percent
                        else:
                            distribution[str_account_id] = distribution_percent
                        line.analytic_distribution = distribution