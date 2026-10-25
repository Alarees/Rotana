# -*- coding: utf-8 -*-
"""توسعة نموذج أمر البيع لخدمات النقل.

يُضاف متغير بوليان لتمييز أوامر بيع النقل عن البيع العادي،
مع إضافة حقول المركبة والسائق والمواقع.
عند تأكيد أمر البيع يُنشأ تلقائياً رحلة مرتبطة به.
عند اختيار المركبة يُحدَّث موقع الانطلاق من موقع المركبة الحالي.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class RotanaTransportSaleOrder(models.Model):
    _inherit = 'sale.order'

    # =======================================
    # تمييز أوامر بيع النقل
    # =======================================

    is_transport_order = fields.Boolean(
        string='أمر نقل',
        default=False,
        copy=False,
        tracking=True,
        help='فعِّل هذا الخيار لتحويل أمر البيع إلى أمر خدمة نقل.',
    )

    # =======================================
    # بيانات النقل
    # =======================================

    transport_location_from_id = fields.Many2one(
        'rotana.transport.location',
        string='من',
        index=True,
        tracking=True,
    )

    transport_location_to_id = fields.Many2one(
        'rotana.transport.location',
        string='إلى',
        index=True,
        tracking=True,
    )

    transport_trip_count = fields.Integer(
        string='عدد الرحلات',
        compute='_compute_transport_trip_count',
    )

    total_transported_weight = fields.Float(
        string='إجمالي الوزن المنقول',
        compute='_compute_total_transported_weight',
        store=True,
    )

    total_weight_to_transport = fields.Float(
        string='إجمالي الوزن المطلوب نقله',
        compute='_compute_total_weight_to_transport',
        store=True,
    )

    total_discharged_quantity = fields.Float(
        string='إجمالي الكمية المفرغة',
        compute='_compute_total_discharged_quantity',
        store=True,
    )

    # transport_efficiency = fields.Float(
    #     string='كفاءة النقل',
    #     compute='_compute_transport_efficiency',
    #     store=False,
    # )

    trip_ids = fields.One2many(
        'rotana.transport.trip',
        'sale_order_id',
        string='الرحلات'
        )

    analytic_account_count = fields.Integer(
        string='عدد الحسابات التحليلية',
        compute='_compute_analytic_account_count',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_transport_order') or self.env.context.get('default_is_transport_order'):
                vals['name'] = self.env['ir.sequence'].next_by_code('rotana.transport.sale')
        return super().create(vals_list)
    
    # =======================================
    # حسابات
    # =======================================

    @api.depends('trip_ids')
    def _compute_transport_trip_count(self):
        for order in self:
            order.transport_trip_count = len(order.trip_ids)

    @api.depends('trip_ids.transported_weight', 'trip_ids.state')
    def _compute_total_transported_weight(self):
        for order in self:
            transported = sum(
                trip.transported_weight for trip in order.trip_ids.filtered(lambda t: t.state != 'draft')
            )
            if transported > order.total_weight_to_transport :
                raise UserError(_(''))
            order.total_transported_weight = transported

    @api.depends('total_transported_weight', 'vehicle_id.capacity_kg')
    def _compute_transport_efficiency(self):
        for order in self:
            if order.vehicle_id and order.vehicle_id.capacity_kg:
                order.transport_efficiency = (
                    order.total_transported_weight / order.vehicle_id.capacity_kg * 100
                )
            else:
                order.transport_efficiency = 0.0

    @api.depends('order_line.product_uom_qty')
    def _compute_total_weight_to_transport(self):
        ton = self.env['uom.uom'].search([('name', '=', 'Ton')], limit=1)
        for order in self:
            order.total_weight_to_transport = sum(
                line.product_uom_id._compute_quantity(line.product_uom_qty, ton) for line in order.order_line
            )

    @api.depends('trip_ids.discharged_quantity')
    def _compute_total_discharged_quantity(self):
        for order in self:
            order.total_discharged_quantity = sum(
                trip.discharged_quantity for trip in order.trip_ids
            )

    @api.depends('trip_ids.account_analytic_id')
    def _compute_analytic_account_count(self):
        for order in self:
            order.analytic_account_count = len(order.trip_ids.mapped('account_analytic_id'))

    # =======================================
    # أحداث تغيير الحقول
    # =======================================

    @api.onchange('vehicle_id')
    def _onchange_transport_vehicle_id(self):
        """عند اختيار المركبة يُحدَّث موقع الانطلاق من موقعها الحالي."""
        if self.vehicle_id and self.vehicle_id.current_location_id:
            self.transport_location_from_id = self.vehicle_id.current_location_id

    @api.onchange('is_transport_order')
    def _onchange_is_transport_order(self):
        """عند تغيير حالة أمر النقل إعادة تعيين الحقول."""
        if not self.is_transport_order:
            self.transport_location_from_id = False
            self.transport_location_to_id = False

    # =======================================
    # تأكيد أمر البيع وتوليد الرحلة
    # =======================================

    # def action_confirm(self):
    #     """تأكيد أمر البيع وتوليد رحلة إذا كان أمر نقل."""
    #     for order in self:
    #         if order.is_transport_order:
    #             analytic_account = {
    #                 'name': order.name,
    #                 'code': f'TRANS-{order.name}',
    #                 'company_id': order.company_id.id,
    #                 'plan_id': self.env.ref('rotana_transport_sale.parent_analytic_plan_id').id,
    #             }
                
    #     if self.is_transport_order:
    #     res = super().action_confirm()
    #     for order in self:
    #         if order.is_transport_order:
    #             order._create_transport_trip()
    #     return res

    # =======================================
    # ويزرد اختيار المركبات وإنشاء الرحلات
    # =======================================

    def action_open_trip_wizard(self):
        """فتح كانبان لاختيار المركبات (بالسحب) ثم إنشاء رحلة لكل مركبة."""
        self.ensure_one()
        if not self.is_transport_order:
            raise UserError(_('هذا الأمر ليس أمر نقل.'))
        if not (self.transport_location_from_id and self.transport_location_to_id):
            raise UserError(_(
                'حدّد موقعي الانطلاق (من) والوصول (إلى) في أمر البيع قبل إنشاء الرحلات.'
            ))

        wizard = self.env['rotana.transport.trip.wizard'].create({
            'sale_order_id': self.id,
        })
        vehicles = self.env['fleet.vehicle'].search([])
        self.env['rotana.transport.trip.wizard.line'].create([
            {'wizard_id': wizard.id, 'vehicle_id': vehicle.id}
            for vehicle in vehicles
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('اختيار المركبات - %s', self.name),
            'res_model': 'rotana.transport.trip.wizard.line',
            'view_mode': 'kanban',
            'domain': [('wizard_id', '=', wizard.id)],
            'context': {'wizard_id': wizard.id},
            'target': 'current',
        }

    # =======================================
    # التوزيع التحليلي للرحلات عند الفوترة
    # =======================================

    def _get_trip_analytic_distribution(self):
        """نسبة كل رحلة من الفاتورة: {حساب الرحلة التحليلي: النسبة %}.

        النسبة = الوزن المنقول في الرحلة / إجمالي الوزن المطلوب نقله في أمر البيع.
        - تُحتسب الرحلات غير المسودة التي لها حساب تحليلي ووزن منقول فقط.
        - لا يتجاوز مجموع النسب 100% (نقل زائد أو اختلاف وحدات الوزن).
        """
        self.ensure_one()
        total = self.total_weight_to_transport
        if not self.is_transport_order or total <= 0:
            return {}
        shares = {}
        for trip in self.trip_ids:
            if (
                trip.state == 'draft'
                or not trip.account_analytic_id
                or trip.transported_weight <= 0
            ):
                continue
            key = str(trip.account_analytic_id.id)
            shares[key] = shares.get(key, 0.0) + trip.transported_weight * 100.0 / total
        if not shares:
            return {}
        percent_total = sum(shares.values())
        if percent_total > 100.0:
            shares = {key: value * 100.0 / percent_total for key, value in shares.items()}
        shares = {
            key: float_round(value, precision_digits=2) for key, value in shares.items()
        }
        # تصحيح فائض التقريب إن وُجد من أكبر نسبة
        excess = sum(shares.values()) - 100.0
        if excess > 0:
            biggest = max(shares, key=shares.get)
            shares[biggest] = float_round(shares[biggest] - excess, precision_digits=2)
        return {key: value for key, value in shares.items() if value > 0}

    # =======================================
    # إجراء فتح الرحلات
    # =======================================

    def action_view_transport_trips(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        print("################## active_id -> ", active_id)
        return {
            'type': 'ir.actions.act_window',
            'name': _('رحلات النقل'),
            'res_model': 'rotana.transport.trip',
            'views': [(False, 'list'), (False, 'form')],
            # 'view_mode': 'list,form',
            # 'res_id': res_id or False,
            'domain': [('id', 'in', self.trip_ids.ids)],
        }

    def action_view_account_analytic(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الحساب التحليلي'),
            'res_model': 'account.analytic.account',
            'views': [(False, 'list'), (False, 'form')],
            # 'view_mode': 'list,form',
            # 'res_id': res_id or False,
            'domain': [('sale_order_id', '=', self.id)],
        }
