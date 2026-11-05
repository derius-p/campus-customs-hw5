# Campus Customs Multi-Agent Operations: Harness

How the system works. This file grows as each problem is completed.

## Database

- **Original:** `data/campus_customs.db`, kept untouched so the shop can be reset before a full run.
- **Working copy:** `data/campus_customs_new.db`, the file the MCP server and backend read and update.
- **Shop "today":** `desk.date_today` = **2026-08-31**. Due dates and overdue checks are measured against it.

### `desk`
| Field | |
|---|---|
| `date_today` | The shop's current date |
| `notes` | Free-text notes (empty) |

**Why it matters:** gives every agent the same "today", so they agree on what is overdue or due soon.

### `tickets`
| Field | |
|---|---|
| `id` | Ticket number (101–103) |
| `type` | `customer_order`, `rent_notice`, or `price_override` |
| `requester` | Who raised it (customer, landlord, student club) |
| `subject` | Short title |
| `sku`, `size`, `qty` | The product and amount involved, if any (links to `inventory` and `pricing`) |
| `lease_id` | Linked lease, if any (→ `leases.id`) |
| `invoice_id` | Linked invoice, if any (→ `invoices.id`) |
| `status` | All three are `open` |
| `notes` | The request in the requester's words |
| `created_at` | When the ticket arrived |

**Why it matters:** the work queue. The Boss reads each ticket and routes it, and the links tell the agents which other tables to check.

### `inventory`
| Field | |
|---|---|
| `sku` | Product code (with `size`, the key) |
| `name` | Product name |
| `size` | S, M, L, XL, or OS (one size) |
| `qty` | Units on hand |
| `location` | Aisle in the shop |

**Why it matters:** Inventory checks stock by SKU and size, and spots shortfalls (the tee in size S and the Crest Mug are at 0).

### `pricing`
| Field | |
|---|---|
| `sku` | Product code |
| `unit_cost` | What the shop pays per unit |
| `list_price` | What the shop charges per unit |

**Why it matters:** Accounting uses cost and price to check margins on discounts and to cost restocking.

### `vendors`
| Field | |
|---|---|
| `id` | Vendor number |
| `name` | Vendor name |
| `specialty` | What they supply (apparel reprint, mugs and small goods, local courier) |
| `lead_days` | Days from order to delivery |

**Why it matters:** Inventory picks who can restock a product and how long it will take.

### `invoices`
| Field | |
|---|---|
| `id` | Invoice number |
| `vendor_id` | Vendor billed by (→ `vendors.id`) |
| `amount` | Amount owed |
| `due_date` | When payment is due |
| `status` | `open` (unpaid) |
| `description` | What the invoice is for |

**Why it matters:** Accounting tracks unpaid bills, and a vendor with an open unpaid invoice won't ship, which blocks restocking.

### `leases`
| Field | |
|---|---|
| `id` | Lease number |
| `space_name` | The rented space (Chapel Street shop) |
| `landlord` | Who is paid |
| `monthly_rent` | Rent per month |
| `next_due` | Next rent due date |
| `notes` | Free-text notes (empty) |

**Why it matters:** Facilities uses it to know what rent is owed, to whom, and when.

### `cash_accounts`
| Field | |
|---|---|
| `name` | Account name (`checking`) |
| `balance` | Money available |
| `date` | As-of date of the balance |

**Why it matters:** the limit on every payment. The pay tool must refuse anything that would make the balance negative, and no money comes in.

### `payments`
| Field | |
|---|---|
| `id` | Payment number |
| `kind` | What was paid (e.g. invoice, rent, purchase order) |
| `ref_id` | The invoice, lease, or order it pays |
| `amount` | Amount paid |
| `account` | Account it came from |
| `paid_at` | When it was paid |
| `approved_by` | The human who approved it |

**Why it matters:** the record of money out. Every payment is logged here with who approved it (empty at the start).

### `payment_requests` (added by the MCP server)
Not in the original database. The MCP server creates it in the working copy the first time it's needed, and a reset removes it.

