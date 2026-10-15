# -*- coding: utf-8 -*-
"""ويزرد اختيار المركبات لإنشاء رحلات من أمر البيع.

الفكرة:
- عند الضغط على زر (إنشاء رحلات) في أمر البيع يُنشأ ويزرد (TransientModel)
  ويُملأ بسطر لكل مركبة، وتُعرض السطور في كانبان مجمّع حسب حقل الاختيار.
- المركبات التي لها رحلة على أمر البيع تظهر مباشرة في عمود (مختارة).
- المستخدم يسحب المركبة من عمود (غير مختارة) إلى عمود (مختارة).
- عند الضغط على زر (إنشاء الرحلات) تُنشأ رحلة rotana.transport.trip
  لكل مركبة مختارة ليس لها رحلة، مربوطة بأمر البيع.
- عند الضغط على الزر تُحذف رحلات المركبات التي في عمود (غير مختارة)
  إذا كانت مسودة، وإذا وُجدت رحلة غير مسودة تُرفض العملية كلها برسالة خطأ.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

LINE_STATES = [
    ('unselected', 'غير مختارة'),
    ('selected', 'مختارة'),
]


class RotanaTransportTripWizard(models.TransientModel):
    _name = 'rotana.transport.trip.wizard'
    _description = 'ويزرد اختيار المركبات للرحلات'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='أمر البيع',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    line_ids = fields.One2many(
        'rotana.transport.trip.wizard.line',
        'wizard_id',
        string='المركبات',
    )

    def action_create_trips(self):
        """إنشاء رحلة لكل مركبة في عمود (مختارة) ليس لها رحلة على أمر البيع."""
        self.ensure_one()
        order = self.sale_order_id
        selected = self.line_ids.filtered(lambda line: line.state == 'selected')
        unselected = self.line_ids - selected
        if not selected and not unselected._has_trips():
            raise UserError(_('اسحب مركبة واحدة على الأقل إلى عمود (مختارة).'))

        # حذف رحلات المسودة للمركبات غير المختارة (يُرفض إن وُجدت رحلة غير مسودة)
        deleted_names = unselected._release_trips()
        if deleted_names:
            order.message_post(body=_(
                'تم حذف %(count)s رحلة مسودة: %(names)s',
                count=len(deleted_names),
                # names='، '.join(deleted_names),
            ))

        Trip = self.env['rotana.transport.trip']
        existing_vehicles = Trip.search([
            ('sale_order_id', '=', order.id),
            ('vehicle_id', 'in', selected.vehicle_id.ids),
        ]).vehicle_id
        new_lines = selected.filtered(
            lambda line: line.vehicle_id not in existing_vehicles
        )
        if new_lines:
            trips = Trip.create([
                {
                    'sale_order_id': order.id,
                    'vehicle_id': line.vehicle_id.id,
                    'planned_date': fields.Date.context_today(self),
                    'company_id': order.company_id.id,
                }
                for line in new_lines
            ])
            order.message_post(body=_(
                'تم إنشاء %(count)s رحلة: %(names)s',
                count=len(trips),
                names=''
                # names='، '.join(trips.mapped('manifest_number')),
            ))
        # العودة إلى أمر البيع
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }


class RotanaTransportTripWizardLine(models.TransientModel):
    _name = 'rotana.transport.trip.wizard.line'
    _description = 'سطر مركبة في ويزرد الرحلات'
    _order = 'id'

    wizard_id = fields.Many2one(
        'rotana.transport.trip.wizard',
        required=True,
        ondelete='cascade',
        index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='المركبة',
        required=True,
        ondelete='cascade',
    )
    state = fields.Selection(
        LINE_STATES,
        string='الاختيار',
        default='unselected',
        required=True,
        # يُظهر العمودين دائماً حتى لو كان أحدهما فارغاً
        group_expand='_read_group_expand_states',
    )

    # حقول للعرض في بطاقة الكانبان
    license_plate = fields.Char(related='vehicle_id.license_plate')
    driver_id = fields.Many2one(related='vehicle_id.driver_id')
    capacity_kg = fields.Float(related='vehicle_id.capacity_kg')
    current_location_id = fields.Many2one(related='vehicle_id.current_location_id')
    readyness_state = fields.Selection(related='vehicle_id.readyness_state')
    trip_count = fields.Integer(
        string='رحلات سابقة على الأمر',
        compute='_compute_trip_count',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """المركبات التي لها رحلة على أمر البيع تبدأ في عمود (مختارة)."""
        wizard_ids = {vals['wizard_id'] for vals in vals_list if vals.get('wizard_id')}
        order_of_wizard = {
            wizard.id: wizard.sale_order_id.id
            for wizard in self.env['rotana.transport.trip.wizard'].browse(wizard_ids)
        }
        trips = self.env['rotana.transport.trip'].search([
            ('sale_order_id', 'in', list(order_of_wizard.values())),
        ])
        used = {(trip.sale_order_id.id, trip.vehicle_id.id) for trip in trips}
        for vals in vals_list:
            if 'state' in vals:
                continue
            order_id = order_of_wizard.get(vals.get('wizard_id'))
            if (order_id, vals.get('vehicle_id')) in used:
                vals['state'] = 'selected'
        return super().create(vals_list)

    def _get_line_trips(self):
        """رحلات أمر البيع الخاصة بمركبات هذه السطور."""
        Trip = self.env['rotana.transport.trip']
        trips = Trip
        for line in self:
            trips |= Trip.search([
                ('sale_order_id', '=', line.wizard_id.sale_order_id.id),
                ('vehicle_id', '=', line.vehicle_id.id),
            ])
        return trips

    def _has_trips(self):
        return bool(self._get_line_trips())

    def _release_trips(self):
        """حذف رحلات المسودة؛ ورفض العملية إن وُجدت رحلة غير مسودة.

        يرجع أرقام المانيفستو المحذوفة.
        """
        trips = self._get_line_trips()
        not_draft = trips.filtered(lambda trip: trip.state != 'draft')
        if not_draft:
            raise UserError(_(
                'لا يمكن إلغاء اختيار المركبة لأن رحلتها ليست في حالة مسودة: %s',
                '، '.join(not_draft.mapped('manifest_number')),
            ))
        names = trips.mapped('manifest_number')
        # حذف سجلات الحركة الخاصة بالرحلات وإرجاع حالة المركبات لما قبلها
        self.env['fleet.vehicle.log']._remove_for_trips(trips)
        # الحذف بصلاحيات مرتفعة لأن مجموعة مستخدم النقل ليس لديها صلاحية حذف الرحلات
        trips.sudo().unlink()
        return names

    @api.model
    def _read_group_expand_states(self, states, domain):
        return [key for key, _label in LINE_STATES]

    @api.depends('vehicle_id', 'wizard_id.sale_order_id')
    def _compute_trip_count(self):
        data = self.env['rotana.transport.trip']._read_group(
            [
                ('sale_order_id', 'in', self.wizard_id.sale_order_id.ids),
                ('vehicle_id', 'in', self.vehicle_id.ids),
            ],
            ['sale_order_id', 'vehicle_id'],
            ['__count'],
        )
        counts = {(order.id, vehicle.id): count for order, vehicle, count in data}
        for line in self:
            line.trip_count = counts.get(
                (line.wizard_id.sale_order_id.id, line.vehicle_id.id), 0
            )

    def action_confirm_selection(self):
        """زر الكانبان: يُستدعى على سجلات غير مهمة، لذا نعتمد على الـ context."""
        wizard = self.env['rotana.transport.trip.wizard'].browse(
            self.env.context.get('wizard_id')
        ).exists()
        if not wizard:
            raise UserError(_('انتهت صلاحية الويزرد، أعد فتحه من أمر البيع.'))
        return wizard.action_create_trips()
