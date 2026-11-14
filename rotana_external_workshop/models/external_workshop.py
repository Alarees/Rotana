# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# حقول لا تُعدَّل بعد دخول الورشة
LOCKED_FIELDS = {'maintenance_request_id', 'fleet_id', 'product_id', 'quantity', 'picking_type_id'}
# المورد والمبلغ: يُعدَّلان في (في الورشة) و(تمت الصيانة) إلى أن تتم الفوترة
FINANCIAL_FIELDS = {'partner_id', 'amount'}


class RotanaExternalWorkshop(models.Model):
    _name = 'rotana.external.workshop'
    _description = 'طلب صيانة اسبير (الورشة الخارجية)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='الرقم', default='/', readonly=True, copy=False)
    maintenance_request_id = fields.Many2one(
        'maintenance.request', string='رقم الصيانة', index=True,
        ondelete='set null', copy=False)
    fleet_id = fields.Many2one(
        'fleet.vehicle', string='رقم المركبة', index=True,
        compute='_compute_fleet_id', store=True, readonly=False)
    part_line_id = fields.Many2one(
        'maintenance.request.part', string='سطر الاسبير في الصيانة',
        copy=False, index='btree_not_null', ondelete='set null')
    product_id = fields.Many2one(
        'product.product', string='الاسبير', required=True, tracking=True,
        domain="[('type', '=', 'consu'), ('is_storable', '=', True)]")
    quantity = fields.Float(string='الكمية', default=1.0, required=True)
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='المورد', tracking=True)
    amount = fields.Monetary(string='المبلغ', tracking=True)
    state = fields.Selection(
        [
            ('draft', 'مسودة'),
            ('confirmed', 'مؤكد'),
            ('in_workshop', 'في الورشة'),
            ('done', 'تمت الصيانة'),
        ],
        string='الحالة', default='draft', required=True, readonly=True, copy=False, tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='فاتورة المورد', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null')
    invoice_state = fields.Selection(
        [('not_invoiced', 'لم تتم الفوترة'), ('invoiced', 'تمت الفوترة')],
        string='حالة الفوترة', compute='_compute_invoice_state', store=True, default='not_invoiced')
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='نوع العملية',
        compute='_compute_picking_type_id', store=True, readonly=False, precompute=True,
        domain="[('code', '=', 'incoming'), ('company_id', '=', company_id)]")
    picking_id = fields.Many2one(
        'stock.picking', string='إذن الاستلام', copy=False, readonly=True,
        ondelete='set null', index='btree_not_null')
    settlement_move_id = fields.Many2one(
        'account.move', string='قيد تسوية المخزن', copy=False, readonly=True,
        ondelete='set null')

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
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
                raise ValidationError(_('كمية الاسبير يجب أن تكون أكبر من صفر.'))

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
        """ ترقيم مستقل لكل شركة: يُنشأ تسلسل الشركة عند أول استخدام. """
        Sequence = self.env['ir.sequence'].sudo()
        code = 'rotana.external.workshop'
        sequence = Sequence.search([('code', '=', code), ('company_id', '=', company_id)], limit=1)
        if not sequence:
            sequence = Sequence.create({
                'name': _('الورشة الخارجية'), 'code': code, 'prefix': 'EW/',
                'padding': 5, 'company_id': company_id,
            })
        return sequence.next_by_id()

    def write(self, vals):
        keys = set(vals)
        if keys & LOCKED_FIELDS and any(r.state not in ('draft', 'confirmed') for r in self):
            raise UserError(_('لا يمكن تعديل بيانات الطلب بعد إرساله إلى الورشة.'))
        if keys & FINANCIAL_FIELDS:
            if any(r.state not in ('in_workshop', 'done') for r in self):
                raise UserError(_('المورد والمبلغ يُحدَّدان في حالة (في الورشة) أو (تمت الصيانة) فقط.'))
            if any(r.invoice_state == 'invoiced' for r in self):
                raise UserError(_('لا يمكن تعديل المورد أو المبلغ بعد الفوترة.'))
        return super().write(vals)

    def unlink(self):
        if any(r.state not in ('draft', 'confirmed') for r in self):
            raise UserError(_('لا يمكن حذف طلب دخل الورشة.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # أزرار تغيير الحالة
    # ------------------------------------------------------------------
    def _check_workshop_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group('rotana_external_workshop.group_external_workshop_manager'):
            raise UserError(_('هذا الإجراء متاح لمدير الورشة الخارجية فقط.'))

    def action_confirm(self):
        self._check_workshop_manager()
        for rec in self.filtered(lambda r: r.state == 'draft'):
            if not rec.product_id or rec.quantity <= 0:
                raise UserError(_('حدد الاسبير والكمية قبل التأكيد.'))
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
                raise UserError(_('حدد المورد للطلب %s قبل تمت الصيانة.', rec.name))
            if not rec.amount:
                raise UserError(_('حدد المبلغ للطلب %s قبل تمت الصيانة.', rec.name))
            if not rec.picking_type_id:
                raise UserError(_(
                    'حدد نوع العملية للطلب %s أو حدد \"عملية التأهيل\" في إعدادات الشركة.', rec.name))
            if rec.picking_type_id.code != 'incoming':
                raise UserError(_('نوع العملية يجب أن يكون استلاماً.'))
            rec._create_receipt()
            rec._create_settlement_entry()
            rec.state = 'done'
        return True

    # ------------------------------------------------------------------
    # إذن الاستلام (غير مربوط بطلب الصيانة ولا بالمورد)
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
            raise UserError(_('تعذر تأكيد إذن الاستلام %s آلياً، راجع الإذن.', picking.name))
        self.picking_id = picking
        return picking

    # ------------------------------------------------------------------
    # قيد تسوية قيمة المخزن بقيمة الاسبير فقط (دون زيادة مبلغ الصيانة)
    # إذن الاستلام يرفع المخزن مقابل حساب تقييم الموقع المصدر؛ القيد يُغلق
    # هذا الحساب مقابل حساب المصروف الذي حُمِّل به الاسبير عند التسليم.
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
                    'لا يمكن تسجيل قيد التسوية: الموقع \"%(location)s\" ليس له حساب تقييم مخزون. '
                    'حدد الحساب في الموقع ثم أعد المحاولة.',
                    location=move.location_id.display_name))
            amount = currency.round(abs(move.value))
            if currency.is_zero(amount):
                continue
            accounts = move.product_id.with_company(company)._get_product_accounts()
            expense_account = company.maintenance_expense_account_id or accounts['expense']
            if not expense_account:
                raise UserError(_(
                    'حدد \"حساب مصروف قطع الغيار\" في إعدادات الشركة أو حساب المصروف في فئة المنتج %s.',
                    move.product_id.categ_id.display_name))
            debit_by_account[valuation_account] += amount
            credit_by_account[expense_account] += amount
        if not debit_by_account:
            return False
        journal = company.maintenance_journal_id or self.env['account.journal'].sudo().search(
            [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('لا يوجد دفتر يومية من النوع \"متنوع\" للشركة %s.', company.name))
        label = _('تسوية قيمة اسبير - %s', self.name)
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
    # الفوترة (فاتورة مورد مربوطة بالحساب التحليلي للمركبة)
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        self.ensure_one()
        self._check_workshop_manager()
        if self.state != 'done':
            raise UserError(_('الفوترة متاحة بعد (تمت الصيانة) فقط.'))
        if self.invoice_state == 'invoiced':
            raise UserError(_('تمت فوترة هذا الطلب مسبقاً.'))
        if not self.partner_id or not self.amount:
            raise UserError(_('حدد المورد والمبلغ قبل الفوترة.'))
        line_vals = {
            'name': _('صيانة خارجية - %(product)s (%(ref)s)',
                      product=self.product_id.display_name, ref=self.name),
            'quantity': 1.0,
            'price_unit': self.amount,
        }
        expense_account = self.company_id.maintenance_expense_account_id
        if not expense_account:
            raise UserError(_(
                'حدد \"حساب مصروف قطع الغيار\" في إعدادات الشركة %s قبل إنشاء فاتورة المورد.',
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
