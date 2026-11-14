# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    maintenance_request_id = fields.Many2one(
        'maintenance.request',
        string='طلب الصيانة',
        copy=False,
        index='btree_not_null',
    )
    fleet_id = fields.Many2one(
        'fleet.vehicle',
        string='المركبة',
        copy=False,
        index='btree_not_null',
        tracking=True,
    )
    is_fleet_operation = fields.Boolean(
        related='picking_type_id.is_fleet_operation',
        string='عملية مركبات',
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    maintenance_part_id = fields.Many2one(
        'maintenance.request.part',
        string='سطر قطعة الغيار',
        copy=False,
        index='btree_not_null',
        ondelete='set null',
        help='سطر قطعة الغيار في طلب الصيانة المرتبط بهذا السطر في إذن التسليم.',
    )

    def _get_maintenance_part(self):
        """ سطر قطعة الغيار المرتبط بسطر إذن التسليم (بالربط المباشر أو بالطلب والمنتج). """
        self.ensure_one()
        if self.maintenance_part_id:
            return self.maintenance_part_id
        picking = self.picking_id
        if picking.maintenance_request_id and picking.picking_type_code == 'outgoing':
            return self.env['maintenance.request.part'].sudo().search([
                ('request_id', '=', picking.maintenance_request_id.id),
                ('product_id', '=', self.product_id.id),
            ], limit=1)
        return self.env['maintenance.request.part']

    def write(self, vals):
        if 'product_id' in vals:
            for move in self:
                if move.product_id.id != vals['product_id'] and move._get_maintenance_part():
                    raise UserError(_(
                        'لا يمكن تغيير المنتج في سطر إذن مرتبط بطلب صيانة. '
                        'ألغِ التأكيد في طلب الصيانة وعدّل قطعة الغيار هناك.'))
        return super().write(vals)

    # ------------------------------------------------------------------
    # قيمة القطع التالفة / المؤهلة عند عودتها للمخزن
    # ------------------------------------------------------------------
    def _get_maintenance_receipt_percent(self):
        """نسبة قيمة هذه الحركة من تكلفة الصنف إن كانت استلام قطعة تالفة/مؤهلة
        مرتبطة بطلب صيانة، وإلا None (تقييم أودو المعتاد)."""
        self.ensure_one()
        picking = self.picking_id
        request = picking.maintenance_request_id
        if not request or not self.is_in:
            return None
        line = request.part_line_ids.filtered(
            lambda l: l.product_id == self.product_id
            and l.picking_type_id == picking.picking_type_id)[:1]
        if not line:
            return None
        company = self.company_id
        if line.spare_state == 'rehab':
            return company.maintenance_rehab_value_percent
        return company.maintenance_scrap_value_percent

    def _get_value_from_quotation(self, quantity, at_date=None):
        """أودو 19 يقيّم حركة الاستلام بتكلفة المنتج الكاملة إذا لم يوجد أمر شراء.
        القطع التالفة/المؤهلة تُقيَّم بنسبة من التكلفة حسب إعدادات الشركة (قرار المالية)."""
        result = super()._get_value_from_quotation(quantity, at_date=at_date)
        if result.get('quantity'):
            return result
        percent = self._get_maintenance_receipt_percent()
        if percent is None:
            return result
        cost = self.product_id.with_company(self.company_id).standard_price
        return {
            'value': cost * quantity * percent / 100.0,
            'quantity': quantity,
            'description': _('قطعة صيانة عائدة للمخزن بنسبة %(percent)s%% من تكلفة الصنف', percent=percent),
        }
