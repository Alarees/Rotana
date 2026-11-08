# -*- coding: utf-8 -*-
{
    'name': 'Rotana Audit Review',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'مراجعة سجل Audit Trail: تمت المراجعة / مرفوضة / إضافة مهمة',
    'description': """
        مراجعة داخلية لسجل Audit Trail لشركة روتانا:
        - حالة مراجعة لكل سجل مُراقَب: قيود اليومية، الحسابات، الضرائب، الشركاء، الشركات
        - الحالات: بانتظار المراجعة / تمت المراجعة / مرفوضة (مع سبب إلزامي)
        - إضافة مهمة (Activity) مرتبطة بالسجل
        - تظهر الحالة في أعلى الشاشة وفي شاشة Audit Trail فقط عند تفعيل Audit Trail في إعدادات الشركة
        - أي تعديل (مسجَّل في السجل) بعد المراجعة يُعيد الحالة تلقائياً إلى بانتظار المراجعة
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/audit_review_wizard_views.xml',
        'views/audit_review_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
