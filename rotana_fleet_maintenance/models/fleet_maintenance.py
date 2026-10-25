# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class MaintenanceRequest(models.Model):
    _name = 'maintenance.request'
    _inherit = ['maintenance.request', 'product.catalog.mixin']

    maintenance_for = fields.Selection(
        selection_add=[
            ('fleet', 'Fleet'),
        ],
        ondelete={
            'fleet': 'cascade',
        },
    )
    fleet_id = fields.Many2one('fleet.vehicle', string='Fleet')

    # ------------------------------------------------------------------
    # قطع الغيار
    # ------------------------------------------------------------------
    part_line_ids = fields.One2many(
        'maintenance.request.part', 'request_id', string='قطع الغيار', copy=True)
    parts_state = fields.Selection(
        [
            ('draft', 'مسودة'),
            ('confirmed', 'مؤكد'),
            ('done', 'مكتمل'),
        ],
        string='حالة قطع الغيار', default='draft', copy=False, tracking=True,
    )
    # كتالوج المنتجات في أودو (واجهة JS) يقرأ حقل "state" من السجل الأب،
    # لذلك نعرضه كنسخة من حالة قطع الغيار.
    state = fields.Selection(related='parts_state', string='الحالة')
    currency_id = fields.Many2one(related='company_id.currency_id')
    parts_total = fields.Monetary(compute='_compute_parts_total', string='إجمالي قطع الغيار')
    picking_ids = fields.One2many(
        'stock.picking', 'maintenance_request_id', string='أذون التسليم', copy=False)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='الحساب التحليلي', copy=False, readonly=True)
    parts_move_id = fields.Many2one(
        'account.move', string='قيد قطع الغيار', copy=False, readonly=True)

    @api.depends('part_line_ids.subtotal')
    def _compute_parts_total(self):
        for request in self:
            request.parts_total = sum(request.part_line_ids.mapped('subtotal'))

    # ------------------------------------------------------------------
    # كتالوج المنتجات (نفس آلية industry_fsm_sale)
    # ------------------------------------------------------------------
    def action_add_from_catalog(self):
        action = super().action_add_from_catalog()
        kanban_view = self.env.ref('rotana_fleet_maintenance.maintenance_part_product_catalog_kanban_view')
        search_view = self.env.ref('rotana_fleet_maintenance.maintenance_part_product_catalog_search_view')
        action['name'] = _('قطع الغيار')
        action['search_view_id'] = [search_view.id, 'search']
        action['views'] = [(kanban_view.id, 'kanban'), (False, 'form')]
        return action

    def _get_action_add_from_catalog_extra_context(self):
        # واجهة الكتالوج (JS) تقرأ order_id من السياق لنداء المتحكم،
        # بالإضافة إلى العملة ودقة الأرقام لعرض السعر.
        return {
            **super()._get_action_add_from_catalog_extra_context(),
            'order_id': self.id,
            'product_catalog_currency_id': self.company_id.currency_id.id,
            'product_catalog_digits': [16, self.env['decimal.precision'].precision_get('Product Price')],
        }

    def _get_product_catalog_domain(self):
        # قطع الغيار = منتجات مخزنية فقط
        return super()._get_product_catalog_domain() & Domain([
            ('type', '=', 'consu'),
            ('is_storable', '=', True),
        ])

    def _is_readonly(self):
        self.ensure_one()
        return self.parts_state != 'draft' or self.archive

    def _get_product_catalog_record_lines(self, product_ids, **kwargs):
        grouped_lines = defaultdict(lambda: self.env['maintenance.request.part'])
        for line in self.part_line_ids:
            if line.product_id.id in product_ids:
                grouped_lines[line.product_id] |= line
        return grouped_lines

    def _get_product_catalog_order_data(self, products, **kwargs):
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            res[product.id]['price'] = product.standard_price
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
            self.env['maintenance.request.part'].create({
                'request_id': self.id,
                'product_id': product_id,
                'quantity': quantity,
            })
        return product.standard_price

    # ------------------------------------------------------------------
    # التأكيد: إذن تسليم + حساب تحليلي
    # ------------------------------------------------------------------
    def action_confirm_parts(self):
        for request in self:
            if request.parts_state != 'draft':
                continue
            if request.maintenance_for != 'fleet' or not request.fleet_id:
                raise UserError(_('تأكيد قطع الغيار متاح لطلبات صيانة المركبات فقط، اختر المركبة أولاً.'))
            if not request.part_line_ids:
                raise UserError(_('أضف قطع غيار واحدة على الأقل قبل التأكيد.'))
            request._create_analytic_account()
            request._create_parts_picking()
            request.parts_state = 'confirmed'
        return True

    def action_reset_parts(self):
        """ إلغاء التأكيد: يُلغي أذون التسليم غير المنفَّذة ويعيد الطلب لمسودة. """
        for request in self:
            if request.parts_state != 'confirmed':
                continue
            if request.picking_ids.filtered(lambda p: p.state == 'done'):
                raise UserError(_('لا يمكن إلغاء التأكيد لأن إذن التسليم تم تنفيذه بالفعل.'))
            request.picking_ids.filtered(lambda p: p.state != 'cancel').sudo().action_cancel()
            request.parts_state = 'draft'
        return True

    def _get_vehicle_analytic_plan(self):
        self.ensure_one()
        return (
            self.company_id.maintenance_analytic_plan_id
            or self.env.ref('rotana_fleet_maintenance.analytic_plan_vehicles').sudo()
        )

    def _create_analytic_account(self):
        self.ensure_one()
        if self.analytic_account_id:
            return self.analytic_account_id
        plan = self._get_vehicle_analytic_plan()
        self.analytic_account_id = self.env['account.analytic.account'].sudo().create({
            'name': '%s - %s (#%s)' % (self.fleet_id.display_name, self.name, self.id),
            'plan_id': plan.id,
            'company_id': self.company_id.id,
        })
        return self.analytic_account_id

    def _create_parts_picking(self):
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.company_id.id)], limit=1)
        picking_type = warehouse.out_type_id
        if not picking_type:
            raise UserError(_('لا يوجد مستودع بنوع عملية "تسليم" للشركة %s.', self.company_id.name))
        src_location = picking_type.default_location_src_id
        dest_location = self.env.ref('rotana_fleet_maintenance.stock_location_maintenance_consumption')
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'maintenance_request_id': self.id,
            'move_ids': [Command.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
                'company_id': self.company_id.id,
            }) for line in self.part_line_ids],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    # ------------------------------------------------------------------
    # الإكمال: قيد يومية لإنقاص قيمة المخزون
    # ------------------------------------------------------------------
    def write(self, vals):
        completing = self.browse()
        if vals.get('stage_id') and self.env['maintenance.stage'].browse(vals['stage_id']).done:
            completing = self.filtered(lambda r: not r.stage_id.done)
            completing._check_parts_before_done()
        res = super().write(vals)
        if completing:
            completing._create_parts_journal_entry()
        return res

    def _check_parts_before_done(self):
        for request in self.filtered('part_line_ids'):
            if request.parts_state == 'draft':
                raise UserError(_('أكّد قطع الغيار (إصدار إذن التسليم) قبل إكمال الطلب "%s".', request.name))
            if request.parts_state == 'confirmed':
                pickings = request.picking_ids.filtered(lambda p: p.state != 'cancel')
                if not pickings or any(p.state != 'done' for p in pickings):
                    raise UserError(_(
                        'لا يمكن إكمال الطلب "%s" قبل تنفيذ إذن تسليم قطع الغيار من المخزن.', request.name))

    def _create_parts_journal_entry(self):
        for request in self.filtered(lambda r: r.parts_state == 'confirmed' and not r.parts_move_id):
            request = request.with_company(request.company_id)
            company = request.company_id
            currency = company.currency_id
            moves = request.picking_ids.filtered(lambda p: p.state == 'done') \
                .sudo().move_ids.filtered(lambda m: m.state == 'done')

            debit_by_account = defaultdict(float)
            credit_by_account = defaultdict(float)
            for move in moves:
                amount = currency.round(abs(move.value))
                if currency.is_zero(amount):
                    continue
                accounts = move.product_id.with_company(company)._get_product_accounts()
                expense_account = company.maintenance_expense_account_id or accounts['expense']
                if not expense_account:
                    raise UserError(_(
                        'حدد "حساب مصروف قطع الغيار" في إعدادات الشركة أو حساب المصروف في فئة المنتج %s.',
                        move.product_id.categ_id.display_name))
                debit_by_account[expense_account] += amount
                credit_by_account[accounts['stock_valuation']] += amount

            if debit_by_account:
                journal = company.maintenance_journal_id or self.env['account.journal'].sudo().search(
                    [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
                if not journal:
                    raise UserError(_('لا يوجد دفتر يومية من النوع "متنوع" للشركة %s.', company.name))
                label = _('قطع غيار - %s - %s', request.fleet_id.display_name, request.name)
                analytic = {str(request.analytic_account_id.id): 100.0} if request.analytic_account_id else False
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
                    'date': fields.Date.context_today(request),
                    'ref': label,
                    'line_ids': line_vals,
                })
                account_move._post()
                request.parts_move_id = account_move
            request.parts_state = 'done'
