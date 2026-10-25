# -*- coding: utf-8 -*-
{
    'name': 'Rotana Fleet Maintenance',
    'version': '19.0.1.1.0',
    'category': 'Maintenance',
    'summary': 'صيانة مركبات روتانا: قطع الغيار، إذن التسليم، الحساب التحليلي وقيد المخزون',
    'description': """
        مديول صيانة المركبات لشركة روتانا:
        - طلب صيانة خاص بالمركبات (Fleet)
        - شاشة اختيار قطع الغيار من المخزن (كتالوج المنتجات)
        - عند التأكيد: إصدار إذن تسليم مخزني + إنشاء حساب تحليلي تابع لخطة المركبات
        - عند إكمال الطلب: قيد يومية لإنقاص قيمة المخزون مربوط بالحساب التحليلي
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'account',
        'analytic',
        'stock',
        'stock_account',
        'fleet',
        'maintenance',
        'mrp_maintenance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/maintenance_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
