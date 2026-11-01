# -*- coding: utf-8 -*-
{
    'name': 'Rotana Management Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Dashboards',
    'summary': 'لوحة إدارة حية: مبيعات الشركات الفرعية (أوامر البيع المؤكدة)',
    'description': """
Rotana Development - HQ
Management Dashboard
====================
- قسم المبيعات: مراقبة مبيعات كل شركة فرعية (أوامر البيع المؤكدة) بصورة حية.
- بطاقات ملخص + بطاقة لكل شركة + مخطط مقارنة + لوحة تفاصيل جانبية.
- فلاتر: الشركات والتاريخ مع اقتراحات سريعة.
- رسوم amCharts 5 (محلية داخل المديول) وخلفية متحركة.
- تحديث حي عبر bus مع تحديث دوري احتياطي.
- أقسام أخرى تُضاف لاحقاً (انظر SECTIONS في dashboard.js).
""",
    'author': 'Rotana Development - HQ',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'bus', 'sale'],
    'data': [
        'security/security.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rotana_management_dashboard/static/src/css/dashboard.css',
            'rotana_management_dashboard/static/src/js/dashboard.js',
            'rotana_management_dashboard/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
