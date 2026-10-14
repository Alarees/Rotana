# -*- coding: utf-8 -*-
"""عهدة رحلة النقل (rotana.transport.trip.custody).

دورة العهدة:
    مسودة -> مؤكدة -> مدفوعة -> منتهية

القيود (حساب العهدة = Custody Payable، الشريك = السائق):
- تأكيد : تغيير حالة فقط (لا قيد).
- دفع   : دفعة قياسية للسائق (من البنك / إلى حساب العهدة): العهدة مدين / البنك دائن.
          وتنتقل العهدة إلى (مدفوعة) عند ترحيل الدفعة بالكامل.
- إنهاء : قيد يومية: المصروفات مدين (موزعة تحليلياً على حساب الرحلة) / العهدة دائن.
- الفرق : المصروف أقل من العهدة -> دفعية على السائق (البنك مدين / العهدة دائن).
          المصروف أكبر من العهدة -> دفعية للسائق (العهدة مدين / البنك دائن).
- الإلغاء : حذف القيود والدفعات وإعادة العهدة إلى مسودة.
"""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CUSTODY_STATES = [
    ('draft', 'مسودة'),
    ('confirmed', 'مؤكدة'),
    ('paid', 'مدفوعة'),
    ('done', 'منتهية'),
]


class RotanaTransportTripCustody(models.Model):
    _name = 'rotana.transport.trip.custody'
    _description = 'عهدة رحلة النقل'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='رقم العهدة',
        default=lambda self: _('جديد'),
        readonly=True,
        copy=False,
        index=True,
    )
    state = fields.Selection(
        CUSTODY_STATES,
        string='الحالة',
        default='draft',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )
    trip_id = fields.Many2one(
        'rotana.transport.trip',
        string='الرحلة',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    sale_order_id = fields.Many2one(
        related='trip_id.sale_order_id',
        string='أمر البيع',
    )
    vehicle_id = fields.Many2one(
        related='trip_id.vehicle_id',
        string='المركبة',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='السائق',
        compute='_compute_partner_id',
        store=True,
        readonly=False,
        required=True,
        tracking=True,
    )
    date = fields.Date(
        string='التاريخ',
        default=fields.Date.context_today,
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='العملة',
    )
    amount = fields.Monetary(
        string='مبلغ العهدة',
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        'rotana.transport.trip.custody.line',
        'custody_id',
        string='سطور التصفية',
    )
    spent_amount = fields.Monetary(
        string='إجمالي المصروف',
        compute='_compute_amounts',
        store=True,
    )
    difference_amount = fields.Monetary(
        string='فرق التصفية',
        compute='_compute_amounts',
        store=True,
        help='مبلغ العهدة - إجمالي المصروف. الموجب: على السائق، السالب: للسائق.',
    )
    paid_amount = fields.Monetary(
        string='المدفوع للسائق',
        compute='_compute_paid_amount',
        help='مجموع دفعات العهدة المرحّلة.',
    )
    remaining_amount = fields.Monetary(
        string='المتبقي بعد الدفعات',
        compute='_compute_remaining',
        help='المدفوع - المصروف، بعد خصم دفعيات التسوية المرحّلة.',
    )
    settle_direction = fields.Selection(
        [('inbound', 'على السائق'), ('outbound', 'للسائق')],
        string='اتجاه التسوية',
        compute='_compute_remaining',
    )
    done_move_id = fields.Many2one(
        'account.move',
        string='قيد التصفية',
        readonly=True,
        copy=False,
    )
    payment_ids = fields.One2many(
        'account.payment',
        'custody_id',
        string='الدفعات',
    )
    notes = fields.Text(string='ملاحظات')

    # ==============================
    # الحقول المحسوبة
    # ==============================

    @api.depends('trip_id.driver_id')
    def _compute_partner_id(self):
        for custody in self:
            custody.partner_id = custody.trip_id.driver_id

    @api.depends('amount', 'line_ids.amount')
    def _compute_amounts(self):
        for custody in self:
            spent = sum(custody.line_ids.mapped('amount'))
            custody.spent_amount = spent
            custody.difference_amount = custody.amount - spent

    @api.depends(
        'payment_ids.state', 'payment_ids.amount',
        'payment_ids.payment_type', 'payment_ids.custody_payment_kind',
    )
    def _compute_paid_amount(self):
        for custody in self:
            advances = custody.payment_ids.filtered(
                lambda pay: pay.custody_payment_kind == 'advance'
                and pay.state in ('in_process', 'paid')
            )
            custody.paid_amount = sum(
                pay.amount if pay.payment_type == 'outbound' else -pay.amount
                for pay in advances
            )

    @api.depends(
        'state', 'paid_amount', 'spent_amount',
        'payment_ids.state', 'payment_ids.amount',
        'payment_ids.payment_type', 'payment_ids.custody_payment_kind',
    )
    def _compute_remaining(self):
        for custody in self:
            remaining = 0.0
            if custody.state == 'done':
                remaining = custody.paid_amount - custody.spent_amount
                settled = custody.payment_ids.filtered(
                    lambda pay: pay.custody_payment_kind == 'settlement'
                    and pay.state in ('in_process', 'paid')
                )
                for pay in settled:
                    # دفعية للسائق تقلل ما له، ودفعية منه تقلل ما عليه
                    remaining += pay.amount if pay.payment_type == 'outbound' else -pay.amount
            currency = custody.currency_id
            if currency:
                remaining = currency.round(remaining)
            custody.remaining_amount = remaining
            if currency and currency.is_zero(remaining):
                custody.settle_direction = False
            else:
                custody.settle_direction = 'inbound' if remaining > 0 else 'outbound'

    @api.constrains('amount')
    def _check_amount(self):
        for custody in self:
            if custody.amount <= 0:
                raise ValidationError(_('مبلغ العهدة يجب أن يكون أكبر من صفر.'))

    # ==============================
    # دورة الحياة
    # ==============================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rotana.transport.trip.custody'
                ) or _('جديد')
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_draft(self):
        if any(custody.state != 'draft' for custody in self):
            raise UserError(_(
                'لا يمكن حذف عهدة غير مسودة. استخدم (إلغاء وإعادة لمسودة) أولاً.'
            ))

    # ==============================
    # مساعدات
    # ==============================

    def _get_custody_settings(self):
        """حساب العهدة ودفتر اليومية من إعدادات الشركة."""
        self.ensure_one()
        company = self.company_id
        account = company.custody_account_id
        journal = company.custody_journal_id
        if not account or not journal:
            raise UserError(_(
                'حدّد حساب العهدة ودفتر يومية العهد في إعدادات نقل روتانا (العهد المالية).'
            ))
        if account.account_type not in ('liability_payable', 'asset_receivable'):
            raise UserError(_(
                'حساب العهدة يجب أن يكون من نوع (دائنة / Payable) أو (مدينة / Receivable) '
                'ليعمل مع الدفعات والتسوية القياسية.'
            ))
        return account, journal

    def _get_move_label(self):
        self.ensure_one()
        return _(
            'عهدة %(name)s - رحلة %(trip)s',
            name=self.name,
            trip=self.trip_id.manifest_number,
        )

    # ==============================
    # الأزرار
    # ==============================

    def action_confirm(self):
        """تأكيد: تغيير الحالة فقط (القيد المحاسبي هو قيد الدفعة)."""
        for custody in self:
            if custody.state != 'draft':
                raise UserError(_('العهدة %s ليست في حالة مسودة.', custody.name))
            # التحقق المبكر من إعدادات الحساب ودفتر اليومية
            custody._get_custody_settings()
            custody.state = 'confirmed'
        return True

    def _create_custody_payment(self, kind, payment_type, amount):
        """إنشاء دفعة قياسية (مسودة) على حساب العهدة وشريك السائق."""
        self.ensure_one()
        account, __ = self._get_custody_settings()
        return self.env['account.payment'].create({
            'payment_type': payment_type,
            'partner_type': (
                'supplier' if account.account_type == 'liability_payable' else 'customer'
            ),
            'partner_id': self.partner_id.id,
            'amount': amount,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'memo': self._get_move_label(),
            'custody_id': self.id,
            'custody_payment_kind': kind,
        })

    def _open_payment(self, payment):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_register_payment(self):
        """إنشاء دفعة قياسية للسائق بالمتبقي من العهدة وفتحها لاختيار الدفتر وترحيلها."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('تسجيل الدفعة متاح للعهدة المؤكدة فقط.'))
        draft = self.payment_ids.filtered(
            lambda pay: pay.custody_payment_kind == 'advance' and pay.state == 'draft'
        )
        if draft:
            return self._open_payment(draft[:1])
        due = self.amount - self.paid_amount
        if self.currency_id.compare_amounts(due, 0) <= 0:
            raise UserError(_('لا يوجد مبلغ متبقٍ للدفع على هذه العهدة.'))
        return self._open_payment(self._create_custody_payment('advance', 'outbound', due))

    def _after_payment_posted(self):
        """يُستدعى بعد ترحيل دفعة عهدة: تحويل الحالة لمدفوعة وتسوية سطور الحساب."""
        for custody in self:
            if (
                custody.state == 'confirmed'
                and custody.currency_id.compare_amounts(
                    custody.paid_amount, custody.amount
                ) >= 0
            ):
                custody.state = 'paid'
            custody._reconcile_custody_lines()

    def action_done(self):
        """إنهاء: قيد (المصروفات مدين موزعة تحليلياً / العهدة دائن) بإجمالي السطور."""
        for custody in self:
            if custody.state != 'paid':
                raise UserError(_('إنهاء العهدة %s متاح للعهدة المدفوعة فقط.', custody.name))
            if not custody.line_ids:
                raise UserError(_('أضف سطور المصروفات الفعلية قبل الإنهاء.'))
            analytic = custody.trip_id.account_analytic_id
            if not analytic:
                raise UserError(_(
                    'الرحلة %s ليس لها حساب تحليلي (يُنشأ عند تأكيد الرحلة).',
                    custody.trip_id.manifest_number,
                ))
            account, journal = custody._get_custody_settings()
            partner = custody.partner_id
            move_lines = []
            for line in custody.line_ids:
                expense = line.product_id.product_tmpl_id.with_company(
                    custody.company_id
                )._get_product_accounts()['expense']
                if not expense:
                    raise UserError(_(
                        'لا يوجد حساب مصروف للمنتج %s (على المنتج أو فئته).',
                        line.product_id.display_name,
                    ))
                move_lines.append(Command.create({
                    'account_id': expense.id,
                    'partner_id': partner.id,
                    'name': line.name or line.product_id.display_name,
                    'debit': line.amount,
                    'credit': 0.0,
                    'analytic_distribution': {str(analytic.id): 100},
                }))
            move_lines.append(Command.create({
                'account_id': account.id,
                'partner_id': partner.id,
                'name': custody._get_move_label(),
                'debit': 0.0,
                'credit': custody.spent_amount,
            }))
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'company_id': custody.company_id.id,
                'date': fields.Date.context_today(custody),
                'ref': custody.name,
                'line_ids': move_lines,
            })
            move.action_post()
            custody.write({'done_move_id': move.id, 'state': 'done'})
            custody._reconcile_custody_lines()
        return True

    def action_settlement_payment(self):
        """دفعية فرق التصفية: للسائق (إن زاد المصروف) أو عليه (إن زادت العهدة)."""
        self.ensure_one()
        if self.state != 'done' or not self.settle_direction:
            raise UserError(_('لا يوجد فرق تصفية مفتوح لهذه العهدة.'))
        draft = self.payment_ids.filtered(
            lambda pay: pay.custody_payment_kind == 'settlement' and pay.state == 'draft'
        )
        payment = draft[:1] or self._create_custody_payment(
            'settlement', self.settle_direction, abs(self.remaining_amount)
        )
        return self._open_payment(payment)

    def _reconcile_custody_lines(self):
        """تسوية سطور حساب العهدة (دفعات العهدة مع قيد التصفية ودفعيات الفرق)."""
        for custody in self:
            account = custody.company_id.custody_account_id
            if not account or not account.reconcile:
                continue
            moves = (
                custody.done_move_id
                | custody.payment_ids.filtered('custody_payment_kind').move_id
            )
            lines = moves.line_ids.filtered(
                lambda line: line.account_id == account
                and not line.reconciled
                and line.parent_state == 'posted'
            )
            if len(lines) > 1:
                try:
                    with self.env.cr.savepoint():
                        lines.reconcile()
                except UserError:
                    # تسوية القيود اختيارية ولا تمنع إكمال العهدة
                    pass

    # ==============================
    # الإلغاء وإعادة لمسودة
    # ==============================

    def action_cancel_reset(self):
        """حذف القيود والدفعات وإعادة العهدة إلى مسودة."""
        for custody in self:
            if custody.state == 'draft':
                continue
            cancelled = custody._wipe_accounting()
            custody.write({
                'state': 'draft',
                'done_move_id': False,
            })
            body = _('تم حذف القيود والدفعات وإعادة العهدة إلى مسودة.')
            if cancelled:
                body += ' ' + _(
                    'تعذر حذف بعض القيود حسب قواعد المحاسبة فتم إلغاؤها: %s',
                    '، '.join(cancelled.mapped('name')),
                )
            custody.message_post(body=body)
        return True

    def _wipe_accounting(self):
        """يحذف الدفعات ثم القيود. يرجع القيود التي تعذر حذفها فتم إلغاؤها."""
        self.ensure_one()
        # 1) الدفعات: حذفها يفك التسويات بنفس الطريقة القياسية
        self.payment_ids.unlink()
        # 2) قيد التصفية
        moves = self.done_move_id.exists()
        for move in moves.filtered(lambda m: m.state == 'posted'):
            move.line_ids.remove_move_reconcile()
            move.button_draft()
        cancelled = self.env['account.move']
        for move in moves:
            try:
                with self.env.cr.savepoint():
                    move.unlink()
            except UserError:
                # قواعد التدقيق أو تسلسل الأرقام تمنع الحذف: يُلغى القيد بدلاً منه
                move.button_cancel()
                cancelled |= move
        return cancelled

    # ==============================
    # الأزرار الذكية
    # ==============================

    def action_view_trip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rotana.transport.trip',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_view_moves(self):
        self.ensure_one()
        return {
            'name': _('القيود'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.done_move_id.ids)],
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'name': _('الدفعات'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_ids.ids)],
        }


class RotanaTransportTripCustodyLine(models.Model):
    _name = 'rotana.transport.trip.custody.line'
    _description = 'سطر مصروفات العهدة'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    custody_id = fields.Many2one(
        'rotana.transport.trip.custody',
        string='العهدة',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='المنتج',
        required=True,
    )
    name = fields.Char(
        string='الوصف',
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    currency_id = fields.Many2one(
        related='custody_id.currency_id',
        string='العملة',
    )
    amount = fields.Monetary(
        string='المبلغ المصروف',
        required=True,
    )

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            line.name = line.product_id.display_name or False

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_('مبلغ السطر يجب أن يكون أكبر من صفر.'))

    def _check_custody_editable(self):
        if any(line.custody_id.state != 'paid' for line in self):
            raise UserError(_(
                'سطور التصفية تُدخل وتُعدَّل في حالة (مدفوعة) فقط.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_custody_editable()
        return lines

    def write(self, vals):
        self._check_custody_editable()
        return super().write(vals)

    def unlink(self):
        self._check_custody_editable()
        return super().unlink()


class RotanaTransportTrip(models.Model):
    _inherit = 'rotana.transport.trip'

    custody_ids = fields.One2many(
        'rotana.transport.trip.custody',
        'trip_id',
        string='العهد',
        groups='account.group_account_user',
    )
    custody_count = fields.Integer(
        string='عدد العهد',
        compute='_compute_custody_count',
        groups='account.group_account_user',
    )

    @api.depends('custody_ids')
    def _compute_custody_count(self):
        for trip in self:
            trip.custody_count = len(trip.custody_ids)

    def action_view_custody(self):
        self.ensure_one()
        return {
            'name': _('العهد'),
            'type': 'ir.actions.act_window',
            'res_model': 'rotana.transport.trip.custody',
            'view_mode': 'list,form',
            'domain': [('trip_id', '=', self.id)],
            'context': {'default_trip_id': self.id},
        }
