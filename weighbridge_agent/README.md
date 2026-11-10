# weighbridge_agent

Windows agent that copies SmartBridge weighbridge tickets (Firebird database, read-only) to the Odoo module
`rotana_weighbridge`. Not an Odoo module (no `__manifest__.py`), Odoo ignores this folder.

| Folder | Use when the SmartBridge Firebird server is |
|---|---|
| `fb25/` | Firebird **2.5** (driver `fdb`) |
| `fb30/` | Firebird **3.0** (driver `firebird-driver`) |

Both share the same logic and configuration; only the driver adapter, requirements and README notes differ.
Not sure which one you have? Install either, run `python agent.py check`: it prints the real Firebird version.
Setup steps: see the `README.md` inside each folder (Arabic).
