from odoo.tests import TransactionCase, tagged

from odoo.addons.rotana_weighbridge.models.weighbridge_ticket import plate_digits


@tagged('post_install', '-at_install')
class TestWeighbridgeTicket(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Ticket = self.env['rotana.weighbridge.ticket']

    def _payload(self, **overrides):
        ticket = {
            'ticket_number': 9001,
            'plate': '99999',
            'first_weight': 22000,
            'first_weight_datetime': '2026-11-09 08:00:00',
            'second_weight': 60000,
            'second_weight_datetime': '2026-11-09 08:20:00',
            'has_trailer': False,
            'customer': 'Test customer',
            'unit': 'Kg',
        }
        ticket.update(overrides)
        return {'station': 'test', 'tickets': [ticket]}

    def _get(self, number=9001):
        return self.Ticket.search([('external_key', '=', 'test:%s' % number)])

    def test_plate_digits(self):
        self.assertEqual(plate_digits('16202  ب ح س ش'), '16202')
        self.assertEqual(plate_digits(' 5153'), '5153')
        self.assertEqual(plate_digits('٣٢٧٩٠ س'), '32790')
        self.assertEqual(plate_digits('00123'), '123')
        self.assertEqual(plate_digits('ABC'), '')
        self.assertEqual(plate_digits(False), '')

    def test_create_computes_net_weight_and_date(self):
        result = self.Ticket.sync_from_agent(self._payload())
        self.assertEqual(result['created'], 1)
        ticket = self._get()
        self.assertEqual(ticket.state, 'done')
        self.assertEqual(ticket.net_weight, 38000)
        self.assertEqual(str(ticket.ticket_date), '2026-11-09')
        self.assertEqual(ticket.vehicle_match, 'external')
        self.assertFalse(ticket.vehicle_id)

    def test_trailer_net_weight(self):
        self.Ticket.sync_from_agent(self._payload(
            first_weight=22080, second_weight=60340, has_trailer=True,
            trailer_first_weight=12880, trailer_second_weight=50920))
        self.assertEqual(self._get().net_weight, 76300)

    def test_pending_then_completed(self):
        self.Ticket.sync_from_agent(self._payload(second_weight=0, second_weight_datetime=None))
        self.assertEqual(self._get().state, 'pending')
        self.assertEqual(self._get().net_weight, 0)
        result = self.Ticket.sync_from_agent(self._payload())
        self.assertEqual(result['updated'], 1)
        self.assertEqual(self._get().state, 'done')

    def test_unchanged_and_cancel(self):
        self.Ticket.sync_from_agent(self._payload())
        self.assertEqual(self.Ticket.sync_from_agent(self._payload())['unchanged'], 1)
        result = self.Ticket.sync_from_agent({'station': 'test', 'deleted': [9001]})
        self.assertEqual(result['cancelled'], 1)
        self.assertEqual(self._get().state, 'cancelled')
        # a cancelled ticket that reappears at the source is reactivated
        self.Ticket.sync_from_agent(self._payload())
        self.assertEqual(self._get().state, 'done')

    def test_bad_ticket_does_not_block_others(self):
        payload = self._payload()
        payload['tickets'].insert(0, {'plate': '1'})  # missing ticket_number
        result = self.Ticket.sync_from_agent(payload)
        self.assertEqual(result['created'], 1)
        self.assertEqual(len(result['errors']), 1)

    def test_dashboard_data_shape(self):
        data = self.Ticket.get_dashboard_data(7)
        self.assertEqual(len(data['days']), 7)
        self.assertIn('count', data['today'])
        self.assertIn('net', data['month'])
