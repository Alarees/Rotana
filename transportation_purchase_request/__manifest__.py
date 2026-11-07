# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Transportation Purchase Request",
    "author": "ForgeFlow, Odoo Community Association (OCA), Rotana",
    "version": "19.0.2.0.0",
    "summary": "Use this module to have notification of requirements of "
    "materials and/or external services and keep track of such "
    "requirements.",
    "website": "https://github.com/OCA/purchase-workflow",
    "category": "Purchase Management",
    "depends": ["purchase_stock", "account"],
    "data": [
        "security/transportation_purchase_request.xml",
        "security/ir.model.access.csv",
        "data/transportation_purchase_request_sequence.xml",
        "data/transportation_purchase_request_data.xml",
        "reports/report_transportation_purchase_request.xml",
        "views/transportation_purchase_request_view.xml",
        "views/transportation_purchase_request_line_view.xml",
        "views/transportation_purchase_request_report.xml",
    ],
    "demo": ["demo/transportation_purchase_request_demo.xml"],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
