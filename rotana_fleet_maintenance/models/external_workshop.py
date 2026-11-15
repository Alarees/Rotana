# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Fields that cannot be edited once the request entered the workshop
LOCKED_FIELDS = {'maintenance_request_id', 'fleet_id', 'product_id', 'quantity', 'picking_type_id'}
# Vendor and amount: editable in (In Workshop) and (Maintenance Done) until invoiced
FINANCIAL_FIELDS = {'partner_id', 'amount'}


class RotanaExternalWorkshop(models.Model):
    _name = 'rotana.external.workshop'
    _description = 'Spare Part Maintenance Request (External Maintenance)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Number', default='/', readonly=True, copy=False)
    maintenance_request_id = fields.Many2one(
        'rotana.maintenance.request', string='Maintenance Request', index=True,
        ondelete='set null', copy=False)
    fleet_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', index=True,
        compute='_compute_fleet_id', store=True, readonly=False)
    part_line_id = fields.Many2one(
        'rotana.maintenance.part', string='Spare Line in Maintenance',
        copy=False, index='btree_not_null', ondelete='set null')
    team_id = fields.Many2one(
        related='part_line_id.team_id', string='Section', readonly=True)
    technician_ids = fields.Many2many(
        'hr.employee', 'rotana_external_workshop_employee_rel', 'workshop_id', 'employee_id',
        string='Technicians', compute='_compute_technician_ids', store=True, readonly=False,
        help='Filled from the works of the maintenance request that belong to the section '
             'of the spare part line. It can be edited until the maintenance is done.')
    product_id = fields.Many2one(
        'product.product', string='Spare Part', required=True, tracking=True,
        domain="[('type', '=', 'consu'), ('is_storable', '=', True)]")
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Vendor', tracking=True)
    amount = fields.Monetary(string='Amount', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('in_workshop', 'In Workshop'),
            ('done', 'Maintenance Done'),
        ],
        string='Status', default='draft', required=True, readonly=True, copy=False, tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='Vendor Bill', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null')
    invoice_state = fields.Selection(
        [('not_invoiced', 'Not Invoiced'), ('invoiced', 'Invoiced')],
        string='Invoice Status', compute='_compute_invoice_state', store=True, default='not_invoiced')
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Operation Type',
        compute='_compute_picking_type_id', store=True, readonly=False, precompute=True,
        domain="[('code', '=', 'incoming'), ('company_id', '=', company_id)]")
    picking_id = fields.Many2one(
        'stock.picking', string='Receipt', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null')
    settlement_move_id = fields.Many2one(
        'account.move', string='Stock Settlement Entry', copy=False, readonly=True,
        ondelete='set null')

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
    @api.depends(
        'part_line_id.team_id',
        'maintenance_request_id.work_ids.team_id',
        'maintenance_request_id.work_ids.technician_ids',
    )
    def _compute_technician_ids(self):
        """ Technicians of the request works that belong to the section of the spare part line. """
        for rec in self:
            team = rec.part_line_id.team_id
            if rec.state in ('in_workshop', 'done') or not team:
                rec.technician_ids = rec.technician_ids
                continue
            works = rec.maintenance_request_id.work_ids.filtered(lambda w: w.team_id == team)
            rec.technician_ids = works.technician_ids

    @api.depends('maintenance_request_id.fleet_id')
    def _compute_fleet_id(self):
        for rec in self:
            rec.fleet_id = rec.maintenance_request_id.fleet_id or rec.fleet_id

    @api.depends('company_id')
    def _compute_picking_type_id(self):
        for rec in self:
            company_type = rec.company_id.maintenance_rehab_picking_type_id
            if not rec.picking_type_id or rec.picking_type_id.company_id != rec.company_id:
                rec.picking_type_id = company_type

    @api.depends('invoice_id', 'invoice_id.state')
    def _compute_invoice_state(self):
        for rec in self:
            rec.invoice_state = 'invoiced' if rec.invoice_id and rec.invoice_id.state != 'cancel' \
                else 'not_invoiced'

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('The spare part quantity must be greater than zero.'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = self._next_company_sequence(company_id)
        return super().create(vals_list)

    @api.model
    def _next_company_sequence(self, company_id):
        """ Independent numbering per company: the company sequence is created on first use. """
        Sequence = self.env['ir.sequence'].sudo()
        code = 'rotana.external.workshop'
        sequence = Sequence.search([('code', '=', code), ('company_id', '=', company_id)], limit=1)
        if not sequence:
            sequence = Sequence.create({
                'name': _('External Maintenance'), 'code': code, 'prefix': 'EW/',
                'padding': 5, 'company_id': company_id,
            })
        return sequence.next_by_id()

    def write(self, vals):
        keys = set(vals)
        if keys & LOCKED_FIELDS and any(r.state not in ('draft', 'confirmed') for r in self):
            raise UserError(_('The request data cannot be modified after it is sent to the workshop.'))
        if keys & FINANCIAL_FIELDS:
            if any(r.state not in ('in_workshop', 'done') for r in self):
                raise UserError(_('Vendor and amount can only be set in the (In Workshop) or (Maintenance Done) status.'))
            if any(r.invoice_state == 'invoiced' for r in self):
                raise UserError(_('The vendor or amount cannot be modified after invoicing.'))
        return super().write(vals)

    def unlink(self):
        if any(r.state not in ('draft', 'confirmed') for r in self):
            raise UserError(_('A request that entered the workshop cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Status buttons
    # ------------------------------------------------------------------
    def _check_workshop_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group('rotana_fleet_maintenance.group_external_workshop_manager'):
            raise UserError(_('This action is only available to the external maintenance manager.'))

    def action_confirm(self):
        self._check_workshop_manager()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.product_id or rec.quantity <= 0:
                raise UserError(_('Set the spare part and quantity before confirming.'))
            rec.state = 'confirmed'
        return True

    def action_send_to_workshop(self):
        self._check_workshop_manager()
        for rec in self.filtered(lambda r: r.state == 'confirmed'):
            rec.state = 'in_workshop'
        return True

    def action_done(self):
        self._check_workshop_manager()
        for rec in self.filtered(lambda r: r.state == 'in_workshop'):
            if not rec.partner_id:
                raise UserError(_('Set the vendor of request %s before marking the maintenance as done.', rec.name))
            if not rec.amount:
                raise UserError(_('Set the amount of request %s before marking the maintenance as done.', rec.name))
            if not rec.picking_type_id:
                raise UserError(_(
                    'Set the operation type of request %s or set the "Rehabilitation Operation Type" in the company settings.', rec.name))
            if rec.picking_type_id.code != 'incoming':
                raise UserError(_('The operation type must be a receipt.'))
            rec._create_receipt()
            rec._create_settlement_entry()
            rec.state = 'done'
        return True

    # ------------------------------------------------------------------
    # Receipt (not linked to the maintenance request nor the vendor)
    # ------------------------------------------------------------------
    def _create_receipt(self):
        self.ensure_one()
        picking_type = self.picking_type_id
        src_location = picking_type.default_location_src_id
        move_vals = {
            'product_id': self.product_id.id,
            'product_uom_qty': self.quantity,
            'product_uom': self.product_id.uom_id.id,
            'company_id': self.company_id.id,
        }
        if src_location:
            move_vals['location_id'] = src_location.id
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'fleet_id': self.fleet_id.id or False,
            'move_ids': [Command.create(move_vals)],
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()
        if picking.state != 'done':
            raise UserError(_('The receipt %s could not be validated automatically, please review it.', picking.name))
        self.picking_id = picking
        return picking

    # ------------------------------------------------------------------
    # Stock value settlement entry for the spare value only (without the maintenance amount)
    # The receipt raises the stock against the valuation account of the source location; the entry closes
    # this account against the expense account charged with the spare on delivery.
    # ------------------------------------------------------------------
    def _create_settlement_entry(self):
        self.ensure_one()
        company = self.company_id
        currency = company.currency_id
        moves = self.picking_id.sudo().move_ids.filtered(lambda m: m.state == 'done')
        debit_by_account = defaultdict(float)
        credit_by_account = defaultdict(float)
        for move in moves:
            if not move.account_move_id:
                continue
            valuation_account = move.location_id.valuation_account_id
            if not valuation_account:
                raise UserError(_(
                    'The settlement entry cannot be posted: location "%(location)s" has no stock valuation account. '
                    'Set the account on the location and try again.',
                    location=move.location_id.display_name))
            amount = currency.round(abs(move.value))
            if currency.is_zero(amount):
                continue
            accounts = move.product_id.with_company(company)._get_product_accounts()
            expense_account = company.maintenance_expense_account_id or accounts['expense']
            if not expense_account:
                raise UserError(_(
                    'Set the "Spare Parts Expense Account" in the company settings or the expense account on the product category %s.',
                    move.product_id.categ_id.display_name))
            debit_by_account[valuation_account] += amount
            credit_by_account[expense_account] += amount
        if not debit_by_account:
            return False
        journal = company.maintenance_journal_id or self.env['account.journal'].sudo().search(
            [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('There is no journal of type "Miscellaneous" for company %s.', company.name))
        label = _('Spare value settlement - %s', self.name)
        line_vals = [Command.create({
            'name': label,
            'account_id': account.id,
            'debit': amount,
            'credit': 0.0,
        }) for account, amount in debit_by_account.items()]
        line_vals += [Command.create({
            'name': label,
            'account_id': account.id,
            'debit': 0.0,
            'credit': amount,
        }) for account, amount in credit_by_account.items()]
        account_move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'company_id': company.id,
            'date': fields.Date.context_today(self),
            'ref': label,
            'line_ids': line_vals,
        })
        account_move._post()
        self.settlement_move_id = account_move
        return account_move

    # ------------------------------------------------------------------
    # Invoicing (vendor bill linked to the vehicle analytic account)
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        self.ensure_one()
        self._check_workshop_manager()
        if self.state != 'done':
            raise UserError(_('Invoicing is only available after (Maintenance Done).'))
        if self.invoice_state == 'invoiced':
            raise UserError(_('This request has already been invoiced.'))
        if not self.partner_id or not self.amount:
            raise UserError(_('Set the vendor and amount before invoicing.'))
        line_vals = {
            'name': _('External maintenance - %(product)s (%(ref)s)',
                      product=self.product_id.display_name, ref=self.name),
            'quantity': 1.0,
            'price_unit': self.amount,
        }
        expense_account = self.company_id.maintenance_expense_account_id
        if not expense_account:
            raise UserError(_(
                'Set the "Spare Parts Expense Account" in the settings of company %s before creating the vendor bill.',
                self.company_id.name))
        line_vals['account_id'] = expense_account.id
        if self.fleet_id.analytic_account_id:
            line_vals['analytic_distribution'] = {str(self.fleet_id.analytic_account_id.id): 100.0}
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': [Command.create(line_vals)],
        })
        self.invoice_id = bill
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_in_invoice_type')
        action.update({'views': [(False, 'form')], 'res_id': bill.id})
        return action
