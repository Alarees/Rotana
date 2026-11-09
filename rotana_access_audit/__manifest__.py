# -*- coding: utf-8 -*-
{
    'name': 'Rotana Access Audit',
    'version': '19.0.1.0.0',
    'category': 'Administration',
    'summary': 'تتبع تغييرات صلاحيات المستخدمين والمجموعات وحقوق الوصول (Access Rights)',
    'description': """
        سجل مستقل ودائم لتغييرات الصلاحيات في شركة روتانا:
        - المستخدمون: إضافة/إزالة المجموعات، الشركات المسموحة، تغيير اسم الدخول، الأرشفة، الإنشاء والحذف
        - المجموعات: تغيير المستخدمين المنتمين للمجموعة، والمجموعات المضمّنة
        - حقوق الوصول (ir.model.access) وقواعد السجلات (ir.rule): إنشاء، تعديل، حذف
        - السجل للقراءة فقط ولا يمكن تعديله أو حذفه (يبقى للأبد)
        - لا يُسجَّل شيء أثناء تثبيت/تحديث المديولات (install_mode)
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/access_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
