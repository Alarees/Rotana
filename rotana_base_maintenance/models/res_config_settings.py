# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    maintenance_expense_account_id = fields.Many2one(
        related='company_id.maintenance_expense_account_id', readonly=False)
    maintenance_journal_id = fields.Many2one(
        related='company_id.maintenance_journal_id', readonly=False)
    maintenance_out_picking_type_id = fields.Many2one(
        related='company_id.maintenance_out_picking_type_id', readonly=False)
    maintenance_in_picking_type_id = fields.Many2one(
        related='company_id.maintenance_in_picking_type_id', readonly=False)
    maintenance_scrap_picking_type_id = fields.Many2one(
        related='company_id.maintenance_scrap_picking_type_id', readonly=False)
    maintenance_rehab_picking_type_id = fields.Many2one(
        related='company_id.maintenance_rehab_picking_type_id', readonly=False)
