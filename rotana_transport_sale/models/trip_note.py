from odoo import _, api, fields, models

class RotanaTransportTripNote(models.Model):
    _name = 'rotana.transport.trip.note'
    _description = 'Rotana Transport Trip Note'
    _order = 'time desc, id desc'


    note_id = fields.Many2one('fleet.vehicle.note', string='note')
    time = fields.Datetime('time')
    trip_id = fields.Many2one('rotana.transport.trip', string='trip')