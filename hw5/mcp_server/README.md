# Campus Customs MCP server

## What it's for

This MCP server is the shared toolbox for the Campus Customs multi-agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Instead of each agent querying the database its own way, every agent calls these tools, so they all see the same data and the same rules. Tools return only values from the database; if something isn't there, the tool says so rather than guessing.

## Database

It connects to the **working copy**, `data/campus_customs_new.db`, and the tools that change data write only there. The original, `data/campus_customs.db`, is never touched by the server; copy it over the working copy to reset the shop before a clean run:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Due dates are measured against the shop's "today", `desk.date_today` (2026-08-31).

## Tools (15)

### Read tools
| Tool | Reads | What it returns |
|---|---|---|
| `get_desk()` | `desk` | The shop's today (`date_today`) and desk notes |
| `list_tickets(status)` | `tickets` | Each ticket's id, type, requester, subject, and status (filter by status, or empty for all) |
| `get_ticket(ticket_id)` | `tickets`, `desk` | One ticket in full: product (sku/size/qty), linked lease or invoice, status, notes |
| `check_stock(sku, size)` | `inventory`, `pricing` | Units on hand by size (leave `size` empty for all sizes), location, unit cost, and list price |
| `check_margin(sku, qty, unit_price, discount_pct)` | `pricing` | Price, margin per unit and in total, discount off list, and `below_cost` |
| `list_vendors()` | `vendors`, `invoices`, `desk` | Every vendor's specialty, lead time, open invoices, and `will_ship` |
| `check_vendor_invoices(vendor_id)` | `vendors`, `invoices`, `desk` | The vendor's invoices with days until due or overdue, the open amount, `will_ship` (false while any invoice is open, per the shop rule), and the earliest delivery if unblocked |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | One invoice: vendor, amount, due date, status, days overdue |
| `get_lease(lease_id)` | `leases`, `desk` | The space, landlord, monthly rent, next due date, and days until it is due |
| `get_cash_balance(account)` | `cash_accounts`, `payment_requests` | The balance, the total waiting for approval, and the balance after it |
| `list_payments(ticket_id)` | `payment_requests`, `payments` | Payments prepared (with status) and payments made |

### Agent write tools (no money moves)
| Tool | Writes (reads) | What it does |
|---|---|---|
| `prepare_payment(kind, ref_id, reason, ticket_id, sku, size, qty)` | `payment_requests` (`invoices`, `leases`, `vendors`, `pricing`, `cash_accounts`) | Adds a **pending** payment for a human to approve: `invoice` (ref_id = invoice id), `rent` (lease id), or `purchase_order` (vendor id + sku/size/qty). The amount and payee come from the database. Refuses if the amount is more than the cash, the bill is already paid, or it's a duplicate |
| `update_ticket(ticket_id, status, note)` | `tickets` (`payment_requests`) | Sets the status (`open`, `in_progress`, `waiting_on_approval`, `needs_human`, `resolved`) and appends a dated, signed note; won't mark a ticket resolved while a payment for it is pending |

### Human-only tools (never given to an agent)
| Tool | Writes | What it does |
|---|---|---|
| `approve_payment(request_id, approved_by)` | `payment_requests`, `cash_accounts`, `payments`, `invoices` / `leases`, `tickets` | **The only tool that moves cash.** Refuses if the balance would go negative, if a purchase order's vendor still has an open invoice, or if `approved_by` is an agent. On success: lowers checking, records the payment with the approver, marks the invoice paid or moves the lease's next due date a month, and resolves the ticket if it was only waiting on approval |
| `reject_payment(request_id, rejected_by, reason)` | `payment_requests`, `tickets` | Turns a request down (no money moves) and sets the ticket to `needs_human` |

`payment_requests` is a table the server adds to the working copy the first time it's needed; resetting the database removes it. The backend's agent loop (`backend/agents/team.py`) gives each agent only the tools its job needs and blocks the human-only tools.

## Running it

From the `HW5` folder, with the project environment set up (`pip install -r requirements.txt`):

```bash
.venv/bin/python mcp_server/server.py
```

It runs over stdio, so a vibe coder or the backend starts it as a subprocess and talks to it directly.
