# rotana_weighbridge (Odoo 19)

Receives SmartBridge weighbridge tickets from the agent running on the scale PC, matches them to fleet
vehicles by **plate number**, and shows a dashboard with tickets per day and total net weight.

## How matching works
- The scale operator types the plate number (e.g. `16202`). Odoo vehicles store it inside `license_plate`
  (e.g. `16202  ب ح س ش`). Matching compares the **leading digits** of both (Arabic digits are normalised).
- One vehicle found -> `Fleet vehicle`; if that vehicle has exactly one open trip (`confirmed` / `in_transit`)
  the ticket is linked to it. Several open trips -> `Needs Review`.
- Several vehicles share the digits -> `Ambiguous plate` -> `Needs Review`.
- No vehicle -> `External truck`: the ticket is stored as a weight ticket only. **No vehicle is created.**
- Manual changes to vehicle/trip are kept; matching re-runs only when the plate changes or via the
  "Re-match vehicle & trip" button.

## Weights
SmartBridge stores `net = first - second` (usually negative: empty truck weighed first). Odoo recomputes
`net = |first - second| + |trailer first - trailer second|` (kg). The value reported by SmartBridge is kept in
`Reported Net (kg)` for reconciliation. Dashboard counts **completed** tickets only (second weight present,
not cancelled). Day = local date of the latest weighing time (`rotana_weighbridge.timezone`).

## Setup (Odoo.sh)
1. Add the folder to the repo, push to a dev/staging branch, install **Rotana Weighbridge**.
2. Settings > Technical > System Parameters:
   - `rotana_weighbridge.api_token` = long random secret (**required**, endpoint is closed without it)
   - `rotana_weighbridge.company_id` = company id for new tickets (optional, default: main company)
   - `rotana_weighbridge.timezone` = `Africa/Khartoum` (created by default)
3. Test:
```
curl -X POST "https://<your-odoo-domain>/rotana/weighbridge/sync" \
  -H "X-Weighbridge-Token: <token>" -H "Content-Type: application/json" \
  -d '{"station":"main","tickets":[{"ticket_number":1,"plate":"16202","first_weight":22000,
       "first_weight_datetime":"2026-11-09 08:00:00","second_weight":60000,
       "second_weight_datetime":"2026-11-09 08:20:00"}]}'
```
(add `?db=<database>` if several databases are served on the domain).

## Endpoint contract
`POST /rotana/weighbridge/ping` -> `{"ok": true}` (checks the token).

`POST /rotana/weighbridge/sync`, header `X-Weighbridge-Token`, JSON body (max 500 items per call):

| key | meaning |
|---|---|
| `station` | weighbridge DB code (default `main`); ticket key = `station:ticket_number` |
| `tickets[]` | upserted by key; unchanged tickets are ignored |
| `deleted[]` | ticket numbers removed at the source -> marked **Cancelled** (never deleted) |

Ticket fields: `ticket_number` (required), `plate`, `first_weight`, `first_weight_datetime`, `second_weight`,
`second_weight_datetime`, `has_trailer`, `trailer_first_weight`, `trailer_second_weight`, `total_net_weight`,
`unit`, `driver`, `customer`, `destination`, `notes`. Weights in kg; datetimes **UTC** `YYYY-MM-DD HH:MM:SS`
(the agent converts from the PC's local time).

Response: `{"created":n,"updated":n,"unchanged":n,"cancelled":n,"errors":[{"ticket_number":..,"error":..}]}`.
One failing ticket never blocks the rest.

## Notes / limits
- Weighbridge ticket numbers can restart after an archive: change `station` (e.g. `main-2`) if that happens.
- Access: internal users read/write (to link a trip manually); only admins create/delete. Tighten with your
  own groups if needed.
- Not done yet (by design): updating `rotana.transport.trip.transported_weight` from the ticket, customer matching.
