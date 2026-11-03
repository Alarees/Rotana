# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    maintenance_analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='الخطة التحليلية للمركبات',
        help='الخطة التي يُنشأ تحتها الحساب التحليلي لكل طلب صيانة. '
             'إن تُركت فارغة تُستخدم خطة "المركبات" الافتراضية.',
    )
    maintenance_expense_account_id = fields.Many2one(
        'account.account',
        string='حساب مصروف قطع الغيار',
        help='الحساب المدين في قيد استهلاك قطع الغيار. '
             'إن تُرك فارغاً يُستخدم حساب مصروف فئة المنتج.',
    )
    maintenance_journal_id = fields.Many2one(
        'account.journal',
        string='دفتر يومية الصيانة',
        domain="[('type', '=', 'general')]",
        help='الدفتر الذي يُسجَّل فيه قيد قطع الغيار. '
             'إن تُرك فارغاً يُستخدم أول دفتر متنوع (General).',
    )
    maintenance_out_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='عمليات التسليم',
        domain="[('code', '=', 'outgoing'), ('company_id', '=', id)]",
        help='نوع العملية الافتراضي لإذن التسليم الذي يُنشأ عند تأكيد قطع الغيار. '
             'إن تُرك فارغاً يُستخدم نوع \"تسليم\" في أول مستودع للشركة.',
    )
    maintenance_in_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='عمليات الاستلام',
        domain="[('code', '=', 'incoming'), ('company_id', '=', id)]",
        help='نوع العملية الافتراضي لإذن استلام قطع الغيار الخاصة بالمركبات.',
    )
