# -*- coding: utf-8 -*-
{
    'name': 'Rotana Transport Sale',
    'version': '19.0.1.0.3',
    'category': 'Sales/Transport',
    'summary': 'نظام إدارة مبيعات خدمات النقل لشركة روتانا',
    'description': """
        مديول خاص بشركة روتانا للنقل يوفر:
        - قائمة مبيعات خاصة بخدمات النقل
        - إدارة مواقع النقل
        - ربط أوامر البيع بالرحلات تلقائياً
        - إضافة العربة والسائق ومواقع الانطلاق والوصول
        - الحساب التحليلي لكل سطر في أمر البيع
        - تتبع حالة الرحلات
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'sale',
        'sale_management',
        'analytic',
        'fleet',
    ],
    'data': [
        'security/rotana_transport_sale_security.xml',
        'security/ir.model.access.csv',
        'data/rotana_transport_sale_sequences.xml',
        'views/rotana_transport_location_views.xml',
        'views/rotana_transport_vehicle_views.xml',
        'views/rotana_transport_driver_views.xml',
        'views/rotana_transport_trip_views.xml',
        'views/rotana_transport_sale_order_views.xml',
        'views/fleet_vehicle_view.xml',
        'views/res_config_settings.xml',
        'views/rotana_transport_trip_wizard_views.xml',
        'views/fleet_vehicle_log_views.xml',
        'views/rotana_transport_trip_note_views.xml',
        'views/rotana_transport_trip_custody_views.xml',
        'views/rotana_transport_menus.xml',
        'report/rotana_transport_dashboard_report.xml',
        'views/rotana_transport_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rotana_transport_sale/static/src/dashboard/**/*',
            'rotana_transport_sale/static/src/scss/trip_note_timeline.scss',
            'rotana_transport_sale/static/src/scss/transport_order_kanban.scss',
        ],
    },
    'external_dependencies': {'python': ['xlsxwriter']},
    "images":  ['static/src/logo.jpeg'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
