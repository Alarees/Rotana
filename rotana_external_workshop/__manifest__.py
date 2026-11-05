# -*- coding: utf-8 -*-
{
    'name': 'Rotana External Workshop',
    'version': '19.0.1.0.0',
    'category': 'Maintenance',
    'summary': 'الورشة الخارجية: طلبات صيانة الاسبير (تأهيل) خارج الشركة',
    'description': """
        مديول الورشة الخارجية لشركة روتانا:
        - طلب صيانة اسبير لكل سطر اسبير حالته (تأهيل) في طلب صيانة المركبة
        - الحالات: مسودة ← مؤكد ← في الورشة ← تمت الصيانة
        - عند (تمت الصيانة): إذن استلام مؤكد آلياً + قيد يومية لتسوية قيمة المخزن
        - فوترة مورد بعد (تمت الصيانة)
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['rotana_fleet_maintenance'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/external_workshop_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
