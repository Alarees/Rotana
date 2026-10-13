# -*- coding: utf-8 -*-
{
    'name': 'Rotana - Weekly Customer Statement (WhatsApp)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Weekly PDF account statement per customer, sent automatically via WhatsApp',
    'description': """
Rotana Weekly Customer Statement
=================================
- Generates a PDF account statement (invoices, payments, running balance) for
  the current month, per customer.
- Provides a WhatsApp Business template that attaches this PDF and sends a
  short summary message (customer name, period, outstanding balance).
- Includes a weekly scheduled action (cron) that sends the statement + PDF
  to every customer with a mobile/phone number and outstanding activity.
""",
    'author': 'Rotana',
    'depends': ['base', 'account', 'whatsapp'],
    'data': [
        'security/ir.model.access.csv',
        'report/weekly_statement_report.xml',
        'data/whatsapp_template_data.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