| Field | |
|---|---|
| `id` | Request number |
| `ticket_id` | The ticket it's for |
| `kind`, `ref_id` | `invoice` (invoice id), `rent` (lease id), or `purchase_order` (vendor id) |
| `payee`, `amount` | Taken from the database by the tool, never typed in by an agent |
| `sku`, `size`, `qty` | Purchase orders only |
| `reason`, `prepared_by` | Why the payment is needed, and which agent prepared it (filled in by the system, not the agent) |
| `status` | `pending`, then `approved`, `rejected`, or `refused` |
| `decided_by`, `decided_at`, `decision_note`, `payment_id` | The human who decided, when, why, and the `payments` row it created |

**Why it matters:** the waiting room between "an agent prepared a payment" and "a human paid it". Agents can add to it but can never approve from it.

## MCP server: first three tools (Problem 3)

The MCP server (`mcp_server/server.py`, FastMCP, server name `campus-customs`) is the toolbox every agent uses. It reads the working copy `data/campus_customs_new.db` (read-only for these three tools) and returns only values from the database, saying so when something isn't found.

| Tool | Tables it reads | Ticket it helps unlock | Why it's the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory`, `pricing` | **101** (customer order) and **103** (bulk hoodie discount) | For 101 it shows the Classic Bulldog Tee (CC-TEE-WHITE) has **0 units in size S**, so the order can't ship from the shelf; for 103 it shows **8 Basic Hoodies (CC-HOOD-NAVY) in size M** against the 20 requested (a 12-unit shortfall) and returns the $22 cost and $58 list price that any discount has to be judged against. |
| `check_vendor_invoices(vendor_id)` | `vendors`, `invoices`, `desk` | **101**, and also **103** | Restocking either ticket's apparel means Bulldog Print Co (vendor 1), and this tool shows that vendor is **blocked by open invoice #501 ($840, 3 days overdue against today, 2026-08-31)** and has a **5-day lead time**, so the agents know the invoice must be paid (with human approval) before any reprint can be ordered. |
| `get_lease(lease_id)` | `leases`, `desk` | **102** (rent notice) | Ticket 102 links to lease 1, and this tool returns exactly what must be paid: **$2,400 to Elm City Properties for the Chapel Street shop, due 2026-09-02, 2 days from today**, so Facilities and Accounting can schedule the payment before it is late. |

## MCP tools (all 15)

