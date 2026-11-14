# -*- coding: utf-8 -*-
{
    'name': 'Rotana Base Maintenance',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': 'Company settings foundation for Rotana fleet maintenance',
    'description': """
        المديول الأساسي الثاني (يُثبَّت قبل صيانة المركبات والورشة الخارجية):
        - حساب مصروف قطع الغيار ودفتر يومية الصيانة
        - أنواع عمليات التسليم والاستلام والتالف والتأهيل
        الخطة التحليلية للمركبات هي "الخطة الأم" المعرَّفة في rotana_base_transport
        ولا تُنشأ هنا مرة أخرى.
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'stock', 'rotana_base_transport'],
    'data': [
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
