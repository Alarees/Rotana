import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    _rec_names_search = ['name', 'driver_id.name', 'unit_number']

    unit_number = fields.Char('Unit Number', required=True, copy=False, index=True)
    current_location_id = fields.Many2one(
        'rotana.transport.location',
        string='Current Location',
        index=True,
        help='Current location of the vehicle. Updated automatically when a trip is completed.',
    )
    analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='Analytic Plan',
        index=True,
        help="This vehicle's analytic plan for financial tracking.",
        store=True,
        readonly=True
    )
    capacity_ton = fields.Float(string='Capacity (Tons)')

    readyness_state = fields.Selection(
        [('ready', 'Ready'), ('booked', 'Booked'), ('on_trip', 'On Trip'), ('on_maintenance', 'Under Maintenance')],
        string='Readiness Status',
        default='ready',
        help='Current vehicle status with respect to trip readiness.',
    )
    state_ref = fields.Many2one(
        'fleet.vehicle.log',
        ondelete='set null',
        string='Current Reference',
        help="The vehicle's current reference, such as the trip it is currently on.",
    )
    note_ids = fields.Many2many(
            'fleet.vehicle.note',
            'fleet_vehicle_note_rel',
            'vehicle_id',
            'note_id',
            string='Notes',
        )

    @api.model
    def _get_parent_analytic_plan_id(self):
        """Parent analytic plan id from the settings (False if not set or deleted)."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'rotana_transport_sale.parent_analytic_plan_id'
        )
        parent_id = int(param) if param and str(param).isdigit() else False
        if parent_id and not self.env['account.analytic.plan'].sudo().browse(parent_id).exists():
            return False
        return parent_id

    def _get_analytic_plan_name(self):
        """Plan name for an existing vehicle: Brand/Model/Unit Number (license plate if no unit number)."""
        self.ensure_one()
        return '/'.join(filter(None, [
            self.model_id.brand_id.name,
            self.model_id.name,
            self.unit_number or self.license_plate,
        ])) or _('Vehicle %s', self.id)

    def _create_missing_analytic_plans(self):
        """Create analytic plans for vehicles that have none.

        Used for vehicles that existed before the module was installed, and as a
        safety net when a trip needs the vehicle plan. All plans are created in a
        single batch call. Returns the vehicles that got a plan.
        """
        vehicles = self.filtered(lambda vehicle: not vehicle.analytic_plan_id)
        if not vehicles:
            return vehicles
        parent_id = self._get_parent_analytic_plan_id()
        if not parent_id:
            _logger.warning(
                'Parent analytic plan is not set: no analytic plan was created for %s vehicle(s). '
                'Set it in the Rotana Transport settings, then run "Create Missing Analytic Plans".',
                len(vehicles),
            )
            return self.browse()
        plans = self.env['account.analytic.plan'].sudo().create([
            {'name': vehicle._get_analytic_plan_name(), 'parent_id': parent_id}
            for vehicle in vehicles
        ])
        for vehicle, plan in zip(vehicles, plans):
            vehicle.analytic_plan_id = plan.id
        return vehicles

    @api.model_create_multi
    def create(self, vals_list):
        Model = self.env['fleet.vehicle.model']
        parent_id = self._get_parent_analytic_plan_id()

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
        default['unit_number'] = self.unit_number + ' (Copy)'
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
            'name': _('Transport Trips'),
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
            'name': _('Analytic Account'),
            'res_model': 'account.analytic.plan',
            'view_mode': 'form',
            'res_id': self.analytic_plan_id.id,
        }