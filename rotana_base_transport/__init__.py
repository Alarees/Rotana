# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """ترحيل القيم القديمة من إعدادات النظام (ir.config_parameter) إلى حقول الشركة.

    كانت الخطة التحليلية الأم والعجز المسموح مخزنين كمعاملات نظام عامة في
    rotana_transport_sale؛ تُنسخ الآن لكل شركة لم تُحدَّد لها قيمة.
    """
    params = env['ir.config_parameter'].sudo()
    plan_param = params.get_param('rotana_transport_sale.parent_analytic_plan_id')
    deficit_param = params.get_param('rotana_transport_sale.allowable_deficit')
    plan_id = int(plan_param) if plan_param and str(plan_param).isdigit() else False
    if plan_id and not env['account.analytic.plan'].sudo().browse(plan_id).exists():
        plan_id = False
    try:
        deficit = float(deficit_param) if deficit_param else 0.0
    except ValueError:
        deficit = 0.0
    for company in env['res.company'].sudo().search([]):
        vals = {}
        if plan_id and not company.parent_analytic_plan_id:
            vals['parent_analytic_plan_id'] = plan_id
        if deficit and not company.allowable_deficit:
            vals['allowable_deficit'] = deficit
        if vals:
            company.write(vals)
