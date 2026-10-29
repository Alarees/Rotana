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
        store=True,
        readonly=True
    )
    capacity_ton = fields.Float(string='الطاقة الاستيعابية (طن)')

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

    @api.model_create_multi
    def create(self, vals_list):
        Model = self.env['fleet.vehicle.model']
        param = self.env['ir.config_parameter'].sudo().get_param(
            'rotana_transport_sale.parent_analytic_plan_id'
        )
        parent_id = int(param) if param and str(param).isdigit() else False

        # قراءة الموديلات والماركات دفعة واحدة بدل استعلام لكل صف
        models = Model.browse([v['model_id'] for v in vals_list if v.get('model_id')])
        models.mapped('brand_id.name')
        by_id = {m.id: m for m in models}

        pending = []  # (vals المركبة، vals الخطة)
        for vals in vals_list:
            if vals.get('analytic_plan_id'):
                continue
            model = by_id.get(vals.get('model_id'), Model)
            name = '/'.join(filter(None, [
                model.brand_id.name, model.name, vals.get('unit_number'),
            ]))
            if name:
                pending.append((vals, {'name': name, 'parent_id': parent_id}))

        if pending:
            plans = self.env['account.analytic.plan'].sudo().create(
                [plan_vals for __, plan_vals in pending]
            )
            for (vals, __), plan in zip(pending, plans):
                vals['analytic_plan_id'] = plan.id
        return super().create(vals_list)

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