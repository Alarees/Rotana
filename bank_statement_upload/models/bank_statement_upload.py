import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import parser


class BankStatementUpload(models.Model):
    _name = 'bank.statement.upload'
    _description = 'Bank Statement Upload'
    _order = 'id desc'

    name = fields.Char(default=lambda self: _('New'), readonly=True, copy=False)
    journal_id = fields.Many2one(
        'account.journal', string='Bank Journal', required=True,
        domain="[('type', '=', 'bank')]", check_company=True)
    company_id = fields.Many2one(
        'res.company', related='journal_id.company_id', store=True, readonly=True)
    file = fields.Binary(string='Statement (PDF)', attachment=True, copy=False)
    filename = fields.Char()
    state = fields.Selection(
        [('draft', 'Draft'), ('read', 'Read')], default='draft', readonly=True, copy=False)
    line_ids = fields.One2many('bank.statement.upload.line', 'upload_id', string='Operations')
    line_count = fields.Integer(compute='_compute_counts')
    posted_count = fields.Integer(compute='_compute_counts')
    unposted_count = fields.Integer(compute='_compute_counts')

    @api.depends('line_ids.is_posted')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.posted_count = len(rec.line_ids.filtered('is_posted'))
            rec.unposted_count = rec.line_count - rec.posted_count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bank.statement.upload') or _('New')
        return super().create(vals_list)

    @staticmethod
    def _make_key(row, direction):
        raw = '|'.join([
            row['ref'], row['op_type'], row['account_no'], row['date'].isoformat(),
            '%.2f' % (row['bank_debit'] or row['bank_credit']), direction])
        return hashlib.sha1(raw.encode()).hexdigest()

    def action_read_statement(self):
        Line = self.env['bank.statement.upload.line']
        for rec in self:
            if not rec.file:
                raise UserError(_('Please upload the statement file first.'))
            try:
                rows = parser.parse_statement(base64.b64decode(rec.file))
            except Exception as e:
                raise UserError(_('Could not read the PDF statement: %s', e)) from e
            if not rows:
                raise UserError(_('No operations were found in the file.'))
            prepared, seen = [], set()
            for row in rows:
                # The bank states things from its own point of view:
                # bank debit -> our credit, bank credit -> our debit.
                direction = 'out' if row['bank_debit'] else 'in'
                key = self._make_key(row, direction)
                prepared.append((key, row))
            keys = list({k for k, _r in prepared})
            existing = set(Line.search([
                ('journal_id', '=', rec.journal_id.id), ('unique_key', 'in', keys)]).mapped('unique_key'))
            vals_list, skipped = [], 0
            for key, row in prepared:
                if key in existing or key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                vals_list.append({
                    'upload_id': rec.id,
                    'unique_key': key,
                    'date': row['date'],
                    'description': row['description'],
                    'ref': row['ref'],
                    'op_type': row['op_type'],
                    'account_no': row['account_no'],
                    'debit': row['bank_credit'],   # reversed
                    'credit': row['bank_debit'],   # reversed
                    'bank_balance': row['balance'],
                })
            Line.create(vals_list)
            rec.state = 'read'
            msg = _('%(new)s operations registered, %(dup)s duplicates skipped.',
                    new=len(vals_list), dup=skipped)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Statement read'), 'message': msg, 'type': 'success',
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    def action_post_lines(self):
        return self.line_ids.action_post_lines()


class BankStatementUploadLine(models.Model):
    _name = 'bank.statement.upload.line'
    _description = 'Bank Statement Upload Line'
    _order = 'date desc, id desc'

    _unique_key_journal = models.Constraint(
        'unique(journal_id, unique_key)',
        'This operation was already registered for this journal.')

    upload_id = fields.Many2one('bank.statement.upload', ondelete='cascade', required=True, index=True)
    journal_id = fields.Many2one(related='upload_id.journal_id', store=True, index=True)
    company_id = fields.Many2one(related='upload_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id')
    unique_key = fields.Char(required=True, copy=False, index=True)
    date = fields.Date(required=True)
    ref = fields.Char(string='Transaction No.', index=True)
    op_type = fields.Char(string='Operation')
    account_no = fields.Char(string='Account / Ref #')
    description = fields.Text()
    debit = fields.Monetary(currency_field='currency_id', help='Money in (bank credit, reversed).')
    credit = fields.Monetary(currency_field='currency_id', help='Money out (bank debit, reversed).')
    amount = fields.Monetary(currency_field='currency_id', compute='_compute_amount', store=True)
    bank_balance = fields.Monetary(currency_field='currency_id')
    is_posted = fields.Boolean(string='Posted', default=False, readonly=True, copy=False, index=True)
    posted_date = fields.Datetime(readonly=True, copy=False)
    bank_statement_line_id = fields.Many2one(
        'account.bank.statement.line', string='Bank Statement Line', readonly=True, copy=False)

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.journal_id.currency_id or rec.company_id.currency_id

    @api.depends('debit', 'credit')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.debit - rec.credit

    def unlink(self):
        if self.filtered('is_posted'):
            raise UserError(_('Posted operations cannot be deleted.'))
        return super().unlink()

    def action_post_lines(self):
        """Post only the operations that are not yet posted."""
        lines = self.filtered(lambda l: not l.is_posted)
        if not lines:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Nothing to post'), 'type': 'warning',
                           'message': _('All selected operations are already posted.')},
            }
        st_vals = [{
            'journal_id': l.journal_id.id,
            'date': l.date,
            'payment_ref': ('%s - %s' % (l.op_type, l.ref)) if l.ref else (l.op_type or l.description),
            'amount': l.amount,
            'unique_import_id': 'BOKPDF-%s-%s' % (l.journal_id.id, l.unique_key),
        } for l in lines]
        statement_lines = self.env['account.bank.statement.line'].create(st_vals)
        now = fields.Datetime.now()
        for line, st in zip(lines, statement_lines):
            line.write({'is_posted': True, 'posted_date': now, 'bank_statement_line_id': st.id})
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Posted'), 'type': 'success',
                       'message': _('%s operations posted to bank statement lines.', len(lines)),
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }
