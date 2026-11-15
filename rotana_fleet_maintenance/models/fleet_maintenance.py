# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class RotanaMaintenanceRequest(models.Model):
    _name = 'rotana.maintenance.request'
    _description = 'Rotana Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'product.catalog.mixin']
    _order = 'id desc'

    # ------------------------------------------------------------------
    # Request data (job card)
    # ------------------------------------------------------------------
    name = fields.Char(string='Subject', required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    fleet_id = fields.Many2one(
        'fleet.vehicle', string='Unit (Vehicle)', required=True, tracking=True, index=True)
    unit_number = fields.Char(related='fleet_id.unit_number', string='Unit Number')
    license_plate = fields.Char(related='fleet_id.license_plate', string='License Plate')
    driver_id = fields.Many2one(
        'res.partner', string='Driver',
        compute='_compute_driver_id', store=True, readonly=False, tracking=True)
    odometer = fields.Float(string='Odometer', tracking=True)
    request_date = fields.Date(
        string='Date', default=fields.Date.context_today, required=True, tracking=True)
    entry_datetime = fields.Datetime(
        string='Entry Time', default=fields.Datetime.now, tracking=True)
    exit_datetime = fields.Datetime(string='Exit Time', tracking=True, copy=False)
    downtime_hours = fields.Float(
        string='Downtime', compute='_compute_downtime_hours', store=True,
        help='Difference between the entry time and the exit time, in hours.')
    stage_id = fields.Many2one(
        'rotana.maintenance.stage', string='Stage', tracking=True, copy=False, index=True,
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_ids', ondelete='restrict')
    inspector_id = fields.Many2one('res.users', string='Inspection Engineer', tracking=True)
    odometer_log_id = fields.Many2one(
        'fleet.vehicle.odometer', string='Odometer Log', copy=False, readonly=True,
        ondelete='set null',
        help='Odometer log created on the vehicle when the request is completed.')
    description = fields.Html(string='Notes')
    work_ids = fields.One2many(
        'rotana.maintenance.work', 'request_id', string='Works', copy=True)

    @api.model
    def _default_stage_id(self):
        return self.env['rotana.maintenance.stage'].search([], order='sequence, id', limit=1)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order=stages._order)

    @api.depends('fleet_id')
    def _compute_driver_id(self):
        for request in self:
            if request.fleet_id.driver_id:
                request.driver_id = request.fleet_id.driver_id
            elif not request.driver_id:
                request.driver_id = False

    @api.depends('entry_datetime', 'exit_datetime')
    def _compute_downtime_hours(self):
        for request in self:
            if request.entry_datetime and request.exit_datetime:
                delta = request.exit_datetime - request.entry_datetime
                request.downtime_hours = max(delta.total_seconds(), 0.0) / 3600.0
            else:
                request.downtime_hours = 0.0

    @api.constrains('entry_datetime', 'exit_datetime')
    def _check_entry_exit(self):
        for request in self:
            if request.entry_datetime and request.exit_datetime \
                    and request.exit_datetime < request.entry_datetime:
                raise ValidationError(_('The exit time cannot be before the entry time.'))

    # ------------------------------------------------------------------
    # Spare parts
    # ------------------------------------------------------------------
    part_line_ids = fields.One2many(
        'rotana.maintenance.part', 'request_id', string='Spare Parts', copy=True)
    parts_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('done', 'Done'),
        ],
        string='Spare Parts Status', default='draft', copy=False, tracking=True,
    )
    # The Odoo product catalog (JS) reads the "state" field of the parent record,
    # so it is exposed as a copy of the spare parts status.
    state = fields.Selection(related='parts_state', string='Status')
    currency_id = fields.Many2one(related='company_id.currency_id')
    parts_total = fields.Monetary(compute='_compute_parts_total', string='Spare Parts Total')
    picking_ids = fields.One2many(
        'stock.picking', 'rotana_request_id', string='Delivery Orders', copy=False)
    workshop_ids = fields.One2many(
        'rotana.external.workshop', 'maintenance_request_id',
        string='External Maintenance Requests', copy=False)
    parts_move_id = fields.Many2one(
        'account.move', string='Spare Parts Entry', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Expenses during maintenance
    # ------------------------------------------------------------------
    expense_ids = fields.One2many(
        'rotana.maintenance.expense', 'request_id', string='Expenses', copy=False)
    expenses_total = fields.Monetary(compute='_compute_expenses_total', string='Expenses Total')
    expense_move_ids = fields.Many2many(
        'account.move', compute='_compute_expense_move_ids', compute_sudo=True, string='Expense Bills')

    @api.depends('expense_ids.amount')
    def _compute_expenses_total(self):
        for request in self:
            request.expenses_total = sum(request.expense_ids.mapped('amount'))

    @api.depends('expense_ids.move_id')
    def _compute_expense_move_ids(self):
        for request in self:
            request.expense_move_ids = request.expense_ids.move_id

    def action_create_expense_bills(self):
        """ Convert the not-yet-invoiced expenses into vendor bills (draft),
        one bill per vendor, linked to the vehicle analytic account. """
        self.ensure_one()
        self._check_analytic_account()
        lines = self.expense_ids.filtered(lambda e: not e.move_id)
        if not lines:
            raise UserError(_('There are no new expenses to invoice.'))
        missing = lines.filtered(lambda e: not e.partner_id)
        if missing:
            raise UserError(_(
                'Set the vendor of the following expenses before creating the bills:\n%s',
                '\n'.join('- %s' % (e.name or '') for e in missing)))
        no_account = lines.filtered(lambda e: not e.account_id)
        if no_account:
            raise UserError(_(
                'Set the expense account of the following expenses before creating the bills:\n%s',
                '\n'.join('- %s' % (e.name or '') for e in no_account)))
        analytic = {str(self.fleet_id.analytic_account_id.id): 100.0}
        bills = self.env['account.move']
        for partner in lines.partner_id:
            partner_lines = lines.filtered(lambda e: e.partner_id == partner)
            bill = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': partner.id,
                'company_id': self.company_id.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': self.name,
                'invoice_line_ids': [Command.create({
                    'name': e.name,
                    'quantity': 1.0,
                    'price_unit': e.amount,
                    'account_id': e.account_id.id,
                    'analytic_distribution': analytic,
                }) for e in partner_lines],
            })
            partner_lines.move_id = bill
            bills |= bill
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_in_invoice_type')
        if len(bills) == 1:
            action.update({'views': [(False, 'form')], 'res_id': bills.id})
        else:
            action['domain'] = [('id', 'in', bills.ids)]
        return action

    @api.depends('part_line_ids.subtotal')
    def _compute_parts_total(self):
        for request in self:
            request.parts_total = sum(request.part_line_ids.mapped('subtotal'))

    # ------------------------------------------------------------------
    # Product catalog (same mechanism as industry_fsm_sale)
    # ------------------------------------------------------------------
    def action_add_from_catalog(self):
        action = super().action_add_from_catalog()
        kanban_view = self.env.ref('rotana_fleet_maintenance.maintenance_part_product_catalog_kanban_view')
        search_view = self.env.ref('rotana_fleet_maintenance.maintenance_part_product_catalog_search_view')
        action['name'] = _('Spare Parts')
        action['search_view_id'] = [search_view.id, 'search']
        action['views'] = [(kanban_view.id, 'kanban'), (False, 'form')]
        return action

    def _get_action_add_from_catalog_extra_context(self):
        # The catalog UI (JS) reads order_id from the context to call the controller,
        # plus the currency and number precision used to display the price.
        return {
            **super()._get_action_add_from_catalog_extra_context(),
            'order_id': self.id,
            'product_catalog_currency_id': self.company_id.currency_id.id,
            'product_catalog_digits': [16, self.env['decimal.precision'].precision_get('Product Price')],
        }

    def _get_product_catalog_domain(self):
        # Spare parts = storable products only
        return super()._get_product_catalog_domain() & Domain([
            ('type', '=', 'consu'),
            ('is_storable', '=', True),
        ])

    def _is_readonly(self):
        self.ensure_one()
        return self.parts_state != 'draft' or (not self.active)

    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        grouped_lines = defaultdict(lambda: self.env['rotana.maintenance.part'])
        for line in self.part_line_ids:
            if line.product_id.id in product_ids:
                grouped_lines[line.product_id] |= line
        return grouped_lines

    def _get_product_catalog_order_data(self, products, **kwargs):
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            res[product.id]['price'] = product.with_company(self.company_id).standard_price
        return res

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        self.ensure_one()
        product = self.env['product.product'].browse(product_id)
        line = self.part_line_ids.filtered(lambda l: l.product_id.id == product_id)
        if line:
            if quantity > 0:
                line.quantity = quantity
            else:
                line.unlink()
        elif quantity > 0:
            self.env['rotana.maintenance.part'].create({
                'request_id': self.id,
                'product_id': product_id,
                'quantity': quantity,
            })
        return product.with_company(self.company_id).standard_price

    # ------------------------------------------------------------------
    # Confirmation: delivery order + analytic account
    # ------------------------------------------------------------------
    def action_confirm_parts(self):
        for request in self:
            if request.parts_state != 'draft':
                continue
            if not request.fleet_id:
                raise UserError(_('Select the vehicle first before confirming.'))
            # The request can be confirmed without spare parts.
            if request.part_line_ids:
                request._check_analytic_account()
                receipt_groups = request._get_receipt_groups()
                request._create_parts_picking()
                request._create_parts_receipts(receipt_groups)
                request._create_workshop_requests()
            request.parts_state = 'confirmed'
        return True

    def action_reset_parts(self):
        """ Reset the confirmation: cancels the delivery orders not yet done and sets the request back to draft. """
        for request in self:
            if request.parts_state != 'confirmed':
                continue
            if request.picking_ids.filtered(lambda p: p.state == 'done'):
                raise UserError(_('The confirmation cannot be reset because the delivery order is already done.'))
            workshops = request.workshop_ids.filtered('part_line_id')
            sent = workshops.filtered(lambda w: w.state not in ('draft', 'confirmed'))
            if sent:
                raise UserError(_(
                    'The confirmation cannot be reset because the following workshop requests already entered the workshop:\n%s',
                    '\n'.join('- %s' % w.name for w in sent)))
            workshops.sudo().unlink()
            request.picking_ids.filtered(
                lambda p: p.state != 'cancel' and p.company_id == request.company_id
            ).with_company(request.company_id).sudo().action_cancel()
            request.parts_state = 'draft'
        return True

    def _check_analytic_account(self):
        self.ensure_one()
        self.fleet_id._ensure_analytic_account()
        if not self.fleet_id.analytic_account_id:
            raise UserError(_('There is no analytic account linked to this vehicle.'))

    def _create_parts_picking(self):
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].with_company(self.company_id).search(
            [('company_id', '=', self.company_id.id)], limit=1)
        # Default operation type from the maintenance settings, otherwise the delivery type of the warehouse
        picking_type = self.company_id.maintenance_out_picking_type_id or warehouse.out_type_id
        if not picking_type:
            raise UserError(_('There is no warehouse with a "Delivery" operation type for company %s.', self.company_id.name))
        src_location = picking_type.default_location_src_id
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            # 'location_id': src_location.id,
            # 'location_dest_id': dest_location.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'rotana_request_id': self.id,
            'fleet_id': self.fleet_id.id,
            'move_ids': [Command.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'rotana_part_id': line.id,
                'location_id': src_location.id,
                'company_id': self.company_id.id,
            }) for line in self.part_line_ids],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _create_workshop_requests(self):
        """ Spare part maintenance request (draft) for every spare line whose state is rehabilitation. """
        self.ensure_one()
        Workshop = self.env['rotana.external.workshop'].sudo()
        for line in self.part_line_ids.filtered(lambda l: l.spare_state == 'rehab'):
            if Workshop.search_count([('part_line_id', '=', line.id)]):
                continue
            Workshop.create({
                'maintenance_request_id': self.id,
                'fleet_id': self.fleet_id.id,
                'part_line_id': line.id,
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'company_id': self.company_id.id,
                'picking_type_id': (line.picking_type_id
                                    or self.company_id.maintenance_rehab_picking_type_id).id,
            })

    def _get_receipt_lines(self):
        """ Lines for which a receipt is issued on confirmation (for extension by other modules). """
        self.ensure_one()
        # Rehabilitation lines get no receipt: an external maintenance request is created instead
        return self.part_line_ids.filtered(lambda l: l.spare_state != 'rehab')

    def _get_receipt_groups(self):
        """ Group the spare part lines by receipt operation type (scrap / rehabilitation). """
        self.ensure_one()
        company = self.company_id
        groups = defaultdict(lambda: self.env['rotana.maintenance.part'])
        for line in self._get_receipt_lines():
            picking_type = line.picking_type_id or (
                company.maintenance_rehab_picking_type_id if line.spare_state == 'rehab'
                else company.maintenance_scrap_picking_type_id)
            if not picking_type:
                raise UserError(_(
                    'Set the operation type of the part "%(product)s" or set the "Scrap / Rehabilitation Operation Type" '
                    'in the settings of company %(company)s.',
                    product=line.product_id.display_name, company=company.name))
            groups[picking_type] |= line
        return groups

    def _create_parts_receipts(self, groups):
        """ One receipt per operation type (scrap / rehabilitation) holding the lines of that type. """
        self.ensure_one()
        pickings = self.env['stock.picking']
        for picking_type, lines in groups.items():
            src_location = picking_type.default_location_src_id
            move_vals = []
            for line in lines:
                vals = {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'company_id': self.company_id.id,
                }
                if src_location:
                    vals['location_id'] = src_location.id
                move_vals.append(Command.create(vals))
            picking = self.env['stock.picking'].sudo().create({
                'picking_type_id': picking_type.id,
                'origin': self.name,
                'company_id': self.company_id.id,
                'rotana_request_id': self.id,
                'fleet_id': self.fleet_id.id,
                'move_ids': move_vals,
            })
            picking.action_confirm()
            picking.action_assign()
            pickings |= picking
        return pickings

    # ------------------------------------------------------------------
    # Completion: journal entry decreasing the stock value
    # ------------------------------------------------------------------
    def write(self, vals):
        completing = self.browse()
        if vals.get('stage_id') and self.env['rotana.maintenance.stage'].browse(vals['stage_id']).done:
            completing = self.filtered(lambda r: not r.stage_id.done)
            completing._check_parts_before_done()
        res = super().write(vals)
        if completing:
            completing.filtered(lambda r: not r.exit_datetime).write(
                {'exit_datetime': fields.Datetime.now()})
            completing._create_parts_journal_entry()
            completing._update_vehicle_odometer()
        return res

    def _update_vehicle_odometer(self):
        """ When the vehicle is repaired, record the odometer reading of the request on the
        vehicle, dated with the entry date. The log is created once per request. """
        Odometer = self.env['fleet.vehicle.odometer'].sudo()
        for request in self.filtered(lambda r: r.odometer > 0 and r.fleet_id):
            if request.entry_datetime:
                date = fields.Datetime.context_timestamp(request, request.entry_datetime).date()
            else:
                date = request.request_date
            vals = {'vehicle_id': request.fleet_id.id, 'value': request.odometer, 'date': date}
            if request.odometer_log_id:
                request.odometer_log_id.sudo().write(vals)
            else:
                request.odometer_log_id = Odometer.create(vals)

    def _check_parts_before_done(self):
        """ The request cannot be completed before the spare parts are confirmed and the delivery orders are done. """
        for request in self.filtered('part_line_ids'):
            if request.parts_state == 'draft':
                raise UserError(_('Confirm the spare parts (issue the delivery order) before completing the request "%s".', request.name))
            if request.parts_state == 'confirmed':
                pickings = request.picking_ids.filtered(lambda p: p.state != 'cancel')
                if not pickings or any(p.state != 'done' for p in pickings):
                    raise UserError(_(
                        'The request "%s" cannot be completed before the spare parts delivery order is done.', request.name))

    def _get_parts_entry_date(self, moves):
        """ Date of the spare parts entry = date the delivery was done, not today's date. """
        dates = [d.date() if hasattr(d, 'date') else d for d in moves.mapped('date') if d]
        return max(dates) if dates else fields.Date.context_today(self)

    def _create_parts_journal_entry(self):
        for request in self.filtered(lambda r: r.parts_state == 'confirmed' and not r.parts_move_id):
            request = request.with_company(request.company_id)
            company = request.company_id
            currency = company.currency_id
            moves = request.picking_ids.filtered(
                lambda p: p.state == 'done' and p.picking_type_code != 'incoming') \
                .sudo().move_ids.filtered(lambda m: m.state == 'done')

            debit_by_account = defaultdict(float)
            credit_by_account = defaultdict(float)
            for move in moves:
                if move.account_move_id:
                    # Odoo 19 already created the valuation entry of this move when it was done (product with Perpetual valuation
                    # and a valuation account on one of the locations); posting a manual entry here would duplicate the cost.
                    continue
                amount = currency.round(abs(move.value))
                if currency.is_zero(amount):
                    continue
                accounts = move.product_id.with_company(company)._get_product_accounts()
                expense_account = company.maintenance_expense_account_id or accounts['expense']
                if not expense_account:
                    raise UserError(_(
                        'Set the "Spare Parts Expense Account" in the company settings or the expense account on the product category %s.',
                        move.product_id.categ_id.display_name))
                debit_by_account[expense_account] += amount
                credit_by_account[accounts['stock_valuation']] += amount

            if debit_by_account:
                journal = company.maintenance_journal_id or self.env['account.journal'].sudo().search(
                    [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
                if not journal:
                    raise UserError(_('There is no journal of type "Miscellaneous" for company %s.', company.name))
                label = _('Spare parts - %s - %s', request.fleet_id.display_name, request.name)
                analytic = {str(request.fleet_id.analytic_account_id.id): 100.0} if request.fleet_id.analytic_account_id else False
                line_vals = [Command.create({
                    'name': label,
                    'account_id': account.id,
                    'debit': amount,
                    'credit': 0.0,
                    'analytic_distribution': analytic,
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
                    'date': request._get_parts_entry_date(moves),
                    'ref': label,
                    'line_ids': line_vals,
                })
                account_move._post()
                request.parts_move_id = account_move
            request.parts_state = 'done'
