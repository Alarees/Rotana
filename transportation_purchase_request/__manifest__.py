# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Transportation Purchase Request",
    "author": "Rotana Development - IT Department",
    "version": "19.0.2.1.0",
    "summary": "Use this module to have notification of requirements of "
    "materials and/or external services and keep track of such "
    "requirements.",
    "category": "Purchase Management",
    "depends": ["purchase_stock", "account"],
    "data": [
        "security/transportation_purchase_request.xml",
        "security/ir.model.access.csv",
        "data/transportation_purchase_request_sequence.xml",
        "reports/report_transportation_purchase_request.xml",
        "views/transportation_purchase_request_view.xml",
        "views/transportation_purchase_request_line_view.xml",
        "views/transportation_purchase_request_report.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
}
