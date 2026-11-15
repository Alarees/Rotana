# -*- coding: utf-8 -*-
{
    'name': 'Rotana Warehouse Gate Keeper',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Full-screen dashboard for the warehouse gate keeper: scan a receipt/delivery slip barcode and edit the delivery info',
    'description': """
        Warehouse gate keeper dashboard:
        - Full-screen dashboard with a barcode search box at the top center.
        - Scan the barcode of a stock receipt or delivery slip: completion status, customer, date,
          products with quantities, total weight per product and the total net weight.
        - Everything is read-only except driver name, truck plate number and driver phone
          of the "Delivery Info & Transport" tab; changes are recorded under the dashboard user.
        - New group "Gate Keeper", lower than the warehouse user (warehouse users inherit it).
        - The delivery info fields (x_*) are created in the database, not in this module: they are
          shown only when they exist on stock.picking.
    """,
    'author': 'Rotana Development - IT Department',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'stock'],
    'data': [
        'security/security.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rotana_gate_keeper/static/src/css/gate_keeper.css',
            'rotana_gate_keeper/static/src/js/gate_keeper.js',
            'rotana_gate_keeper/static/src/xml/gate_keeper.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
