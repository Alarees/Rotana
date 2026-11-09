{
    'name': 'Rotana Weighbridge',
    'version': '19.0.1.0.0',
    'summary': 'SmartBridge weighbridge tickets matched to fleet vehicles by plate number, with a daily dashboard',
    'category': 'Operations',
    'author': 'Rotana',
    'license': 'LGPL-3',
    'depends': ['base', 'fleet', 'rotana_fleet', 'rotana_transport_sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/ir_config_parameter.xml',
        'views/weighbridge_ticket_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rotana_weighbridge/static/src/dashboard/dashboard.js',
            'rotana_weighbridge/static/src/dashboard/dashboard.xml',
            'rotana_weighbridge/static/src/dashboard/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
}
