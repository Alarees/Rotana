# -*- coding: utf-8 -*-
from odoo import models

from .sale_order import BUS_CHANNEL, BUS_EVENT


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _rotana_dashboard_notify_ar(self):
        """إشارة «حدث تغيير» عند ترحيل/إلغاء قيد يمس حساب ذمم العملاء (مديونيات/سداد)."""
        company_ids = set()
        for move in self:
            if any(line.account_id.account_type == 'asset_receivable' for line in move.line_ids):
                company_ids.add(move.company_id.id)
        bus = self.env['bus.bus']
        for company_id in company_ids:
            bus._sendone(BUS_CHANNEL, BUS_EVENT, {'company_id': company_id})

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._rotana_dashboard_notify_ar()
        return posted

    def button_draft(self):
        res = super().button_draft()
        self._rotana_dashboard_notify_ar()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self._rotana_dashboard_notify_ar()
        return res
