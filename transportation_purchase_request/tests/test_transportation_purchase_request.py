# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestPurchaseRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.request_model = cls.env["transportation.purchase.request"]
        cls.line_model = cls.env["transportation.purchase.request.line"]
        cls.transportation_purchase_request = cls.request_model.create(
            {"requested_by": SUPERUSER_ID}
        )
        cls.line = cls.line_model.create(
            {
                "description": "Test line",
                "request_id": cls.transportation_purchase_request.id,
                "product_qty": 5.0,
            }
        )

    def _make_approvers(self):
        """One different user per approval stage."""
        users = {}
        for stage, xmlid in (
            ("dept_manager", "group_pr_dept_manager"),
            ("accounts_head", "group_pr_accounts_head"),
            ("internal_audit", "group_pr_internal_auditor"),
            ("general_manager", "group_pr_general_manager"),
        ):
            users[stage] = self.env["res.users"].create(
                {
                    "name": f"Approver {stage}",
                    "login": f"pr_approver_{stage}",
                    "group_ids": [
                        (4, self.env.ref(f"transportation_purchase_request.{xmlid}").id)
                    ],
                }
            )
        return users

    def test_transportation_purchase_request_status(self):
        """Tests Transportation Purchase Request status workflow."""
        pr = self.transportation_purchase_request
        self.assertTrue(pr.is_editable)
        self.assertEqual(pr.state, "draft")
        pr.button_to_approve()
        self.assertEqual(pr.state, "dept_manager")
        self.assertFalse(pr.is_editable)
        with self.assertRaisesRegex(UserError, "which is not draft"):
            pr.unlink()
        # approve through the whole chain with a different user per stage
        users = self._make_approvers()
        for stage, nxt in (
            ("dept_manager", "accounts_head"),
            ("accounts_head", "internal_audit"),
            ("internal_audit", "general_manager"),
            ("general_manager", "approved"),
        ):
            getattr(pr.with_user(users[stage]), f"button_approve_{stage}")()
            self.assertEqual(pr.state, nxt)
            self.assertEqual(pr[f"{stage}_user_id"], users[stage])
            self.assertTrue(pr[f"{stage}_date"])
        self.assertFalse(pr.is_editable)
        pr.button_draft()
        self.assertEqual(pr.state, "draft")
        self.assertFalse(pr.dept_manager_user_id)
        self.assertFalse(pr.general_manager_date)
        self.assertTrue(pr.is_editable)
        pr.unlink()

    def test_same_person_cannot_approve_two_stages(self):
        pr = self.transportation_purchase_request
        pr.button_to_approve()
        user = self.env["res.users"].create(
            {
                "name": "Double approver",
                "login": "pr_double_approver",
                "group_ids": [
                    (4, self.env.ref("transportation_purchase_request.group_pr_dept_manager").id),
                    (4, self.env.ref("transportation_purchase_request.group_pr_accounts_head").id),
                ],
            }
        )
        pr.with_user(user).button_approve_dept_manager()
        with self.assertRaisesRegex(UserError, "different person"):
            pr.with_user(user).button_approve_accounts_head()

    def test_cannot_approve_own_request(self):
        user = self.env["res.users"].create(
            {
                "name": "Requester approver",
                "login": "pr_requester_approver",
                "group_ids": [
                    (4, self.env.ref("transportation_purchase_request.group_pr_dept_manager").id),
                ],
            }
        )
        pr = self.request_model.create({"requested_by": user.id})
        self.line_model.create({"request_id": pr.id, "product_qty": 1.0})
        pr.button_to_approve()
        with self.assertRaisesRegex(UserError, "own request"):
            pr.with_user(user).button_approve_dept_manager()

    def test_lines_locked_after_approval_request(self):
        pr = self.transportation_purchase_request
        pr.button_to_approve()
        with self.assertRaisesRegex(UserError, "not in draft"):
            self.line.write({"product_qty": 99})
        with self.assertRaisesRegex(UserError, "not in draft"):
            self.line_model.create({"request_id": pr.id, "product_qty": 1.0})
        with self.assertRaisesRegex(UserError, "not in draft"):
            self.line.unlink()

    def _add_approver_groups(self):
        self.env.user.group_ids = [
            (4, self.env.ref(f"transportation_purchase_request.{xmlid}").id)
            for xmlid in (
                "group_pr_dept_manager",
                "group_pr_accounts_head",
                "group_pr_internal_auditor",
                "group_pr_general_manager",
            )
        ]

    def test_approval_order_and_rights(self):
        pr = self.transportation_purchase_request
        pr.button_to_approve()
        user = self.env["res.users"].create(
            {
                "name": "Approver",
                "login": "pr_accounts_approver",
                "group_ids": [
                    (4, self.env.ref("transportation_purchase_request.group_pr_accounts_head").id)
                ],
            }
        )
        # right group but the request is not at this stage yet
        with self.assertRaises(UserError):
            pr.with_user(user).button_approve_accounts_head()
        # request at the first stage can't be approved by a missing group
        with self.assertRaises(UserError):
            pr.with_user(user).button_approve_dept_manager()

    def test_reject_cancels_lines(self):
        pr = self.transportation_purchase_request
        pr.button_to_approve()
        self._add_approver_groups()
        pr.button_rejected()
        self.assertEqual(pr.state, "rejected")
        self.assertTrue(pr.line_ids.cancelled)
        pr.button_draft()
        self.assertFalse(pr.line_ids.cancelled)

    def test_auto_reject(self):
        """A request is auto-rejected when all its lines are cancelled."""
        pr = self.transportation_purchase_request
        self.line_model.create(
            {"request_id": pr.id, "description": "Second", "product_qty": 5.0}
        )
        lines = pr.line_ids
        lines[0].do_cancel()
        self.assertNotEqual(pr.state, "rejected")
        lines[1].do_cancel()
        self.assertEqual(pr.state, "rejected")

    def test_to_approve_allowed(self):
        pr = self.transportation_purchase_request
        self.assertTrue(pr.to_approve_allowed)
        pr.line_ids.write({"product_qty": 0})
        self.assertFalse(pr.to_approve_allowed)
        pr.line_ids.write({"product_qty": 5})
        self.assertTrue(pr.to_approve_allowed)
        pr.line_ids.do_cancel()
        pr.button_draft()
        new_line = self.line_model.create(
            {"request_id": pr.id, "product_qty": 0.0}
        )
        self.assertFalse(pr.to_approve_allowed)
        new_line.write({"product_qty": 1})
        self.assertTrue(pr.to_approve_allowed)

    def test_empty_transportation_purchase_request(self):
        pr = self.transportation_purchase_request
        pr.line_ids.write({"product_qty": 0})
        with self.assertRaises(UserError):
            pr.button_to_approve()
        pr.line_ids.write({"product_qty": 4})
        pr.button_to_approve()
        self.assertEqual(pr.state, "dept_manager")

    def test_line_count(self):
        self.assertEqual(len(self.transportation_purchase_request.line_ids), 1)
        self.line_model.create(
            {"request_id": self.transportation_purchase_request.id, "product_qty": 1.0}
        )
        self.assertEqual(len(self.transportation_purchase_request.line_ids), 2)

    def test_default_name_and_form(self):
        with Form(self.request_model) as f:
            f.requested_by = self.env.user
        self.assertNotEqual(f.record.name, "New")

    def test_copy_transportation_purchase_request(self):
        copy = self.transportation_purchase_request.copy()
        self.assertEqual(copy.state, "draft")
        self.assertNotEqual(copy.name, self.transportation_purchase_request.name)
        self.assertEqual(len(copy.line_ids), len(self.transportation_purchase_request.line_ids))

    def test_price_and_totals(self):
        pr = self.transportation_purchase_request
        self.line.write({"price_unit": 10.0})
        self.assertEqual(self.line.price_subtotal, 50.0)
        self.assertEqual(pr.amount_total, 50.0)
        second = self.line_model.create(
            {"request_id": pr.id, "product_qty": 2.0, "price_unit": 7.5}
        )
        self.assertEqual(pr.amount_total, 65.0)
        second.do_cancel()
        self.assertEqual(pr.amount_total, 50.0)


