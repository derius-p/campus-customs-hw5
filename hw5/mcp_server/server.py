"""Campus Customs MCP server: the only way the agents (and the backend) get or change shop facts.

Talks to the working copy of the shop database, data/campus_customs_new.db (never the original
data/campus_customs.db, which is kept for resets). Every value returned comes from the database;
when something isn't there, the tool says so instead of guessing.

Read tools
  get_desk()                          desk
  list_tickets(status)                tickets
  get_ticket(ticket_id)               tickets (+ desk for today)
  check_stock(sku, size)              inventory + pricing
  check_margin(sku, qty, unit_price)  pricing
  list_vendors()                      vendors + invoices
  check_vendor_invoices(vendor_id)    vendors + invoices
  get_invoice(invoice_id)             invoices + vendors
  get_lease(lease_id)                 leases
  get_cash_balance(account)           cash_accounts + payment_requests
  list_payments(ticket_id)            payment_requests + payments

Agent write tools (no money moves)
  prepare_payment(...)                payment_requests (reads invoices / leases / vendors / pricing / cash_accounts)
  update_ticket(ticket_id, status, note)   tickets

Human-only tools (never given to an agent; the backend's approve button calls them)
  approve_payment(request_id, approved_by)   payment_requests, cash_accounts, payments, invoices / leases, tickets
  reject_payment(request_id, rejected_by, reason)   payment_requests

Run (stdio, for a vibe coder or the backend):  python server.py
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "needs_human", "resolved")

mcp = FastMCP("campus-customs")

# Payments an agent has prepared wait here until a human approves or rejects them. The table is
# created in the working copy only (a reset copies the original database back, without it).
_REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,            -- invoice | rent | purchase_order
    ref_id INTEGER NOT NULL,       -- invoice id | lease id | vendor id
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    sku TEXT, size TEXT, qty INTEGER,   -- purchase orders only
    reason TEXT NOT NULL,
    prepared_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | refused
    created_at TEXT NOT NULL,
    decided_by TEXT, decided_at TEXT, decision_note TEXT,
    payment_id INTEGER
)
"""


# ---------------------------------------------------------------- helpers

def _check_db() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}. Copy data/campus_customs.db to it first.")