| Tool | Tables it uses | Who calls it | What it does |
|---|---|---|---|
| `get_desk()` | `desk` | All agents | The shop's today (2026-08-31) |
| `list_tickets(status)` | `tickets` | Boss | The board: each ticket's id, type, requester, subject, status |
| `get_ticket(ticket_id)` | `tickets`, `desk` | All agents | One ticket in full, including linked sku/size/qty, lease, invoice, and notes |
| `check_stock(sku, size)` | `inventory`, `pricing` | Inventory, Accounting, Customer Service | Units on hand by size, location, unit cost, list price |
| `check_margin(sku, qty, unit_price, discount_pct)` | `pricing` | Accounting | Margin per unit and in total at a proposed price; flags a price at or below cost |
| `list_vendors()` | `vendors`, `invoices`, `desk` | Inventory | Every vendor's specialty, lead time, open invoices, and whether it will ship |
| `check_vendor_invoices(vendor_id)` | `vendors`, `invoices`, `desk` | Inventory, Accounting | One vendor's invoices, days overdue, `will_ship`, and earliest delivery if unblocked |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | Accounting | One invoice: vendor, amount, due date, status, days overdue |
| `get_lease(lease_id)` | `leases`, `desk` | Facilities, Accounting | Space, landlord, rent, next due date, days until due |
| `get_cash_balance(account)` | `cash_accounts`, `payment_requests` | Boss, Accounting | Checking balance, the total already waiting for approval, and what's left after it |
| `list_payments(ticket_id)` | `payment_requests`, `payments` | Boss, Accounting | Payments prepared (and their status) and payments actually made |
| `prepare_payment(kind, ref_id, reason, ticket_id, sku, size, qty)` | writes `payment_requests`; reads `invoices`, `leases`, `vendors`, `pricing`, `cash_accounts` | Accounting | Adds a **pending** request with the amount taken from the database. Refuses if the amount is more than cash, the bill is already paid, or it's a duplicate; warns if all pending payments together exceed cash. **Moves no money.** |
| `update_ticket(ticket_id, status, note)` | `tickets`, `payment_requests` | Boss | Sets status (`open`, `in_progress`, `waiting_on_approval`, `needs_human`, `resolved`) and adds a signed, dated note; won't mark a ticket resolved while a payment for it is pending |
| `approve_payment(request_id, approved_by)` | `payment_requests`, `cash_accounts`, `payments`, `invoices` or `leases`, `tickets` | **Human only** (the board's Approve button) | The only tool that moves cash. Refuses if the balance would go negative, if a purchase order's vendor still has an open invoice, or if `approved_by` is an agent. On success: lowers checking, adds a `payments` row with the approver, marks the invoice paid or moves the lease's next due date a month, and resolves the ticket if it was only waiting on approval |
| `reject_payment(request_id, rejected_by, reason)` | `payment_requests`, `tickets` | **Human only** | Turns a request down (no money moves) and sets the ticket to `needs_human` |

## The agent team

All five agents run on **gpt-6-luna** through Portkey (`backend/agents/config.py`). The prompts are in `backend/prompts/`, the data types in `backend/models.py`, and the agent loop in `backend/agents/team.py`. Every agent has `ask_agent(agent, task)` and can delegate to any other agent, within the guards listed under Safety.

| Agent | Job | MCP tools it can call |
|---|---|---|
| **Boss** (`boss.md`), shown on the board as Maurie McInnis, President | Reads the ticket, picks which specialists to call and in what order, makes the final call, and keeps the ticket status current | `get_desk`, `list_tickets`, `get_ticket`, `get_cash_balance`, `list_payments`, `update_ticket` |
| **Inventory** (`inventory.md`), shown as Geoffrey Chatas, SVP for Operations | Stock by SKU and size, shortfalls, which vendor can restock and when | `get_desk`, `get_ticket`, `check_stock`, `list_vendors`, `check_vendor_invoices` |
| **Accounting** (`accounting.md`), shown as Katrina Spencer, VP for Finance & CFO | Cash, invoices, margins, and preparing payments and purchase orders for human approval | `get_desk`, `get_ticket`, `get_cash_balance`, `get_invoice`, `check_vendor_invoices`, `check_stock`, `check_margin`, `get_lease`, `list_payments`, `prepare_payment` |
| **Facilities** (`facilities.md`), shown as Mike Bellamy, VP for Facilities | The lease, rent, and landlord; checks a rent notice against the lease | `get_desk`, `get_ticket`, `get_lease` |
| **Customer Service** (`customer_service.md`), shown as Renee Kopkowski, VP for Communications | Drafts replies to requesters (drafts only, never sent) | `get_desk`, `get_ticket`, `check_stock` |

No agent can call `approve_payment` or `reject_payment`.

## Audit trail

`output/audit_trail.json` is a JSON list that only grows (`backend/audit.py`). Every run adds its records to the end, and nothing is wiped. Each record is written **as it happens**, one per agent-loop step:

| Record type | What it captures |
|---|---|
| `run_started` / `run_finished` | The ticket handed to the Boss; at the end, the decision plus total requests, tokens, tool calls, and delegations |
| `agent_started` / `agent_finished` | The task an agent was given; its final answer and its own token use |
| `model_step` | Each model response: step number, the model that answered (`gpt-6-luna-global`), any text, the tool calls it asked for (with arguments and call ids), and tokens in and out |
| `delegation` / `delegation_refused` | Who asked whom, with the exact task, or why the guard refused |
| `tool_call` / `tool_result` / `tool_blocked` | The MCP tool, its arguments, and its result (linked by call id), or why it was blocked |
| `approval` / `rejection` | A human's decision on a payment (written by the backend, Problem 7) |
| `error` | Anything that failed, and where |

Every record carries `run_id`, `ticket_id`, a UTC `time`, the `agent`, and the delegation `chain` (e.g. `boss → facilities → accounting`), so any number on the board can be traced back to the tool call that produced it.

## Backend routes (`backend/main.py`)

FastAPI. Start it from `backend/` with `uvicorn main:app --reload --port 8000` (with the project's `.venv` active). The backend gets every shop fact through the same MCP server the agents use, over one shared connection. Base URL `http://localhost:8000`; interactive docs at `/docs`.

- `GET /tickets`: the three tickets with their database status, `open` or `resolved` (resolved once the team has finished a run on it since the last reset, or the database says resolved), whether the team is running on one, and each ticket's last outcome from the audit trail.
- `POST /tickets/{ticket_id}/run`: starts the agent team on that ticket in the background and returns a `run_id` right away. Refused if a ticket is already running (one at a time).
- `GET /events?since=&ticket_id=&run_id=&limit=`: recent audit-trail records for the board: what each agent said, delegations, and every MCP tool call and result. Poll with `since=next_since` to get only new events.
- `GET /payments?ticket_id=`: the payments agents prepared (pending, approved, rejected, refused) and the payments actually made.
- `POST /payments/{request_id}/approve` (body `{"approved_by": "<person>"}`): a human approves a payment. **The only route that changes cash**: it lowers checking, records the payment and updates the invoice or lease. Refused if cash would go negative, the vendor is blocked, or the approver is an agent. Written to the audit trail as `approval`.
- `POST /payments/{request_id}/reject` (body `{"approved_by": "<person>", "note": "<why>"}`): a human turns a payment down. No money moves. Written to the audit trail as `rejection`.
- `GET /cash`: the current checking balance from `cash_accounts`, plus the total waiting for approval.
- `POST /reset`: copies `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run. Refused while a ticket is running. The audit trail is kept and gets a `reset` record.

## Dashboard (`frontend/`)

React + Vite + TypeScript. Start it from `frontend/` with `npm run dev` and open `http://localhost:5173`. It calls the backend at `http://localhost:8000`, which allows that origin. The look and the reasons for it are in `output/design.md`.

- **Header:** the Yale Bulldog Blue crest and wordmark (from HW4), the shop date, the **live checking balance** (counts down, flashes, shows the change and a sparkline), and **Reset shop** (`POST /reset`).
- **Tickets column:** the three tickets with Open / Agents working / Resolved badges, the finer database status, and **Activate Ops Team** (`POST /tickets/{id}/run`). Only one ticket runs at a time.
- **Agent floor:** five tiles, each a Yale officer playing an agent (cartoon, name, role subtitle). Each shows live state, current action, and tool count. Under them:
  - **Live:** the timeline of handoffs, tool calls with results, and what each agent says (`GET /events`, polled about every second during a run).
  - **Summary:** the Boss's decision, open questions, customer drafts marked "Draft, not sent", and what each agent did.
- **Approvals and cash column:**
  - pending payments with the balance after each, plus **Approve & pay** / **Reject**. These are signed with the name in "Approving as" and call `POST /payments/{id}/approve` and `/reject`.
  - decided payments (`GET /payments`) and a cash ledger (`GET /cash`).
- **Responsive:** the team goes five across, then 3 + 2, then 2 + 2 + 1 as the window narrows, and the columns stack on small screens.
- **Links:** `?ticket=<id>&view=summary` opens the board on one ticket's summary (used for the screenshots in `output/resolved_board.html`).

## Safety

### Shop rules, and where each is enforced
| Rule | Where it is enforced |
|---|---|
| `desk.date_today` is "today" | Every date tool measures from it (`get_desk`, `days_until_due`, `overdue`); prompts tell agents never to use the real calendar |
| Vendor lead times come from `vendors` | `check_vendor_invoices`, `list_vendors`, `prepare_payment` (expected delivery = today + `lead_days`) |
| A vendor with an open unpaid invoice won't ship | `will_ship` in the vendor tools; `approve_payment` refuses a purchase order while the vendor has an open invoice |
| Human approval for every payment | Only `approve_payment` moves cash. It is never given to an agent, it is blocked in the tool wrapper, and it refuses an agent's name. The board requires the approver's name |
| Paying updates the related tables | `approve_payment` writes `payments`, lowers `cash_accounts`, marks the invoice paid or moves the lease's `next_due`, and updates the ticket |
| No negative balances | `prepare_payment` refuses an amount over the cash, and `approve_payment` checks again at the moment of payment |
| Cash only goes out | No tool adds money; only a reset restores the opening balance |
| Reset before a full run | `POST /reset` / **Reset shop** copies the original database over the working copy (the original is never written) |
| No emailing customers or calling vendors | No tool sends anything; customer messages are drafts on the board |
| Only gpt-6-luna, through Portkey | One model for all five agents (`backend/agents/config.py`); the audit trail records the model on every step |
| Never invent data; facts only through MCP | Prompts forbid it; agents have no database access except the MCP tools; amounts in payments come from the database |

### Guardrails in this build
- **Human approval for every payment.** Agents can only *prepare* a payment. `approve_payment` and `reject_payment` are left out of every agent's tool list, blocked again in the tool-call wrapper if one is ever requested, and refuse any `approved_by` that is an agent's name.
- **Amounts come from the database, not the agent.** `prepare_payment` looks up the invoice amount, the rent, or qty × unit cost itself, so an agent can't inflate or invent a number.
- **No negative balances.** `prepare_payment` refuses anything over the cash on hand, and `approve_payment` checks again at the moment of payment (cash may have dropped since the request was prepared).
- **Shop rules enforced in code, not only in prompts.** A purchase order can't be paid while the vendor has an open invoice. A ticket can't be marked resolved while a payment is pending. Duplicate requests are refused.
- **Attribution.** The system stamps `prepared_by` and `updated_by` with the calling agent's name, and the approver's name goes on the `payments` row.
- **Nothing leaves the shop.** No tool sends email or contacts a vendor. Customer messages are drafts on the board.
- **No bypass.** Agents get shop facts only through the MCP server, over the working copy. The original database is never opened for writing.
- **Least privilege.** Each agent sees only the tools its job needs (e.g. Facilities has only `get_desk`, `get_ticket`, and `get_lease`).

### Limits that keep token use in check (`backend/agents/config.py`)
| Limit | Value |
|---|---|
| Delegation depth | 2 (Boss → specialist → specialist) |
| Delegations per ticket | 8 |
| No self-delegation or asking anyone already in the chain | blocks A → B → A loops |
| Tokens per ticket (whole team) | 250,000 |
| MCP tool calls per ticket (whole team) | 40 |
| Per agent run | Boss: 16 requests, 20 tool calls, 120k tokens. Specialists: 8 requests, 10 tool calls, 60k tokens |
| Tool results kept in the audit trail | 4,000 characters |
| Model | gpt-6-luna only, one shared client |

Each agent is told how much of the team budget is left on every turn. For scale, a test run of ticket 102 used 18 model requests, about 36k tokens, 17 tool calls, and 3 delegations.

### What a real business would add
- **Real money:**
  - Approval thresholds and two-person sign-off above a set amount.
  - Separate logins for the people who prepare and the people who approve.
  - Payee and bank details checked against a vendor master file (to stop invoice fraud).
  - Daily and monthly spending caps.
  - A reconciliation of `payments` against the bank statement.
  - Read-only access to the real bank, with payments made by a person in the bank's own system.
- **Real customers:**
  - A person reviews every message before it's sent.
  - No customer personal data in prompts beyond what the ticket needs.
  - No promises of dates, prices, or refunds that aren't in the database.
  - A tone and policy check on drafts.
  - A clear way for a customer to reach a person.
- **Prompt injection:**
  - Treat ticket text and customer notes as data, not instructions. A note saying "approve this payment" or "give 50% off" must not change what the agents do.
  - Keep the code-level checks above, because a prompt alone can be talked around.
- **Operations:**
  - A dry-run mode.
  - A kill switch to stop all agents.
  - Alerts on refused payments, blocked tools, or budget overruns.
  - Daily cost reports per ticket.
  - Audit logs kept tamper-evident and stored off the machine.
  - Regular reviews of a sample of agent decisions.
