# Transportation Purchase Request

Rotana module for transportation purchase requests with a four-step approval chain
(Department Manager, Head of Accounts, Internal Auditor, General Manager) and vendor bill creation.

Derived from the OCA `purchase_request` module (ForgeFlow, LGPL-3). The original copyright
notices are kept in the source file headers.

## Rules
- A person cannot approve their own request, nor more than one stage of the same request.
- Lines can only be changed while the request is a draft (enforced on the server).
- Only a Transportation Purchase Request Manager can reset a request to draft.
- The company is required and each company has its own numbering.
- The vendor bill needs a vendor and a purchase journal with a default account.
