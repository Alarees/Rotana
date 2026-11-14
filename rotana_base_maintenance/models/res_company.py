# -*- coding: utf-8 -*-
from odoo import fields, models


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
