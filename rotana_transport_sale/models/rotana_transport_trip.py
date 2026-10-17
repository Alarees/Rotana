# -*- coding: utf-8 -*-
"""نموذج رحلات النقل لشركة روتانا.

يُولَّد تلقائياً عند تأكيد أمر بيع النقل.
يتضمن حالات: مسودة، مؤكدة، في الطريق، مكتملة.
عند الاكتمال يُحدَّث الموقع الحالي للمركبة.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

TRIP_STATES = [
    ('draft', 'مسودة'),
    ('confirmed', 'مؤكدة'),
    ('in_transit', 'في الطريق'),
    ('done', 'مكتملة'),
]


class RotanaTransportTrip(models.Model):
    _name = 'rotana.transport.trip'
    _description = 'رحلة النقل'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'manifest_number'

    def _defalut_allowable_deficit(self):
        return self.env['ir.config_parameter'].sudo().get_param('rotana_transport_sale.allowable_deficit', default=0.0)


    manifest_number = fields.Char(
        string='رقم المانيفستو',
        copy=False,
        help='رقم المانيفستو المخصص لأمر النقل.',
        # default=lambda self: _('جديد'),
        # required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='أمر البيع')

    state = fields.Selection(
        selection=TRIP_STATES,
        string='الحالة',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # الموارد
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='المركبة',
        index=True,
        tracking=True,
        required=True,
    )

    driver_id = fields.Many2one(
        related='vehicle_id.driver_id',
        index=True,
        tracking=True,
        required=True,
    )

    # المسار
    location_from_id = fields.Many2one(
        'rotana.transport.location',
        related='sale_order_id.transport_location_from_id',
        string='من (الموقع)',
        index=True,
        tracking=True,
        required=True,
    )

    location_to_id = fields.Many2one(
        'rotana.transport.location',
        related='sale_order_id.transport_location_to_id',
        string='إلى (الموقع)',
        index=True,
        tracking=True,
        required=True,
    )

    # التواريخ
    planned_date = fields.Date(
        string='تاريخ الرحلة المخطط',
        tracking=True,
    )

    actual_start_date = fields.Datetime(
        string='تاريخ الانطلاق الفعلي',
        tracking=True,
    )

    actual_end_date = fields.Datetime(
        string='تاريخ الوصول الفعلي',
        tracking=True,
    )

    transported_weight = fields.Float(
        string='الوزن المنقول',
        store=True,
    )
    
    allowable_deficit = fields.Float(
        string='الحد المسموح به من النقص',
        default=_defalut_allowable_deficit,
        help='الحد المسموح به من النقص في الوزن أثناء النقل.',
        store=True,
    )

    transport_efficiency= fields.Float(
        compute='_compute_transport_efficiency',
        string='كفاءة النقل',
        readonly=True,
        store=True)

    discharged_quantity = fields.Float(
        string='الكمية المفرغة',
        store=True)

    notes = fields.Text(string='ملاحظات')

    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='الحساب التحليلي',
        store=True,
        readonly=True,
    )

    # ==============================
    # دورة الحياة
    # ==============================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sale_order = self.env['sale.order'].browse(vals.get('sale_order_id'))
            if sale_order.state in ('draft', 'cancel'):
                raise ValidationError('لا يمكن إنشاء رحلة لأمر بيع غير مؤكد')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'لا يمكن حذف الرحلة %(name)s إلا بعد اعادتها لحالة مسودة',
                    name=rec.manifest_number,
                ))
        return super().unlink()

    def _create_vehicle_log(self, state_to, to_destination=False):
        """تسجيل حركة في سجل مركبة الرحلة (وهو يحدّث حالة المركبة وموقعها).

        يتم بصلاحيات مرتفعة لأن مستخدم النقل لا يملك صلاحية الكتابة على السجل.
        """
        Log = self.env['fleet.vehicle.log'].sudo()
        vals_list = []
        for trip in self:
            vehicle = trip.vehicle_id
            if not vehicle:
                continue
            location_to = vehicle.current_location_id
            if to_destination and trip.location_to_id:
                location_to = trip.location_to_id
            vals_list.append({
                'vehicle_id': vehicle.id,
                'state_from': vehicle.readyness_state,
                'state_to': state_to,
                'location_from': vehicle.current_location_id.id or trip.location_from_id.id,
                'location_to': location_to.id,
                # حقل Reference يقبل نصاً بصيغة "model,id" وليس رقماً فقط
                'status_ref': '%s,%s' % (trip._name, trip.id),
            })
        return Log.create(vals_list)

    def action_generate_manifest_number(self):
        manifest_number = self.env['ir.sequence'].next_by_code('rotana.transport.trip')
        self.write({'manifest_number': manifest_number})
        account_analytic = self.env['account.analytic.account'].create({
            'name': self.manifest_number,
            'company_id': self.company_id.id,
            'sale_order_id': self.sale_order_id.id,
            'plan_id': self.vehicle_id.analytic_plan_id.id if self.vehicle_id else False,
        })
        self.account_analytic_id = account_analytic.id
     

    def action_confirm(self):
        """تأكيد الرحلة: تنتقل من مسودة إلى مؤكدة."""
        for trip in self:
            if trip.state != 'draft':
                raise UserError(_(
                    'لا يمكن تأكيد الرحلة %(name)s لأنها ليست في حالة مسودة.',
                    name=trip.manifest_number,
                ))
            if trip.transported_weight <= 0.0:
                raise UserError(_(
                    'لا يمكن تأكيد الرحلة %(name)s, الرجاء ادخال الوزن المنقول',
                    name=trip.manifest_number,
                ))
            trip.write({'state': 'confirmed'})
            trip._create_vehicle_log('booked')
            # trip.vehicle_id.sudo().write({
            #     'readyness_state': 'booked',
            #     'state_ref': trip,
            # })
        return True

    def action_start_transit(self):
        """بدء الرحلة: تنتقل من مؤكدة إلى في الطريق."""
        for trip in self:
            if trip.state != 'confirmed':
                raise UserError(_(
                    'يجب تأكيد الرحلة %(name)s قبل بدء التنقل.',
                    name=trip.manifest_number,
                ))
            vals = {'state': 'in_transit'}
            if not trip.actual_start_date:
                vals['actual_start_date'] = fields.Datetime.now()
            trip.write(vals)
            trip._create_vehicle_log('on_trip')
            # trip.vehicle_id.sudo().write({
            #     'readyness_state': 'on_trip',
            #     'state_ref': trip,
            # })
        return True

    def action_done(self):
        """إكمال الرحلة: تنتقل إلى مكتملة وتُحدَّث بيانات المركبة."""
        for trip in self:
            if trip.state != 'in_transit':
                raise UserError(_(
                    'يجب أن تكون الرحلة %(name)s في الطريق قبل إكمالها.',
                    name=trip.manifest_number,
                ))
            if trip.discharged_quantity <= 0.0:
                raise UserError(_('الرجاء ادخال الوزن المفرغ للرحلة قبل اكمالها'))
            vals = {'state': 'done'}
            if not trip.actual_end_date:
                vals['actual_end_date'] = fields.Datetime.now()
            trip.write(vals)
            # تحديث الموقع الحالي للمركبة بالموقع النهائي للرحلة
            if trip.vehicle_id:
                trip._create_vehicle_log('ready', to_destination=True)
                # trip.vehicle_id.sudo().write({
                #     'current_location_id': trip.location_to_id.id,
                #     'readyness_state': 'ready',
                #     'state_ref': trip,
                # })
        return True

    def action_reset_to_draft(self):
        """إعادة إلى مسودة (للمدير فقط)."""
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_(
                'لا يمكن إعادة الرحلة المكتملة إلى مسودة.'
            ))
        if self.state == 'draft':
            return True
        self.write({'state': 'draft'})
        self._create_vehicle_log('ready')
        # self.vehicle_id.sudo().write({
        #     'current_location_id': self.location_from_id.id,
        #     'readyness_state': 'ready',
        #     'state_ref': self,
        # })
        return True

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'context': {
                'default_is_transport_order': True,
            },
        }

    def action_view_account_analytic(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.account',
            'view_mode': 'form',
            'res_id': self.account_analytic_id.id,
            'context': {
                'default_sale_order_id': self.sale_order_id.id,
            },
        }

    def action_view_transport_trips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('رحلات النقل'),
            'res_model': 'rotana.transport.trip',
            'views': [(False, 'form')],
            # 'view_mode': 'list,form',
            'res_id': self.id,
        }

    @api.depends('transported_weight', 'discharged_quantity')
    def _compute_transport_efficiency(self):
        for trip in self:
            if trip.transported_weight > 0:
                trip.transport_efficiency =  (trip.discharged_quantity / trip.transported_weight) * 100
            else:
                trip.transport_efficiency = 0.0
