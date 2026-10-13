{
    'name': 'Bank Statement PDF Upload (Bank of Khartoum)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Upload and read Bank of Khartoum PDF statements and post them to bank statement lines',
    'depends': ['account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
