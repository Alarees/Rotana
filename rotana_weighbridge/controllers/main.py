import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_BATCH = 500


class WeighbridgeController(http.Controller):
    """Endpoint used by the agent running on the weighbridge PC.

    Authentication: header ``X-Weighbridge-Token`` must equal the system
    parameter ``rotana_weighbridge.api_token`` (no token configured = endpoint closed).
    """

    @staticmethod
    def _json(data, status=200):
        return request.make_json_response(data, status=status)

    @staticmethod
    def _authorized():
        token = request.env['ir.config_parameter'].sudo().get_param('rotana_weighbridge.api_token')
        supplied = request.httprequest.headers.get('X-Weighbridge-Token', '')
        return bool(token) and hmac.compare_digest(token.encode(), supplied.encode())

    @http.route('/rotana/weighbridge/ping', type='http', auth='public', methods=['GET', 'POST'],
                csrf=False, save_session=False)
    def ping(self, **kwargs):
        if not self._authorized():
            return self._json({'error': 'unauthorized'}, 401)
        return self._json({'ok': True})

    @http.route('/rotana/weighbridge/sync', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    def sync(self, **kwargs):
        if not self._authorized():
            return self._json({'error': 'unauthorized'}, 401)
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return self._json({'error': 'invalid JSON'}, 400)
        if not isinstance(payload, dict):
            return self._json({'error': 'payload must be a JSON object'}, 400)
        tickets = payload.get('tickets') or []
        deleted = payload.get('deleted') or []
        if not isinstance(tickets, list) or not isinstance(deleted, list):
            return self._json({'error': "'tickets' and 'deleted' must be lists"}, 400)
        if len(tickets) + len(deleted) > MAX_BATCH:
            return self._json({'error': 'batch too large (max %s)' % MAX_BATCH}, 400)
        result = request.env['rotana.weighbridge.ticket'].sudo().sync_from_agent(payload)
        return self._json(result)
