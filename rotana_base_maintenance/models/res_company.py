# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    maintenance_expense_account_id = fields.Many2one(
        'account.account',
        string='Spare Parts Expense Account',
        help='Debit account of the spare-parts consumption entry. '
             'If empty, the expense account of the product category is used.',
    )
    maintenance_journal_id = fields.Many2one(
        'account.journal',
        string='Maintenance Journal',
        domain="[('type', '=', 'general')]",
        help='Journal of the spare-parts entry. If empty, the first miscellaneous journal is used.',
    )
    maintenance_out_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Delivery Operation Type',
        domain="[('code', '=', 'outgoing'), ('company_id', '=', id)]",
        help='Default operation type of the delivery order created when spare parts are confirmed. '
             'If empty, the delivery type of the company warehouse is used.',
    )
    maintenance_in_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Receipt Operation Type',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]",
        help='Default operation type of the receipt for fleet spare parts.',
    )
    maintenance_scrap_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Scrap Operation Type',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]",
        help='Receipt operation type for spare parts whose state is scrap.',
    )
    maintenance_rehab_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Rehabilitation Operation Type',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]",
        help='Receipt operation type for spare parts whose state is rehabilitation.',
    )
    maintenance_scrap_value_percent = fields.Float(
        string='Scrap Receipt Value (%)',
        default=0.0,
        help='Value of a scrap spare part when it returns to stock, as a percentage of the '
             "product's cost. 0 means it enters stock at zero value. Decided by finance.",
    )
    maintenance_rehab_value_percent = fields.Float(
        string='Rehabilitated Receipt Value (%)',
        default=100.0,
        help='Value of a rehabilitated spare part when it returns to stock, as a percentage of '
             "the product's cost. Decided by finance.",
    )

    @api.constrains('maintenance_scrap_value_percent', 'maintenance_rehab_value_percent')
    def _check_maintenance_value_percent(self):
        for company in self:
            for percent in (company.maintenance_scrap_value_percent,
                            company.maintenance_rehab_value_percent):
                if percent < 0.0 or percent > 100.0:
                    raise ValidationError(_('The receipt value percentage must be between 0 and 100.'))
