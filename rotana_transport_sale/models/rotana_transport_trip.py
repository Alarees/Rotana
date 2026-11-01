# -*- coding: utf-8 -*-
"""نموذج رحلات النقل لشركة روتانا.

يُولَّد تلقائياً عند تأكيد أمر بيع النقل.
يتضمن حالات: مسودة، مؤكدة، في الطريق، مكتملة.
عند الاكتمال يُحدَّث الموقع الحالي للمركبة.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

TRIP_STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('in_transit', 'In Transit'),
    ('done', 'Completed'),
]


class RotanaTransportTrip(models.Model):
    _name = 'rotana.transport.trip'
    _description = 'Transport Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'manifest_number'

    def _defalut_allowable_deficit(self):
        return self.env['ir.config_parameter'].sudo().get_param('rotana_transport_sale.allowable_deficit', default=0.0)


    manifest_number = fields.Char(
        string='Manifest Number',
        copy=False,
        help='Manifest number assigned to the transport order.',
        # default=lambda self: _('جديد'),
        # required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order')

    state = fields.Selection(
        selection=TRIP_STATES,
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # الموارد
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
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
        string='From (Location)',
        index=True,
        tracking=True,
        required=True,
    )

    location_to_id = fields.Many2one(
        'rotana.transport.location',
        related='sale_order_id.transport_location_to_id',
        string='To (Location)',
        index=True,
        tracking=True,
        required=True,
    )

    # التواريخ
    planned_date = fields.Date(
        string='Planned Trip Date',
        tracking=True,
    )

    actual_start_date = fields.Datetime(
        string='Actual Departure Date',
        tracking=True,
    )

    actual_end_date = fields.Datetime(
        string='Actual Arrival Date',
        tracking=True,
    )

    transported_weight = fields.Float(
        string='Transported Weight',
        store=True,
    )
    
    allowable_deficit = fields.Float(
        string='Allowable Deficit',
        default=_defalut_allowable_deficit,
        help='Allowable weight deficit during transport.',
        store=True,
    )

    transport_efficiency= fields.Float(
        compute='_compute_transport_efficiency',
        string='Transport Efficiency',
        readonly=True,
        store=True)

    discharged_quantity = fields.Float(
        string='Discharged Quantity',
        store=True)

    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        store=True,
        readonly=True,
    )

    note_ids = fields.One2many('rotana.transport.trip.note', 'trip_id', string='note')

    # ==============================
    # دورة الحياة
    # ==============================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sale_order = self.env['sale.order'].browse(vals.get('sale_order_id'))
            if sale_order.total_transported_weight >= sale_order.total_weight_to_transport :
                raise UserError(_('You cannot create the trip: the transported weight is already complete.'))
            if sale_order.state in ('draft', 'cancel'):
                raise ValidationError('You cannot create a trip for an unconfirmed sales order.')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Trip %(name)s can only be deleted after it is reset to draft.',
                    name=rec.manifest_number,
                ))
        return super().unlink()

    @api.onchange('discharged_quantity')
    def _onchange_discharged_quantity(self):
        for trip in self:
            if trip.discharged_quantity > trip.transported_weight :
                raise UserError(_('The discharged weight cannot exceed the transported weight.'))

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
                    'Trip %(name)s cannot be confirmed because it is not in draft state.',
                    name=trip.manifest_number,
                ))
            if trip.transported_weight <= 0.0:
                raise UserError(_(
                    'Trip %(name)s cannot be confirmed. Please enter the transported weight.',
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
                    'Trip %(name)s must be confirmed before starting transit.',
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
                    'Trip %(name)s must be in transit before it can be completed.',
                    name=trip.manifest_number,
                ))
            if trip.discharged_quantity <= 0.0:
                raise UserError(_('Please enter the discharged weight for the trip before completing it.'))
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
                'A completed trip cannot be reset to draft.'
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
            'name': _('Transport Trips'),
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