@tagged("post_install", "-at_install")
class TestPurchaseRequestVendorBill(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.request = cls.env["transportation.purchase.request"].create(
            {"requested_by": SUPERUSER_ID, "vendor_id": cls.partner_a.id}
        )
        line_model = cls.env["transportation.purchase.request.line"]
        cls.line1 = line_model.create(
            {
                "request_id": cls.request.id,
                "description": "Item 1",
                "product_qty": 2.0,
                "price_unit": 10.0,
            }
        )
        cls.line2 = line_model.create(
            {
                "request_id": cls.request.id,
                "description": "Item 2",
                "product_qty": 1.0,
                "price_unit": 5.0,
            }
        )

    def test_bill_requires_approval(self):
        with self.assertRaises(UserError):
            self.request.action_create_vendor_bill()
        self.request.button_to_approve()
        with self.assertRaises(UserError):
            self.request.action_create_vendor_bill()

    def test_create_vendor_bill(self):
        self.request.button_to_approve()
        self.request.state = "approved"
        self.line2.do_cancel()
        action = self.request.action_create_vendor_bill()
        bill = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.partner_id, self.partner_a)
        self.assertEqual(bill.transportation_purchase_request_id, self.request)
        self.assertEqual(bill.invoice_origin, self.request.name)
        self.assertEqual(len(bill.invoice_line_ids), 1)
        self.assertEqual(bill.invoice_line_ids.quantity, 2.0)
        self.assertEqual(bill.invoice_line_ids.price_unit, 10.0)
        self.assertEqual(self.request.bill_count, 1)
        # a second bill cannot be created while one is active
        with self.assertRaises(UserError):
            self.request.action_create_vendor_bill()
        # once cancelled, a new one can be created
        bill.button_cancel()
        self.assertEqual(self.request.bill_count, 0)
