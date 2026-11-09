import logging
import re
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Arabic-Indic and Extended Arabic-Indic digits -> Latin digits
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_LEADING_DIGITS = re.compile(r'^\s*(\d+)')

# Trip states considered "open" when linking a weighbridge ticket to a trip
OPEN_TRIP_STATES = ('confirmed', 'in_transit')


def plate_digits(value):
    """Leading digits of a plate (``'16202  ب ح س ش'`` -> ``'16202'``), without leading zeros."""
    if not value:
        return ''
    match = _LEADING_DIGITS.match(str(value).translate(_ARABIC_DIGITS))
    return match.group(1).lstrip('0') if match else ''


def _to_float(value):
    try:
        return float(value) if value not in (None, '') else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_text(value):
    return str(value).strip() if value is not None else ''


def _to_datetime(value):
    """Parse 'YYYY-MM-DD HH:MM:SS' (or ISO with 'T'), expected in UTC. Returns False if empty/invalid."""
    if not value:
        return False
    try:
        return datetime.strptime(str(value).replace('T', ' ')[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return False


def _same(current, new):
    if isinstance(new, bool):
        return bool(current) == new
    if isinstance(new, float):
        return abs((current or 0.0) - new) < 0.0001
    if isinstance(new, str):
        return (current or '') == new
    return (current or False) == (new or False)


class WeighbridgeTicket(models.Model):
    _name = 'rotana.weighbridge.ticket'
    _description = 'Weighbridge Ticket'
    _order = 'ticket_datetime desc, id desc'

    _external_key_uniq = models.Constraint(
        'UNIQUE(external_key)',
        'This weighbridge ticket already exists.',
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(string='Ticket', compute='_compute_name', store=True)
    external_key = fields.Char(string='External Key', required=True, readonly=True, copy=False)
    station_code = fields.Char(string='Weighbridge Station', required=True, readonly=True, default='main')
    ticket_number = fields.Integer(string='Ticket Number', required=True, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self._get_target_company_id())
    state = fields.Selection(
        [('pending', 'Pending'), ('done', 'Completed'), ('cancelled', 'Cancelled')],
        string='Status', compute='_compute_state', store=True, index=True)
    is_cancelled = fields.Boolean(string='Cancelled at source', readonly=True)
    ticket_count = fields.Integer(string='Tickets', default=1, readonly=True)

    # ------------------------------------------------------------------
    # Weights (kg) - raw values reported by SmartBridge
    # ------------------------------------------------------------------
    first_weight = fields.Float(string='First Weight (kg)', readonly=True)
    first_weight_datetime = fields.Datetime(string='First Weight Time', readonly=True)
    second_weight = fields.Float(string='Second Weight (kg)', readonly=True)
    second_weight_datetime = fields.Datetime(string='Second Weight Time', readonly=True)
    has_trailer = fields.Boolean(string='Has Trailer', readonly=True)
    trailer_first_weight = fields.Float(string='Trailer First Weight (kg)', readonly=True)
    trailer_second_weight = fields.Float(string='Trailer Second Weight (kg)', readonly=True)
    truck_net_weight = fields.Float(string='Truck Net (kg)', compute='_compute_net_weights', store=True)
    trailer_net_weight = fields.Float(string='Trailer Net (kg)', compute='_compute_net_weights', store=True)
    net_weight = fields.Float(string='Net Weight (kg)', compute='_compute_net_weights', store=True)
    source_net_weight = fields.Float(string='Reported Net (kg)', readonly=True)
    unit = fields.Char(string='Unit', readonly=True, default='Kg')
    ticket_datetime = fields.Datetime(string='Ticket Time', compute='_compute_ticket_datetime', store=True, index=True)
    ticket_date = fields.Date(string='Ticket Date', compute='_compute_ticket_date', store=True, index=True)

    # ------------------------------------------------------------------
    # Vehicle / trip matching
    # ------------------------------------------------------------------
    plate_number = fields.Char(string='Plate Number', readonly=True, index=True)
    plate_key = fields.Char(string='Plate Digits', compute='_compute_plate_key', store=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', index=True, ondelete='set null')
    unit_number = fields.Char(string='Unit Number', related='vehicle_id.unit_number')
    vehicle_match = fields.Selection(
        [('matched', 'Fleet vehicle'), ('external', 'External truck'), ('ambiguous', 'Ambiguous plate')],
        string='Vehicle Match', default='external', index=True)
    trip_id = fields.Many2one('rotana.transport.trip', string='Trip', index=True, ondelete='set null')
    review_reason = fields.Selection(
        [('ambiguous_vehicle', 'Several vehicles share this plate'),
         ('multiple_trips', 'Several open trips for this vehicle')],
        string='Review Reason')
    needs_review = fields.Boolean(string='Needs Review', compute='_compute_needs_review', store=True, index=True)

    # ------------------------------------------------------------------
    # Business info (free text from the weighbridge)
    # ------------------------------------------------------------------
    driver_name = fields.Char(string='Driver', readonly=True)
    customer_name = fields.Char(string='Customer', readonly=True)
    destination = fields.Char(string='Destination', readonly=True)
    notes = fields.Text(string='Notes', readonly=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.model
    def _get_target_company_id(self):
        param = self.env['ir.config_parameter'].sudo().get_param('rotana_weighbridge.company_id')
        return int(param) if param and param.strip().isdigit() else self.env.company.id

    @api.model
    def _get_timezone(self):
        name = self.env['ir.config_parameter'].sudo().get_param('rotana_weighbridge.timezone') or 'Africa/Khartoum'
        try:
            return pytz.timezone(name)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone('Africa/Khartoum')

    @api.depends('ticket_number', 'station_code')
    def _compute_name(self):
        for rec in self:
            if rec.station_code in (False, '', 'main'):
                rec.name = str(rec.ticket_number)
            else:
                rec.name = '%s-%s' % (rec.station_code, rec.ticket_number)

    @api.depends('second_weight', 'is_cancelled')
    def _compute_state(self):
        for rec in self:
            if rec.is_cancelled:
                rec.state = 'cancelled'
            elif rec.second_weight > 0:
                rec.state = 'done'
            else:
                rec.state = 'pending'

    @api.depends('first_weight', 'second_weight', 'has_trailer',
                 'trailer_first_weight', 'trailer_second_weight')
    def _compute_net_weights(self):
        # SmartBridge stores net = first - second (negative when the empty truck is weighed first),
        # so we always work with absolute differences.
        for rec in self:
            truck = 0.0
            if rec.first_weight > 0 and rec.second_weight > 0:
                truck = abs(rec.first_weight - rec.second_weight)
            trailer = 0.0
            if rec.has_trailer and rec.trailer_first_weight > 0 and rec.trailer_second_weight > 0:
                trailer = abs(rec.trailer_first_weight - rec.trailer_second_weight)
            rec.truck_net_weight = truck
            rec.trailer_net_weight = trailer
            rec.net_weight = truck + trailer

    @api.depends('first_weight_datetime', 'second_weight_datetime')
    def _compute_ticket_datetime(self):
        # Clocks of the weighing devices are not always in sync, so the completion time is the latest stamp.
        for rec in self:
            stamps = [d for d in (rec.first_weight_datetime, rec.second_weight_datetime) if d]
            rec.ticket_datetime = max(stamps) if stamps else (rec.create_date or fields.Datetime.now())

    @api.depends('ticket_datetime')
    def _compute_ticket_date(self):
        tz = self._get_timezone()
        for rec in self:
            if rec.ticket_datetime:
                rec.ticket_date = pytz.utc.localize(rec.ticket_datetime).astimezone(tz).date()
            else:
                rec.ticket_date = False

    @api.depends('plate_number')
    def _compute_plate_key(self):
        for rec in self:
            rec.plate_key = plate_digits(rec.plate_number)

    @api.depends('review_reason')
    def _compute_needs_review(self):
        for rec in self:
            rec.needs_review = bool(rec.review_reason)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _auto_match(self):
        """Match each ticket to a fleet vehicle by plate number, then to its single open trip.

        - One vehicle with the same plate digits -> matched (+ trip if exactly one open trip).
        - Several vehicles with the same digits -> ambiguous, goes to review.
        - No vehicle -> external truck: kept as a weight ticket only, no vehicle is created.
        """
        Vehicle = self.env['fleet.vehicle'].sudo()
        Trip = self.env['rotana.transport.trip'].sudo()
        for rec in self:
            vals = {'vehicle_id': False, 'trip_id': False, 'vehicle_match': 'external', 'review_reason': False}
            key = rec.plate_key
            if key:
                candidates = Vehicle.search([('license_plate', '=like', '%' + key + '%')]).filtered(
                    lambda v: plate_digits(v.license_plate) == key)
                if len(candidates) == 1:
                    vals.update(vehicle_id=candidates.id, vehicle_match='matched')
                    trips = Trip.search([('vehicle_id', '=', candidates.id), ('state', 'in', OPEN_TRIP_STATES)])
                    if len(trips) == 1:
                        vals['trip_id'] = trips.id
                    elif len(trips) > 1:
                        vals['review_reason'] = 'multiple_trips'
                elif len(candidates) > 1:
                    vals.update(vehicle_match='ambiguous', review_reason='ambiguous_vehicle')
            rec.write(vals)

    def action_rematch(self):
        self._auto_match()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._auto_match()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'plate_number' in vals:
            self._auto_match()
        return res

    # ------------------------------------------------------------------
    # Sync from the weighbridge agent
    # ------------------------------------------------------------------
    @api.model
    def sync_from_agent(self, payload):
        """Upsert tickets sent by the agent.

        payload = {'station': 'main', 'tickets': [{...}], 'deleted': [ticket_number, ...]}
        Returns counters and per-ticket errors. One bad ticket never blocks the others.
        """
        station = (_to_text(payload.get('station')) or 'main')[:30]
        result = {'created': 0, 'updated': 0, 'unchanged': 0, 'cancelled': 0, 'errors': []}
        for item in payload.get('tickets') or []:
            try:
                with self.env.cr.savepoint():
                    result[self._sync_one(station, item)] += 1
            except Exception as exc:  # noqa: BLE001 - report and continue with the next ticket
                _logger.exception('Weighbridge sync failed for ticket %s', item.get('ticket_number'))
                result['errors'].append({'ticket_number': item.get('ticket_number'), 'error': str(exc)})
        for number in payload.get('deleted') or []:
            try:
                with self.env.cr.savepoint():
                    record = self.search([('external_key', '=', '%s:%s' % (station, int(number)))], limit=1)
                    if record and not record.is_cancelled:
                        record.is_cancelled = True
                        result['cancelled'] += 1
            except Exception as exc:  # noqa: BLE001
                _logger.exception('Weighbridge cancel failed for ticket %s', number)
                result['errors'].append({'ticket_number': number, 'error': str(exc)})
        return result

    def _sync_one(self, station, item):
        number = int(item['ticket_number'])
        vals = {
            'first_weight': _to_float(item.get('first_weight')),
            'first_weight_datetime': _to_datetime(item.get('first_weight_datetime')),
            'second_weight': _to_float(item.get('second_weight')),
            'second_weight_datetime': _to_datetime(item.get('second_weight_datetime')),
            'has_trailer': bool(item.get('has_trailer')),
            'trailer_first_weight': _to_float(item.get('trailer_first_weight')),
            'trailer_second_weight': _to_float(item.get('trailer_second_weight')),
            'source_net_weight': abs(_to_float(item.get('total_net_weight'))),
            'unit': _to_text(item.get('unit')) or 'Kg',
            'plate_number': _to_text(item.get('plate')),
            'driver_name': _to_text(item.get('driver')),
            'customer_name': _to_text(item.get('customer')),
            'destination': _to_text(item.get('destination')),
            'notes': _to_text(item.get('notes')),
            'is_cancelled': False,
        }
        key = '%s:%s' % (station, number)
        record = self.search([('external_key', '=', key)], limit=1)
        if record:
            changed = {k: v for k, v in vals.items() if not _same(record[k], v)}
            if not changed:
                return 'unchanged'
            record.write(changed)
            return 'updated'
        self.create(dict(vals, external_key=key, station_code=station, ticket_number=number))
        return 'created'

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, days=30):
        """KPIs and a per-day series (completed tickets only) for the dashboard client action."""
        days = max(1, min(int(days or 30), 366))
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        since = today - timedelta(days=days - 1)
        done = [('state', '=', 'done')]

        def totals(extra_domain):
            rows = self._read_group(done + extra_domain, [], ['__count', 'net_weight:sum'])
            count, net = rows[0] if rows else (0, 0.0)
            return {'count': count or 0, 'net': net or 0.0}

        by_day = {}
        grouped = self._read_group(
            done + [('ticket_date', '>=', since)], ['ticket_date:day'], ['__count', 'net_weight:sum'])
        for day, count, net in grouped:
            if day:
                by_day[str(day)[:10]] = (count or 0, net or 0.0)
        series = []
        for offset in range(days):
            current = (since + timedelta(days=offset)).isoformat()
            count, net = by_day.get(current, (0, 0.0))
            series.append({'date': current, 'count': count, 'net': net})

        return {
            'today': totals([('ticket_date', '=', today)]),
            'month': totals([('ticket_date', '>=', month_start)]),
            'pending_today': self.search_count([('state', '=', 'pending'), ('ticket_date', '=', today)]),
            'needs_review': self.search_count([('needs_review', '=', True), ('state', '!=', 'cancelled')]),
            'days': series,
            'today_date': today.isoformat(),
            'month_start': month_start.isoformat(),
        }
