# -*- coding: utf-8 -*-
{
    'name': 'Rotana Employee Performance KPI Dashboards',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Dashboards',
    'summary': 'لوحات مؤشرات أداء الموظفين لمديولات المبيعات والمشتريات والحسابات والمخازن والتصنيع',
    'description': """
Rotana Development - HQ
Employee Performance KPI Dashboards
=====================================
- Sales KPIs (per Salesperson)
- Purchase KPIs (per Buyer)
- Accounting KPIs (per Accountant)
- Inventory KPIs (per Warehouse Keeper)
- Manufacturing KPIs (per Production Supervisor)

Built with vanilla JavaScript (no framework), Chart.js, and a manual
Material Design look (Google Material color/typography tokens via CSS).
Filters: Company/Branch, Date Range.
""",
    'author': 'Rotana Development - HQ',
    'license': 'LGPL-3',
    'depends': ['base', 'sale_management', 'purchase', 'account', 'stock', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rotana_kpi_dashboard/static/src/js/dashboard_client_action.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
