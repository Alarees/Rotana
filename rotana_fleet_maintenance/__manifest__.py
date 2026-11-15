# -*- coding: utf-8 -*-
{
    'name': 'Rotana Fleet Maintenance',
    'version': '19.0.2.0.0',
    'category': 'Maintenance',
    'summary': 'Rotana fleet maintenance: standalone app for maintenance requests, spare parts, expenses and external maintenance',
    'description': """
        Rotana fleet maintenance app (standalone, independent of the standard Maintenance module):
        - Maintenance request following the job card: date, entry/exit time, driver and odometer
        - Maintenance teams (sections) with their technicians and colors, and a works table per request
        - Spare parts selection screen from the warehouse (product catalog)
        - On confirmation: stock delivery order; on completion: journal entry decreasing the stock value linked to the vehicle analytic account
        - Maintenance expenses and vendor bills
        - External maintenance (spare part rehabilitation)
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
