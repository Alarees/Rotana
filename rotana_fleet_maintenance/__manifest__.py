# -*- coding: utf-8 -*-
{
    'name': 'Rotana Fleet Maintenance',
    'version': '19.0.2.0.0',
    'category': 'Maintenance',
    'summary': 'صيانة مركبات روتانا: تطبيق مستقل بطلبات الصيانة وقطع الغيار والمنصرفات والورشة الخارجية',
    'description': """
        تطبيق صيانة المركبات لشركة روتانا (مستقل عن مديول Maintenance القياسي):
        - طلب صيانة بنفس بيانات استمارة الجوب: التاريخ، زمن الدخول والخروج، السائق، العداد، القسم والفني
        - فرق الصيانة (الأقسام) وفنيوها وألوانها، وجدول أعمال لكل طلب
        - شاشة اختيار قطع الغيار من المخزن (كتالوج المنتجات)
        - عند التأكيد: إذن تسليم مخزني، وعند الإكمال: قيد يومية لإنقاص قيمة المخزون مربوط بالحساب التحليلي للمركبة
        - منصرفات الصيانة وفواتير الموردين
        - الورشة الخارجية (صيانة الاسبير - تأهيل)
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
        'product',
        'account',
        'analytic',
        'stock',
        'stock_account',
        'fleet',
        'rotana_base_maintenance',
        'rotana_transport_sale',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/data.xml',
        'views/request_views.xml',
        'views/config_views.xml',
        'views/catalog_views.xml',
        'views/external_workshop_views.xml',
        'views/stock_picking_views.xml',
        'views/fleet_vehicle_view.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
