# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_statement_period(self):
        """Return (date_from, date_to) = the 1st of the current month -> today.
        Adjust here if you want a rolling 7-day window instead of month-to-date.
        """
        today = fields.Date.context_today(self)
        date_from = today.replace(day=1)
        return date_from, today

    def get_weekly_statement_lines(self, date_from=None, date_to=None):
        """Return the account movement (invoices = debit, payments = credit)
        for this partner between date_from/date_to, with a running balance,
        plus the opening balance (balance carried from before date_from).

        Used by the QWeb report (report/weekly_statement_report.xml).
        """
        self.ensure_one()
        AccountMoveLine = self.env['account.move.line']

        if not date_from or not date_to:
            date_from, date_to = self._get_statement_period()

        base_domain = [
            ('partner_id', '=', self.id),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ]

        # Opening balance = everything posted before the period start
        opening_lines = AccountMoveLine.search(base_domain + [('date', '<', date_from)])
        opening_balance = sum(opening_lines.mapped('debit')) - sum(opening_lines.mapped('credit'))

        # Movement inside the period
        period_lines = AccountMoveLine.search(
            base_domain + [('date', '>=', date_from), ('date', '<=', date_to)],
            order='date asc, id asc',
        )

        running = opening_balance
        result_lines = []
        for line in period_lines:
            running += line.debit - line.credit
            result_lines.append({
                'date': line.date,
                'label': line.move_id.name or line.name or '/',
                'move_type': line.move_id.move_type,
                'debit': line.debit,
                'credit': line.credit,
                'balance': running,
            })

        return {
            'date_from': date_from,
            'date_to': date_to,
            'opening_balance': opening_balance,
            'lines': result_lines,
            'closing_balance': running,
            'total_debit': sum(l['debit'] for l in result_lines),
            'total_credit': sum(l['credit'] for l in result_lines),
        }

    def _has_statement_activity(self, date_from, date_to):
        self.ensure_one()
        count = self.env['account.move.line'].search_count([
            ('partner_id', '=', self.id),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        return count > 0

    @api.model
    def _cron_send_weekly_whatsapp_statement(self):
        """Scheduled action: send the WhatsApp statement template + PDF to
        every customer that has account movement this month and a phone number.
        """
        template = self.env.ref(
            'rotana_customer_statement.whatsapp_template_weekly_statement',
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Rotana weekly statement: WhatsApp template not found, skipping cron.")
            return

        today = fields.Date.context_today(self)
        date_from = today.replace(day=1)
        date_to = today
        period_label = "%s - %s" % (date_from.strftime('%d/%m/%Y'), date_to.strftime('%d/%m/%Y'))

        partners = self.search([
            ('customer_rank', '>', 0),
            ('active', '=', True),
            '|', ('phone', '!=', False), ('mobile', '!=', False),
        ])

        sent, skipped = 0, 0
        for partner in partners:
            if not partner._has_statement_activity(date_from, date_to):
                skipped += 1
                continue
            try:
                composer = self.env['whatsapp.composer'].with_context(
                    active_model='res.partner',
                    active_ids=partner.ids,
                ).create({
                    'wa_template_id': template.id,
                    'res_model': 'res.partner',
                    'res_ids': str(partner.id),
                })
                # Free-text variable {{2}} = the period label
                if hasattr(composer, 'free_text_json'):
                    composer.free_text_json = '{"2": "%s"}' % period_label
                composer._send_whatsapp_template()
                sent += 1
            except Exception:
                _logger.exception(
                    "Rotana weekly statement: failed to send WhatsApp to partner %s (%s)",
                    partner.id, partner.name,
                )
        _logger.info(
            "Rotana weekly statement cron: sent=%s skipped(no activity)=%s total_customers=%s",
            sent, skipped, len(partners),
        )
        return True
