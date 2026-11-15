# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Filter-only field (side panel of the spare parts catalog):
    # Returns the products that have a positive stock inside the selected warehouse.
    maintenance_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Available in Warehouse',
        compute='_compute_maintenance_warehouse_id',
        search='_search_maintenance_warehouse_id',
    )

    @api.depends_context('allowed_company_ids')
    def _compute_maintenance_warehouse_id(self):
        self.maintenance_warehouse_id = False

    def _search_maintenance_warehouse_id(self, operator, value):
        """ The search panel may send different operators (=, in, child_of ...),
        so any operator is converted to a set of warehouses and their stock is searched. """
        negative = operator in ('!=', 'not in')
        if operator in ('=', '!=', 'in', 'not in', 'child_of', 'parent_of'):
            # Odoo 19 passes the value as an OrderedSet (not list/set), so convert it to a list of ids
            if isinstance(value, int):
                ids = [value]
            elif value and not isinstance(value, str):
                ids = list(getattr(value, 'ids', value))
            else:
                ids = []
            warehouses = self.env['stock.warehouse'].browse([w for w in ids if isinstance(w, int)])
        else:
            warehouses = self.env['stock.warehouse'].search([('id', operator, value)])
        # Only the warehouses of the companies allowed for the current user
        warehouses = warehouses.filtered(lambda w: w.company_id in self.env.companies)
        locations = warehouses.view_location_id
        product_ids = []
        if locations:
            groups = self.env['stock.quant'].sudo()._read_group(
                [('location_id', 'child_of', locations.ids), ('quantity', '>', 0),
                 ('company_id', 'in', self.env.companies.ids)],
                groupby=['product_id'],
            )
            product_ids = [product.id for (product,) in groups]
        return [('id', 'not in' if negative else 'in', product_ids)]
