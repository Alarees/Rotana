# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    workshop_ids = fields.One2many(
        'rotana.external.workshop', 'maintenance_request_id',
        string='طلبات الورشة الخارجية', copy=False)

    def _get_receipt_lines(self):
        """ سطور (تأهيل) لا يصدر لها إذن استلام هنا: يُنشأ لها طلب ورشة خارجية بدلاً منه. """
        return super()._get_receipt_lines().filtered(lambda l: l.spare_state != 'rehab')

    def action_confirm_parts(self):
        to_confirm = self.filtered(lambda r: r.parts_state == 'draft')
        res = super().action_confirm_parts()
        for request in to_confirm:
            request._create_workshop_requests()
        return res

    def _create_workshop_requests(self):
        """ طلب صيانة اسبير (مسودة) لكل سطر اسبير حالته تأهيل. """
        self.ensure_one()
        Workshop = self.env['rotana.external.workshop'].sudo()
        for line in self.part_line_ids.filtered(lambda l: l.spare_state == 'rehab'):
            if Workshop.search_count([('part_line_id', '=', line.id)]):
                continue
            Workshop.create({
                'maintenance_request_id': self.id,
                'fleet_id': self.fleet_id.id,
                'part_line_id': line.id,
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'company_id': self.company_id.id,
                'picking_type_id': (line.picking_type_id
                                    or self.company_id.maintenance_rehab_picking_type_id).id,
            })

    def action_reset_parts(self):
        to_reset = self.filtered(lambda r: r.parts_state == 'confirmed')
        workshops = to_reset.workshop_ids.filtered('part_line_id')
        sent = workshops.filtered(lambda w: w.state not in ('draft', 'confirmed'))
        if sent:
            raise UserError(_(
                'لا يمكن إلغاء التأكيد لأن طلبات الورشة التالية دخلت الورشة:\n%s',
                '\n'.join('- %s' % w.name for w in sent)))
        res = super().action_reset_parts()
        workshops.sudo().unlink()
        return res
