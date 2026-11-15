# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RotanaMaintenancePart(models.Model):
    _name = 'rotana.maintenance.part'
    _description = 'Maintenance Spare Part'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    request_id = fields.Many2one(
        'rotana.maintenance.request', string='Maintenance Request',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    parts_state = fields.Selection(related='request_id.parts_state')
    product_id = fields.Many2one(
        'product.product', string='Spare Part', required=True,
        domain="[('type', '=', 'consu'), ('is_storable', '=', True)]",
    )
    team_id = fields.Many2one('rotana.maintenance.team', string='Section')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    spare_state = fields.Selection(
        [('scrap', 'Scrap'), ('rehab', 'Rehabilitation')],
        string='Spare State', default='scrap', required=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Operation Type',
        compute='_compute_picking_type_id', store=True, readonly=False,
        domain="[('code', '=', 'incoming')]",
        help='Operation type of the receipt, set automatically from the company settings according to the spare state.',
    )
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unit')
    qty_available = fields.Float(related='product_id.qty_available', string='Available')
    unit_cost = fields.Float(compute='_compute_unit_cost', string='Cost')
    subtotal = fields.Monetary(compute='_compute_subtotal', string='Total')

    @api.depends('spare_state', 'request_id.company_id')
    def _compute_picking_type_id(self):
        for line in self:
            company = line.request_id.company_id or self.env.company
            if line.spare_state == 'rehab':
                line.picking_type_id = company.maintenance_rehab_picking_type_id
            else:
                line.picking_type_id = company.maintenance_scrap_picking_type_id

    @api.depends('product_id', 'request_id.company_id')
    def _compute_unit_cost(self):
        for line in self:
            company = line.request_id.company_id or self.env.company
            line.unit_cost = line.product_id.with_company(company).standard_price

    @api.depends('quantity', 'unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('The spare part quantity must be greater than zero.'))

    @api.constrains('request_id', 'product_id')
    def _check_unique_product(self):
        for line in self:
            if len(line.request_id.part_line_ids.filtered(
                    lambda l: l.product_id == line.product_id)) > 1:
                raise ValidationError(_(
                    'The spare part %s is duplicated in the same request, change its quantity instead.',
                    line.product_id.display_name))

    # ------------------------------------------------------------------
    # Lines are locked after confirmation
    # ------------------------------------------------------------------
    def _check_request_editable(self):
        if self.env.context.get('skip_part_editable_check'):
            return
        for line in self:
            if line.request_id.parts_state != 'draft':
                raise UserError(_('Spare parts cannot be modified after the request is confirmed.'))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_request_editable()
        return lines

    def write(self, vals):
        self._check_request_editable()
        res = super().write(vals)
        if 'product_id' in vals:
            # Changing the spare on a maintenance line is propagated to external maintenance requests not yet sent
            workshops = self.env['rotana.external.workshop'].sudo().search([
                ('part_line_id', 'in', self.ids),
                ('state', 'in', ('draft', 'confirmed')),
            ])
            if workshops:
                workshops.write({'product_id': vals['product_id']})
        return res

    def unlink(self):
        self._check_request_editable()
        return super().unlink()

    # ------------------------------------------------------------------
    # Product catalog support (product.catalog.mixin)
    # ------------------------------------------------------------------
    def _get_product_catalog_lines_data(self, parent_record=False, **kwargs):
        """ Line data shown by the catalog (quantity, price ...). """
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
