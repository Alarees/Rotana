from odoo import _, api, fields, models

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    _rec_names_search = ['name', 'driver_id.name', 'unit_number']

    unit_number = fields.Char('Unit Number', required=True, copy=False, index=True)
    current_location_id = fields.Many2one(
        'rotana.transport.location',
        string='الموقع الحالي',
        index=True,
        help='الموقع الحالي للمركبة. يُحدَّث تلقائياً عند اكتمال الرحلة.',
    )
    analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='خطة الحساب التحليلي',
        index=True,
        help='خطة الحساب التحليلي الخاصة بهذه المركبة للتتبع المالي.',
    )
    capacity_kg = fields.Float(string='الطاقة الاستيعابية (كغ)')

    readyness_state = fields.Selection(
        [('ready', 'جاهز'), ('booked', 'محجوز'), ('on_trip', 'في رحلة'), ('on_maintenance', 'في الصيانة')],
        string='حالة الجاهزية',
        default='ready',
        help='الحالة الحالية للمركبة فيما يتعلق بالجاهزية للرحلات.',
    )
    state_ref = fields.Many2one(
        'fleet.vehicle.log',
        ondelete='set null',
        string='المرجع الحالي',
        help='المرجع الحالي للمركبة، مثل الرحلة الحالية التي تشارك فيها.',
    )
    note_ids = fields.Many2many(
            'fleet.vehicle.note',
            'fleet_vehicle_note_rel',
            'vehicle_id',
            'note_id',
            string='ملاحظات',
        )

    def create(self, vals):
        model = self.env['fleet.vehicle.model'].browse(vals.get('model_id'))
        name = (model.brand_id.name or '') + '/' + (model.name or '') + '/' + (vals.get('unit_number'))
        parent_plan = self.env['ir.config_parameter'].sudo().get_param('rotana_transport_sale.parent_analytic_plan_id')
        analytic_plan_id = {
            'parent_id': parent_plan,
            'name': name,
        }
        vals['analytic_plan_id'] = self.env['account.analytic.plan'].create(analytic_plan_id).id
        return super().create(vals)

    def copy(self, default=None):
        """تجاوز النسخ الافتراضي لتجنب تكرار رقم الوحدة."""
        if default is None:
            default = {}
        default['unit_number'] = self.unit_number + ' (نسخة)'
        return super().copy(default=default)

    @api.depends('model_id.brand_id.name', 'model_id.name', 'unit_number')
    def _compute_vehicle_name(self):
        for record in self:
            record.name = (record.model_id.brand_id.name or '') + '/' + (record.model_id.name or '') + '/' + (record.unit_number or _('No Unit Number'))

    # =======================================
    # إجراء فتح الرحلات
    # =======================================

    def action_view_transport_trips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('رحلات النقل'),
            'res_model': 'rotana.transport.trip',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
            },
        }

    def action_view_analytic_plan(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الحساب التحليلي'),
            'res_model': 'account.analytic.plan',
            'view_mode': 'form',
            'res_id': self.analytic_plan_id.id,
        }