# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MaintenanceRequestPart(models.Model):
    _name = 'maintenance.request.part'
    _description = 'قطعة غيار في طلب صيانة'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one(
        'maintenance.request', string='طلب الصيانة',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    parts_state = fields.Selection(related='request_id.parts_state')
    product_id = fields.Many2one(
        'product.product', string='قطعة الغيار', required=True,
        domain="[('type', '=', 'consu'), ('is_storable', '=', True)]",
    )
    quantity = fields.Float(string='الكمية', default=1.0, required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='الوحدة')
    qty_available = fields.Float(related='product_id.qty_available', string='المتوفر')
    unit_cost = fields.Float(related='product_id.standard_price', string='التكلفة')
    subtotal = fields.Monetary(compute='_compute_subtotal', string='الإجمالي')

    @api.depends('quantity', 'unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('كمية قطعة الغيار يجب أن تكون أكبر من صفر.'))

    @api.constrains('request_id', 'product_id')
    def _check_unique_product(self):
        for line in self:
            if len(line.request_id.part_line_ids.filtered(
                    lambda l: l.product_id == line.product_id)) > 1:
                raise ValidationError(_(
                    'قطعة الغيار %s مكررة في نفس الطلب، عدّل الكمية بدلاً من التكرار.',
                    line.product_id.display_name))

    # ------------------------------------------------------------------
    # حماية السطور بعد التأكيد
    # ------------------------------------------------------------------
    def _check_request_editable(self):
        for line in self:
            if line.request_id.parts_state != 'draft':
                raise UserError(_('لا يمكن تعديل قطع الغيار بعد تأكيد الطلب.'))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_request_editable()
        return lines

    def write(self, vals):
        self._check_request_editable()
        return super().write(vals)

    def unlink(self):
        self._check_request_editable()
        return super().unlink()

    # ------------------------------------------------------------------
    # دعم كتالوج المنتجات (product.catalog.mixin)
    # ------------------------------------------------------------------
    def _get_product_catalog_lines_data(self, parent_record=False, **kwargs):
        """ بيانات السطور التي يعرضها الكتالوج (الكمية والسعر ...). """
        if len(self) == 1:
            return {
                'quantity': self.quantity,
                'price': self.unit_cost,
                'readOnly': self.request_id._is_readonly(),
                'uomDisplayName': self.uom_id.display_name,
            }
        if self:
            self.product_id.ensure_one()
            return {
                'quantity': sum(self.mapped('quantity')),
                'price': self[0].unit_cost,
                'readOnly': True,
                'uomDisplayName': self[0].uom_id.display_name,
            }
        return {
            'quantity': 0,
            'readOnly': False,
        }
