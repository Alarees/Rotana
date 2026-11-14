# -*- coding: utf-8 -*-
{
    'name': 'Rotana Base Transport',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': 'Company settings foundation for Rotana transport and fleet modules',
    'description': """
        المديول الأساسي الأول (يُثبَّت قبل أي مديول نقل أو صيانة):
        - الخطة التحليلية الأم للمركبات (تُستخدم في مبيعات النقل وصيانة المركبات)
        - العجز المسموح الافتراضي
        - حساب ودفتر العهدة
        الحقول على الشركة (res.company) وفي الإعدادات (res.config.settings).
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'analytic'],
    'data': [
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
