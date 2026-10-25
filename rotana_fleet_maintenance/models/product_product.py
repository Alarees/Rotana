# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # حقل للفلترة فقط (القائمة الجانبية في كتالوج قطع الغيار):
    # يُرجع المنتجات التي يتوفر منها رصيد موجب داخل المخزن المحدد.
    maintenance_warehouse_id = fields.Many2one(
        'stock.warehouse', string='المخزن',
        compute='_compute_maintenance_warehouse_id',
        search='_search_maintenance_warehouse_id',
    )

    @api.depends_context('allowed_company_ids')
    def _compute_maintenance_warehouse_id(self):
        self.maintenance_warehouse_id = False

    def _search_maintenance_warehouse_id(self, operator, value):
        """ قائمة البحث الجانبية قد ترسل عوامل مختلفة (=, in, child_of ...)،
        لذلك نحوّل أي عامل إلى مجموعة مخازن ثم نبحث عن رصيدها. """
        negative = operator in ('!=', 'not in')
        if operator in ('=', '!=', 'in', 'not in', 'child_of', 'parent_of'):
            ids = value if isinstance(value, (list, tuple, set)) else [value]
            warehouses = self.env['stock.warehouse'].browse([w for w in ids if isinstance(w, int)])
        else:
            warehouses = self.env['stock.warehouse'].search([('id', operator, value)])
        locations = warehouses.view_location_id
        product_ids = []
        if locations:
            groups = self.env['stock.quant'].sudo()._read_group(
                [('location_id', 'child_of', locations.ids), ('quantity', '>', 0)],
                groupby=['product_id'],
            )
            product_ids = [product.id for (product,) in groups]
        return [('id', 'not in' if negative else 'in', product_ids)]