def _ensure_tables() -> None:
    _check_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(_REQUESTS_SCHEMA)


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query on the working database and return rows as dicts."""
    _check_db()
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _connect_rw() -> sqlite3.Connection:
    _ensure_tables()
    conn = sqlite3.connect(DB_PATH, isolation_level="IMMEDIATE")  # one writer at a time
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    """The shop's 'today' (desk.date_today), which all due dates are measured against."""
    rows = _query("SELECT date_today FROM desk LIMIT 1")
    if not rows:
        raise RuntimeError("desk.date_today is missing from the database")
    return rows[0]["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _balance(account: str = "checking") -> float | None:
    rows = _query("SELECT balance FROM cash_accounts WHERE name = ?", (account,))
    return rows[0]["balance"] if rows else None


def _has_requests_table() -> bool:
    """Reads never create the table, so a freshly reset database stays identical to the original."""
    return bool(_query("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'payment_requests'"))


def _pending_total() -> float:
    if not _has_requests_table():
        return 0.0
    rows = _query("SELECT COALESCE(SUM(amount), 0) AS total FROM payment_requests WHERE status = 'pending'")
    return round(rows[0]["total"], 2)


# ---------------------------------------------------------------- read tools

@mcp.tool
def get_desk() -> dict:
    """The shop's desk: today's date for the shop (desk.date_today) and any desk notes.

    Every due date, overdue check, and delivery estimate is measured from this date, not the real calendar.
    """
    rows = _query("SELECT date_today, notes FROM desk LIMIT 1")
    return rows[0] if rows else {"found": False, "note": "The desk table is empty."}


@mcp.tool
def list_tickets(status: str = "") -> dict:
    """List the tickets on the board (id, type, requester, subject, status).

    Args:
        status: Only tickets with this status (open, in_progress, waiting_on_approval, needs_human,
            resolved). Leave empty for all tickets.
    """
    sql = "SELECT id, type, requester, subject, status FROM tickets"
    params: tuple = ()
    if status.strip():
        sql += " WHERE status = ?"
        params = (status.strip(),)
    rows = _query(sql + " ORDER BY id", params)
    return {"count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket in full: type, requester, subject, product (sku/size/qty), linked lease or
    invoice, status, and notes. Start every ticket here.

    Args:
        ticket_id: Ticket number, e.g. 101.
    """
    rows = _query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if not rows:
        ids = [r["id"] for r in _query("SELECT id FROM tickets ORDER BY id")]
        return {"ticket_id": ticket_id, "found": False, "note": f"No ticket {ticket_id}; ticket ids: {ids}."}
    return {**rows[0], "found": True, "today": _today()}


@mcp.tool
def check_stock(sku: str, size: str = "") -> dict:
    """Check how many units of a product are on hand, by SKU and size, with its cost and price.

    Use for customer orders and bulk requests: is there enough on the shelf, and what does each
    unit cost the shop and sell for?

    Args:
        sku: Product code, e.g. "CC-TEE-WHITE".
        size: Size, e.g. "S", "M", "L", "XL", or "OS" (one size). Leave empty to list every size.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    sql = "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?"
    params: tuple = (sku,)
    if size:
        sql += " AND size = ?"
        params += (size,)
    rows = _query(sql + " ORDER BY size", params)
    price = _query("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not rows:
        sizes = [r["size"] for r in _query("SELECT size FROM inventory WHERE sku = ?", (sku,))]
        note = (f"No size {size} for {sku}; sizes stocked: {', '.join(sizes)}." if sizes
                else f"No product with SKU {sku} in inventory.")
        return {"sku": sku, "size": size or None, "found": False, "note": note}
    return {
        "sku": sku,
        "name": rows[0]["name"],
        "found": True,
        "stock": [{"size": r["size"], "qty": r["qty"], "location": r["location"], "in_stock": r["qty"] > 0}
                  for r in rows],
        "total_qty": sum(r["qty"] for r in rows),
        "unit_cost": price[0]["unit_cost"] if price else None,
        "list_price": price[0]["list_price"] if price else None,
    }


@mcp.tool
def check_margin(sku: str, qty: int, unit_price: float = 0, discount_pct: float = 0) -> dict:
    """Work out the margin on a sale at a proposed price, from the pricing table.

    Give either unit_price (the price per unit offered) or discount_pct (percent off list price).
    With neither, it uses the list price. Flags any price at or below the shop's unit cost.

    Args:
        sku: Product code, e.g. "CC-HOOD-NAVY".
        qty: Number of units in the deal.
        unit_price: Proposed price per unit (optional).
        discount_pct: Proposed discount off list price, e.g. 15 for 15% (optional).
    """
    sku = sku.strip().upper()
    rows = _query("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not rows:
        return {"sku": sku, "found": False, "note": f"No pricing for SKU {sku}."}
    cost, listp = rows[0]["unit_cost"], rows[0]["list_price"]
    if unit_price > 0:
        price = unit_price
    elif discount_pct > 0:
        price = round(listp * (1 - discount_pct / 100), 2)
    else:
        price = listp
    margin = round(price - cost, 2)
    return {
        "sku": sku, "found": True, "qty": qty, "unit_cost": cost, "list_price": listp,
        "unit_price": price, "discount_pct": round((1 - price / listp) * 100, 2),
        "margin_per_unit": margin, "margin_pct": round(margin / price * 100, 2) if price else None,
        "revenue": round(price * qty, 2), "total_cost": round(cost * qty, 2), "total_margin": round(margin * qty, 2),
        "below_cost": price <= cost,
        "list_margin_total": round((listp - cost) * qty, 2),
    }


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead time, open invoice total, and whether it will ship.

    Use to find which vendor can restock a product (match the specialty) before checking its invoices.
    """
    vendors = _query("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
    for v in vendors:
        owed = _query("SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM invoices "
                      "WHERE vendor_id = ? AND status = 'open'", (v["id"],))[0]
        v["open_invoices"], v["open_amount"] = owed["n"], round(owed["total"], 2)
        v["will_ship"] = owed["n"] == 0
    return {"today": _today(), "vendors": vendors}


@mcp.tool
def check_vendor_invoices(vendor_id: int) -> dict:
    """Look up a vendor (specialty, lead time) and its invoices, and whether it will ship.

    Shop rule: a vendor will not ship new product while it has an open unpaid invoice. Use this
    before planning any restock, to see if the vendor is blocked, what is owed, and how overdue
    it is relative to the shop's today (desk.date_today).

    Args:
        vendor_id: Vendor number, e.g. 1 (Bulldog Print Co).
    """
    vendor = _query("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if not vendor:
        ids = [r["id"] for r in _query("SELECT id FROM vendors ORDER BY id")]
        return {"vendor_id": vendor_id, "found": False, "note": f"No vendor {vendor_id}; vendor ids: {ids}."}
    today = _today()
    invoices = _query(
        "SELECT id, amount, due_date, status, description FROM invoices WHERE vendor_id = ? ORDER BY due_date",
        (vendor_id,),
    )
    for inv in invoices:
        days = _days_between(today, inv["due_date"])
        inv["days_until_due"] = days
        inv["overdue"] = inv["status"] == "open" and days < 0
    open_invoices = [inv for inv in invoices if inv["status"] == "open"]
    return {
        **vendor[0],
        "found": True,
        "today": today,
        "invoices": invoices,
        "open_amount": round(sum(inv["amount"] for inv in open_invoices), 2),
        "will_ship": not open_invoices,
        "earliest_delivery_if_unblocked": (date.fromisoformat(today) + timedelta(days=vendor[0]["lead_days"])).isoformat(),
        "note": (f"Blocked: {len(open_invoices)} open unpaid invoice(s); the vendor won't ship until they are paid."
                 if open_invoices else "No open invoices; the vendor will ship."),
    }


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Look up one invoice: vendor, amount, due date, status, and how overdue it is.

    Args:
        invoice_id: Invoice number, e.g. 501.
    """
    rows = _query("SELECT i.*, v.name AS vendor_name, v.lead_days FROM invoices i "
                  "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (invoice_id,))
    if not rows:
        ids = [r["id"] for r in _query("SELECT id FROM invoices ORDER BY id")]
        return {"invoice_id": invoice_id, "found": False, "note": f"No invoice {invoice_id}; invoice ids: {ids}."}
    today = _today()
    days = _days_between(today, rows[0]["due_date"])
    return {**rows[0], "found": True, "today": today, "days_until_due": days,
            "overdue": rows[0]["status"] == "open" and days < 0}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a lease: the space, landlord, monthly rent, and when rent is next due.

    Use for rent notices: how much is owed, to whom, and how many days until it is due
    relative to the shop's today (desk.date_today).

    Args:
        lease_id: Lease number, e.g. 1 (Chapel Street shop).
    """
    lease = _query("SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
                   (lease_id,))
    if not lease:
        ids = [r["id"] for r in _query("SELECT id FROM leases ORDER BY id")]
        return {"lease_id": lease_id, "found": False, "note": f"No lease {lease_id}; lease ids: {ids}."}
    today = _today()
    days = _days_between(today, lease[0]["next_due"])
    return {**lease[0], "found": True, "today": today, "days_until_due": days, "overdue": days < 0}


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """The cash on hand in an account, and how much is already tied up in payments waiting for approval.

    Only cash goes out in this shop (no revenue is modeled), so this balance is all there is.

    Args:
        account: Cash account name; the shop has "checking".
    """
    rows = _query("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,))
    if not rows:
        names = [r["name"] for r in _query("SELECT name FROM cash_accounts")]
        return {"account": account, "found": False, "note": f"No account {account}; accounts: {names}."}
    pending = _pending_total()
    return {**rows[0], "found": True, "pending_requests_total": pending,
            "balance_after_pending": round(rows[0]["balance"] - pending, 2)}


@mcp.tool
def list_payments(ticket_id: int = 0) -> dict:
    """Payments prepared (pending, approved, rejected, refused) and payments actually made.

    Args:
        ticket_id: Only requests for this ticket; 0 for all.
    """
    requests: list[dict] = []
    if _has_requests_table():
        sql, params = "SELECT * FROM payment_requests", ()
        if ticket_id:
            sql, params = sql + " WHERE ticket_id = ?", (ticket_id,)
        requests = _query(sql + " ORDER BY id", params)
    return {"requests": requests,
            "payments_made": _query("SELECT * FROM payments ORDER BY id")}


# ---------------------------------------------------------------- agent write tools (no money moves)

@mcp.tool
def prepare_payment(kind: Literal["invoice", "rent", "purchase_order"], ref_id: int, reason: str,
                    ticket_id: int = 0, sku: str = "", size: str = "", qty: int = 0,
                    prepared_by: str = "") -> dict:
    """Prepare a payment for a HUMAN to approve. This does not pay anything or change cash.

    The amount is taken from the database, not from the caller: the invoice amount, the lease's
    monthly rent, or (purchase order) qty x the product's unit cost. Refuses if the amount is more
    than the cash on hand, if the bill is already paid, or if the same payment is already pending.

    Args:
        kind: "invoice" (ref_id = invoice id), "rent" (ref_id = lease id), or
            "purchase_order" (ref_id = vendor id, plus sku, size, qty).
        ref_id: The invoice, lease, or vendor id.
        reason: Why this payment is needed (which ticket, what it unblocks).
        ticket_id: The ticket this payment is for.
        sku, size, qty: For purchase orders only: what to restock.
        prepared_by: Filled in by the system with the agent's name.
    """
    today = _today()
    extra: dict = {}
    if kind == "invoice":
        rows = _query("SELECT i.id, i.amount, i.status, v.name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                      "WHERE i.id = ?", (ref_id,))
        if not rows:
            return {"prepared": False, "note": f"No invoice {ref_id}."}
        if rows[0]["status"] != "open":
            return {"prepared": False, "note": f"Invoice {ref_id} is already {rows[0]['status']}."}
        amount, payee = rows[0]["amount"], rows[0]["name"]
    elif kind == "rent":
        rows = _query("SELECT landlord, monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,))
        if not rows:
            return {"prepared": False, "note": f"No lease {ref_id}."}
        amount, payee = rows[0]["monthly_rent"], rows[0]["landlord"]
        extra["rent_due"] = rows[0]["next_due"]
    else:
        vendor = _query("SELECT name, lead_days FROM vendors WHERE id = ?", (ref_id,))
        price = _query("SELECT unit_cost FROM pricing WHERE sku = ?", (sku.strip().upper(),))
        if not vendor:
            return {"prepared": False, "note": f"No vendor {ref_id}."}
        if not price or qty <= 0 or not size.strip():
            return {"prepared": False, "note": "A purchase order needs a priced sku, a size, and qty > 0."}
        amount, payee = round(price[0]["unit_cost"] * qty, 2), vendor[0]["name"]
        open_inv = _query("SELECT id, amount FROM invoices WHERE vendor_id = ? AND status = 'open'", (ref_id,))
        extra["vendor_blocked_by_invoices"] = open_inv
        extra["expected_delivery_if_shipped_today"] = (
            date.fromisoformat(today) + timedelta(days=vendor[0]["lead_days"])).isoformat()

    balance = _balance() or 0.0
    if amount > balance:
        return {"prepared": False, "amount": amount, "balance": balance,
                "note": f"Refused: ${amount:,.2f} is more than the ${balance:,.2f} in checking "
                        f"(short ${amount - balance:,.2f}). No negative balances."}

    with _connect_rw() as conn:
        dup = conn.execute("SELECT id FROM payment_requests WHERE kind = ? AND ref_id = ? AND status = 'pending' "
                           "AND COALESCE(sku,'') = ? AND COALESCE(size,'') = ?",
                           (kind, ref_id, sku.strip().upper(), size.strip().upper())).fetchone()
        if dup:
            return {"prepared": False, "request_id": dup["id"], "note": f"Already pending as request {dup['id']}."}
        cur = conn.execute(
            "INSERT INTO payment_requests (ticket_id, kind, ref_id, payee, amount, sku, size, qty, reason, "
            "prepared_by, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (ticket_id or None, kind, ref_id, payee, amount, sku.strip().upper() or None,
             size.strip().upper() or None, qty or None, reason, prepared_by or "unknown", _now()))
        request_id = cur.lastrowid
    pending = _pending_total()
    return {"prepared": True, "request_id": request_id, "kind": kind, "ref_id": ref_id, "payee": payee,
            "amount": amount, "status": "pending", "needs_human_approval": True, "balance": balance,
            "pending_requests_total": pending, "balance_if_all_pending_approved": round(balance - pending, 2),
            **extra, "note": "Prepared only. Nothing is paid until a human approves it on the board."
            + (f" Warning: all pending payments together (${pending:,.2f}) are more than the ${balance:,.2f} "
               "in checking, so not all of them can be approved." if pending > balance else "")}


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str = "", updated_by: str = "") -> dict:
    """Set a ticket's status and add a note. A ticket can't be marked resolved while a payment
    for it is still waiting for human approval.

    Args:
        ticket_id: Ticket number.
        status: open, in_progress, waiting_on_approval, needs_human, or resolved.
        note: Short note to add to the ticket (appended, never overwrites earlier notes).
        updated_by: Filled in by the system with the agent's name.
    """
    if status not in TICKET_STATUSES:
        return {"updated": False, "note": f"Status must be one of {TICKET_STATUSES}."}
    with _connect_rw() as conn:
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            return {"updated": False, "note": f"No ticket {ticket_id}."}
        pending = conn.execute("SELECT COUNT(*) FROM payment_requests WHERE ticket_id = ? AND status = 'pending'",
                               (ticket_id,)).fetchone()[0]
        if status == "resolved" and pending:
            return {"updated": False, "note": f"Ticket {ticket_id} has {pending} payment(s) waiting for human "
                                              "approval; use waiting_on_approval."}
        notes = row["notes"] or ""
        if note.strip():
            stamp = f"[{_today()} {updated_by or 'unknown'}] {note.strip()}"
            notes = f"{notes}\n{stamp}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return {"updated": True, "ticket_id": ticket_id, "old_status": row["status"], "status": status}


# ---------------------------------------------------------------- human-only tools (never given to agents)

@mcp.tool
def approve_payment(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Pay a prepared request: the only tool that moves cash.

    Refuses if the cash would go negative, or (purchase orders) if the vendor still has an open
    unpaid invoice. On success: lowers checking, records the payment, marks the invoice paid or moves
    the lease's next due date a month, and resolves the ticket if it was only waiting on approval.

    Args:
        request_id: The payment request to approve.
        approved_by: Name of the person approving (not an agent).
    """
    who = approved_by.strip()
    if not who or who.lower() in AGENT_NAMES:
        return {"approved": False, "note": "approved_by must be the name of a human, not an agent."}
    today = _today()
    with _connect_rw() as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return {"approved": False, "note": f"No payment request {request_id}."}
        if req["status"] != "pending":
            return {"approved": False, "note": f"Request {request_id} is already {req['status']}."}
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]

        def refuse(reason: str) -> dict:
            conn.execute("UPDATE payment_requests SET status='refused', decided_by=?, decided_at=?, decision_note=? "
                         "WHERE id=?", (who, _now(), reason, request_id))
            return {"approved": False, "request_id": request_id, "balance": balance, "note": f"Refused: {reason}"}

        if req["amount"] > balance:
            return refuse(f"${req['amount']:,.2f} is more than the ${balance:,.2f} in checking; no negative balances.")
        updates: dict = {}
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if not inv or inv["status"] != "open":
                return refuse(f"invoice {req['ref_id']} is not open.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updates["invoice"] = {"id": req["ref_id"], "status": "paid"}
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            new_due = _add_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            updates["lease"] = {"id": req["ref_id"], "paid_through": lease["next_due"], "next_due": new_due}
        else:
            blocking = conn.execute("SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'",
                                    (req["ref_id"],)).fetchall()
            if blocking:
                ids = [r["id"] for r in blocking]
                return refuse(f"vendor {req['ref_id']} still has open invoice(s) {ids} and won't ship.")
            vendor = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (req["ref_id"],)).fetchone()
            updates["purchase_order"] = {"vendor_id": req["ref_id"], "sku": req["sku"], "size": req["size"],
                                         "qty": req["qty"], "expected_delivery":
                                         (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()}
        new_balance = round(balance - req["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'", (new_balance, today))
        cur = conn.execute("INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                           "VALUES (?, ?, ?, 'checking', ?, ?)", (req["kind"], req["ref_id"], req["amount"], today, who))
        conn.execute("UPDATE payment_requests SET status='approved', decided_by=?, decided_at=?, payment_id=? "
                     "WHERE id=?", (who, _now(), cur.lastrowid, request_id))
        ticket_status = None
        if req["ticket_id"]:
            # Resolve the ticket only if the Boss said approval was all it was waiting on.
            left = conn.execute("SELECT COUNT(*) FROM payment_requests WHERE ticket_id = ? AND status = 'pending'",
                                (req["ticket_id"],)).fetchone()[0]
            current = conn.execute("SELECT status FROM tickets WHERE id = ?", (req["ticket_id"],)).fetchone()
            ticket_status = current["status"] if current else None
            if ticket_status == "waiting_on_approval" and left == 0:
                ticket_status = "resolved"
                conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (req["ticket_id"],))
    return {"approved": True, "request_id": request_id, "payment_id": cur.lastrowid, "amount": req["amount"],
            "payee": req["payee"], "old_balance": balance, "new_balance": new_balance, "approved_by": who,
            "paid_at": today, "updated": updates, "ticket_id": req["ticket_id"], "ticket_status": ticket_status}


@mcp.tool
def reject_payment(request_id: int, rejected_by: str, reason: str = "") -> dict:
    """HUMAN ONLY. Turn down a prepared payment. No money moves.

    Args:
        request_id: The payment request to reject.
        rejected_by: Name of the person rejecting (not an agent).
        reason: Why it was rejected.
    """
    who = rejected_by.strip()
    if not who or who.lower() in AGENT_NAMES:
        return {"rejected": False, "note": "rejected_by must be the name of a human, not an agent."}
    with _connect_rw() as conn:
        req = conn.execute("SELECT status, ticket_id FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return {"rejected": False, "note": f"No payment request {request_id}."}
        if req["status"] != "pending":
            return {"rejected": False, "note": f"Request {request_id} is already {req['status']}."}
        conn.execute("UPDATE payment_requests SET status='rejected', decided_by=?, decided_at=?, decision_note=? "
                     "WHERE id=?", (who, _now(), reason, request_id))
        if req["ticket_id"]:
            conn.execute("UPDATE tickets SET status = 'needs_human' WHERE id = ?", (req["ticket_id"],))
    return {"rejected": True, "request_id": request_id, "rejected_by": who, "ticket_id": req["ticket_id"]}


if __name__ == "__main__":
    mcp.run(show_banner=False)  # stdio
