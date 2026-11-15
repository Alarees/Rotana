# -*- coding: utf-8 -*-
{
    'name': 'Rotana Delivery Info (TEST ONLY)',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'TEST ONLY: defines the "Delivery Info & Transport" fields and tab on stock.picking for test databases',
    'description': """
        For test databases only. Do NOT install on the production database, where these fields
        already exist (created manually) and would clash with the fields defined here.

        Adds the "Delivery Info & Transport" tab to the stock picking form with:
        - Transport type (customer / company)
        - Driver name, truck plate number, driver phone
        - Destination, customer tax ID, agent customer name
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
