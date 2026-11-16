# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GROUP_XMLID = 'rotana_gate_keeper.group_rotana_gate_keeper'

# Fields of the "Delivery Info & Transport" tab. They are created in the database (not in this
# module), so each one is shown only if it exists on stock.picking.
INFO_FIELDS = (
    'x_transport_type',
    'x_driver_name',
    'x_truck_plate_number',
    'x_driver_phone',
    'x_destination',
    'x_customer_tax_id',
    'agent_customer_name',
)
# The only fields the gate keeper may change.
EDITABLE_FIELDS = ('x_driver_name', 'x_truck_plate_number', 'x_driver_phone')


class RotanaGateKeeper(models.AbstractModel):
    _name = 'rotana.gate.keeper'
    _description = 'Warehouse gate keeper dashboard'

    # ------------------------------------------------------------------ access
    def _check_gate_access(self):
        if not self.env.user.has_group(GROUP_XMLID):
            raise AccessError(_('You are not allowed to use the warehouse gate dashboard.'))

    def _picking_domain(self):
        # sudo() bypasses record rules, so the allowed companies are applied here.
        return [
            ('picking_type_code', 'in', ('incoming', 'outgoing')),
            ('company_id', 'in', self.env.companies.ids),
        ]

    def _get_picking(self, picking_id):
        # sudo() keeps the current uid: writes and chatter stay attributed to the dashboard user.
        picking = self.env['stock.picking'].sudo().search(
            self._picking_domain() + [('id', '=', int(picking_id))], limit=1)
        if not picking:
            raise AccessError(_('This receipt/delivery slip is not available.'))
        return picking

    # ------------------------------------------------------------------ public API
    @api.model
    def search_picking(self, barcode):
        """Find a receipt / delivery slip by its barcode (the slip number); False when not found."""
        self._check_gate_access()
        code = (barcode or '').strip()
        if not code:
            return False
        picking = self._find_picking(code)
        return self._picking_payload(picking) if picking else False

    def _find_picking(self, code):
        """Find the slip among the companies currently selected in the company switcher.

        Slip numbers are unique per company only, so the same number can exist in several companies.
        """
        Picking = self.env['stock.picking'].sudo()
        domain = self._picking_domain()
        escaped = code.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pickings = Picking.search(domain + [('name', '=', code)])
        if not pickings:
            pickings = Picking.search(domain + [('name', '=ilike', escaped)])
        if len(pickings) > 1:
            # Same number in several selected companies: prefer the current company.
            pickings = pickings.filtered(lambda p: p.company_id == self.env.company) or pickings
            if len(pickings) > 1:
                raise UserError(_(
                    'رقم الإذن موجود في أكثر من شركة. اختر الشركة المطلوبة فقط من مبدل الشركات ثم أعد المسح.'))
        if pickings:
            return pickings
        # Not in the selected companies: tell the user when it belongs to another company they can access
        # (never reveal slips of companies the user has no access to).
        other_companies = self.env.user.company_ids - self.env.companies
        if other_companies:
            other = Picking.search([
                ('picking_type_code', 'in', ('incoming', 'outgoing')),
                ('company_id', 'in', other_companies.ids),
                ('name', '=', code),
            ], limit=1)
            if other:
                raise UserError(_(
                    'هذا الإذن يتبع شركة "%s". فعّل هذه الشركة من مبدل الشركات ثم أعد المسح.',
                    other.company_id.name))
        return Picking.browse()

    @api.model
    def save_delivery_info(self, picking_id, values):
        """Save the editable delivery info fields only; anything else sent is ignored."""
        self._check_gate_access()
        picking = self._get_picking(picking_id)
        meta = picking.fields_get(list(EDITABLE_FIELDS), attributes=['string'])
        vals = {}
        for name, value in (values or {}).items():
            if name in EDITABLE_FIELDS and name in picking._fields:
                vals[name] = (value or '').strip() or False
        changes = [
            (meta[name]['string'], picking[name], new)
            for name, new in vals.items() if (picking[name] or False) != new
        ]
        if changes:
            picking.write(vals)
            lines = Markup('').join(
                Markup('<li>%s: %s &rarr; %s</li>') % (label, old or '-', new or '-')
                for label, old, new in changes
            )
            picking.message_post(
                body=Markup('<p>%s</p><ul>%s</ul>') % (_('Delivery info updated from the gate dashboard'), lines),
                subtype_xmlid='mail.mt_note',
            )
        return self._picking_payload(picking)

    # ------------------------------------------------------------------ payload
    def _picking_payload(self, picking):
        states = dict(picking._fields['state']._description_selection(self.env))
        is_done = picking.state == 'done'
        date = picking.date_done if is_done else picking.scheduled_date

        lines = {}
        for move in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
            product = move.product_id
            qty = move.quantity if is_done else move.product_uom_qty
            qty_in_product_uom = move.product_uom._compute_quantity(qty, product.uom_id, round=False)
            key = (product.id, move.product_uom.id)
            line = lines.setdefault(key, {
                'product': product.display_name,
                'uom': move.product_uom.display_name,
                'qty': 0.0,
                'unit_weight': product.weight,
                'weight': 0.0,
            })
            line['qty'] += qty
            line['weight'] += qty_in_product_uom * product.weight
        moves = list(lines.values())
        for line in moves:
            line['weight'] = round(line['weight'], 3)

        template = self.env['product.template']
        weight_uom = (
            template._get_weight_uom_name_from_ir_config_parameter()
            if hasattr(template, '_get_weight_uom_name_from_ir_config_parameter') else 'kg'
        )
        return {
            'id': picking.id,
            'name': picking.name,
            'state': picking.state,
            'state_label': states.get(picking.state, picking.state),
            'is_done': is_done,
            'type': picking.picking_type_code,
            'type_label': 'استلام' if picking.picking_type_code == 'incoming' else 'تسليم',
            'company': picking.company_id.display_name or False,
            'partner': picking.partner_id.display_name or False,
            'date': fields.Datetime.to_string(date) if date else False,
            'moves': moves,
            'total_weight': round(sum(line['weight'] for line in moves), 3),
            'weight_uom': weight_uom,
            'missing_weight': any(not line['unit_weight'] for line in moves),
            'fields': self._delivery_fields_payload(picking),
        }

    def _delivery_fields_payload(self, picking):
        names = [name for name in INFO_FIELDS if name in picking._fields]
        if not names:
            return []
        meta = picking.fields_get(names, attributes=['string', 'type', 'selection'])
        result = []
        for name in names:
            ftype = meta[name]['type']
            value = picking[name]
            item = {
                'name': name,
                'label': meta[name]['string'],
                'type': ftype,
                'editable': name in EDITABLE_FIELDS and ftype == 'char',
            }
            if ftype == 'selection':
                selection = meta[name]['selection']
                item['value'] = value or ''
                item['display'] = dict(selection).get(value, '')
            elif ftype == 'many2one':
                item['value'] = item['display'] = value.display_name or ''
            elif ftype == 'boolean':
                item['value'] = bool(value)
                item['display'] = 'نعم' if value else 'لا'
            else:
                item['value'] = item['display'] = str(value) if value else ''
            result.append(item)
        return result
