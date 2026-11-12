# -*- coding: utf-8 -*-
{
    'name': 'Rotana Audit Review - HR',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'إضافة الموارد البشرية إلى سجل Audit Trail ومراجعته',
    'description': """
        يوسّع مديول rotana_audit_review ليشمل الموارد البشرية:
        الموظفون، نسخ العقد (hr.version)، قسائم الرواتب ودفعاتها، الإجازات ومخصصاتها،
        المصروفات، الحضور، الأقسام، الوظائف، التقييمات.
        - تظهر تغييراتها في شاشة Audit Trail مع عمود نوع السجل واسمه وفلاتر خاصة
        - حالة المراجعة (تمت المراجعة / مرفوضة / مهمة) في كل سجل
        - تغيير حقل state (حالة سير العمل) لا يُعيد الحالة إلى بانتظار المراجعة، بل تغيير البيانات فقط
        - المراجع الداخلي يرى سجلات HR (بما فيها الرواتب) قراءة فقط
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': [
        'rotana_audit_review',
        'hr',
        'hr_holidays',
        'hr_payroll',
        'hr_expense',
        'hr_attendance',
        'hr_appraisal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/hr_audit_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
