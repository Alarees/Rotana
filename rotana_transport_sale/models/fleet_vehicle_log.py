from odoo import api, fields, models

STATE = [
    ('ready', 'جاهز'),
    ('booked', 'محجوز'),
    ('on_trip', 'في رحلة'),
    ('on_maintenance', 'في الصيانة'),
]


class FleetVehicleLog(models.Model):
    _name = 'fleet.vehicle.log'
    _description = 'سجل حركات المركبة'
    _order = 'date desc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='المركبة',
        required=True,
        index=True,
        ondelete='cascade',
    )
    date = fields.Datetime('التاريخ', default=fields.Datetime.now, required=True)
    state_from = fields.Selection(STATE, string='الحالة من')
    state_to = fields.Selection(STATE, string='الحالة إلى')
    location_from = fields.Many2one('rotana.transport.location', string='الموقع من')
    location_to = fields.Many2one('rotana.transport.location', string='الموقع إلى')
    status_ref = fields.Reference(
        selection=[('rotana.transport.trip', 'رحلة النقل')],
        string='المرجع الحالي',
        help='المرجع الحالي للمركبة، مثل الرحلة الحالية التي تشارك فيها.',
    )
    done_by = fields.Many2one(
        'res.users',
        string='تم بواسطة',
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        related='vehicle_id.company_id',
        store=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        # تطبيق الحركات بترتيبها الزمني فتبقى المركبة على حالة آخر حركة
        logs.sorted(lambda log: (log.date, log.id))._apply_to_vehicle()
        return logs

    def _apply_to_vehicle(self):
        """تحديث حالة المركبة وموقعها ومرجعها من هذه الحركات."""
        for log in self:
            vals = {'state_ref': log.id}
            if log.state_to:
                vals['readyness_state'] = log.state_to
            if log.location_to:
                vals['current_location_id'] = log.location_to.id
            log.vehicle_id.write(vals)

    @api.model
    def _remove_for_trips(self, trips):
        """حذف سجلات الحركة المرتبطة برحلات، وإرجاع المركبات لحالتها السابقة.

        - إن كانت المحذوفة هي آخر حركة للمركبة: تُرجَع المركبة إلى آخر حركة
          متبقية، وإن لم يبقَ شيء تعود إلى حالة وموقع ما قبل أول حركة محذوفة.
        - إن كان للمركبة حركات أحدث فلا تتغير حالتها.
        """
        Log = self.sudo()
        refs = ['%s,%s' % (trips._name, trip_id) for trip_id in trips.ids]
        logs = Log.search([('status_ref', 'in', refs)])
        if not logs:
            return
        to_restore = []
        for vehicle in logs.vehicle_id:
            latest = Log.search([('vehicle_id', '=', vehicle.id)], limit=1)
            if latest in logs:
                first = logs.filtered(
                    lambda log, veh=vehicle: log.vehicle_id == veh
                ).sorted(lambda log: (log.date, log.id))[0]
                to_restore.append((vehicle, first))
        logs.unlink()
        for vehicle, first in to_restore:
            last = Log.search([('vehicle_id', '=', vehicle.id)], limit=1)
            if last:
                last._apply_to_vehicle()
                continue
            vals = {'state_ref': False}
            if first.state_from:
                vals['readyness_state'] = first.state_from
            if first.location_from:
                vals['current_location_id'] = first.location_from.id
            vehicle.sudo().write(vals)
