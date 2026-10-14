# -*- coding: utf-8 -*-
"""التوزيع التحليلي لرحلات أمر بيع النقل على سطور الفاتورة.

عند إصدار فاتورة من أمر بيع نقل يُوزَّع كل سطر على الحسابات التحليلية للرحلات
بنسبة (الوزن المنقول في الرحلة / إجمالي الوزن المطلوب نقله في أمر البيع)،
وعند ترحيل الفاتورة تُنشأ السطور التحليلية لكل رحلة تلقائياً من هذا التوزيع.
"""
from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_trip_analytic_order(self):
        """أمر بيع النقل المرتبط بسطر الفاتورة (أو فارغ)."""
        self.ensure_one()
        sale_line = self.sale_line_ids[:1]
        if not sale_line or sale_line.display_type or sale_line.is_downpayment:
            return self.env['sale.order']
        order = sale_line.order_id
        return order if order.is_transport_order else self.env['sale.order']

    def _merge_trip_distribution(self, base, order):
        """يحذف حسابات رحلات الأمر من التوزيع الحالي ويضيف النسب المحدثة."""
        trip_account_ids = set(order.trip_ids.account_analytic_id.ids)
        merged = {}
        for key, percent in (base or {}).items():
            account_ids = {int(acc) for acc in key.split(',') if acc.strip()}
            if account_ids & trip_account_ids:
                continue
            merged[key] = percent
        merged.update(order._get_trip_analytic_distribution())
        return merged

    def _related_analytic_distribution(self):
        # EXTENDS 'sale': توزيع الرحلات يُحسب لحظة إنشاء سطر الفاتورة
        vals = super()._related_analytic_distribution()
        order = self._get_trip_analytic_order()
        if order:
            vals = self._merge_trip_distribution(vals, order)
        return vals

    def _refresh_trip_analytic_distribution(self):
        """تحديث نسب الرحلات حسب أحدث الأوزان المنقولة."""
        for line in self.filtered(lambda l: l.display_type == 'product'):
            order = line._get_trip_analytic_order()
            if not order:
                continue
            new_distribution = line._merge_trip_distribution(
                line.analytic_distribution, order
            )
            if new_distribution != (line.analytic_distribution or {}):
                line.analytic_distribution = new_distribution


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # قبل الترحيل (وإنشاء السطور التحليلية) تُحدَّث نسب الرحلات بأحدث الأوزان
        invoices = self.filtered(
            lambda move: move.move_type == 'out_invoice' and move.state == 'draft'
        )
        invoices.invoice_line_ids._refresh_trip_analytic_distribution()
        return super()._post(soft=soft)
