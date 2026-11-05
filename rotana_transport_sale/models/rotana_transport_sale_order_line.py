# -*- coding: utf-8 -*-
"""توسعة سطر أمر البيع لإضافة الحساب التحليلي الخاص بالمركبة.

عند تحديد المركبة في أمر البيع، يُملأ الحساب التحليلي
لكل سطر بالحساب التحليلي المرتبط بتلك المركبة.
"""
from odoo import _, api, fields, models


# Unit name -> tons. Odoo's own UoM conversion cannot be trusted here: the database has two
# "TON" units, and count units (PCS, Packet, Roll...) are linked 1:1 to TON, so converting
# them would count every piece as one ton.
WEIGHT_UOM_TO_TON = {
    'ton': 1.0, 'tons': 1.0, 'tonne': 1.0, 'tonnes': 1.0, 't': 1.0,
    'kg': 0.001, 'kgs': 0.001, 'kilogram': 0.001,
    'g': 0.000001,
}


class RotanaTransportSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_transport_weight_tons(self):
        """Weight of this line in tons (0.0 when the line has no known weight).

        - Sections/notes, services and non-positive quantities do not count.
        - Weight units (TON, KG, g) are converted by unit name.
        - Count units (PCS, Carton, Bag...) use the product weight (kg per product unit).
          Products without a weight are not counted.
        """
        self.ensure_one()
        product = self.product_id
        if self.display_type or not product or product.type == 'service' or self.product_uom_qty <= 0:
            return 0.0
        factor = WEIGHT_UOM_TO_TON.get((self.product_uom_id.name or '').strip().lower())
        if factor is not None:
            return self.product_uom_qty * factor
        return self.product_qty * (product.weight or 0.0) / 1000.0

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