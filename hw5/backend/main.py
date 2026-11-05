"""Campus Customs backend: the routes the React board calls.

Start it from the backend/ folder:   uvicorn main:app --reload --port 8000

Shop facts come only from the MCP server (mcp_server/server.py) over data/campus_customs_new.db,
the same server the agents use; the backend holds one MCP connection open for its routes. The
only route that moves cash is POST /payments/{id}/approve, which a human triggers on the board.

Routes
  GET  /tickets                    the three tickets, open or resolved, plus each one's last outcome
  POST /tickets/{ticket_id}/run    start the agent team on a ticket (runs in the background)
  GET  /events                     recent agent events (what each agent said, which tools it used)
  GET  /payments                   payments the agents prepared (pending / approved / ...) and payments made
  POST /payments/{id}/approve      a human approves a payment; this is what changes cash
  POST /payments/{id}/reject       a human turns a payment down (no money moves)
  GET  /cash                       the current checking balance from cash_accounts
  POST /reset                      copy the original database over the working copy for a fresh run
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]  # HW5/
if str(ROOT) not in sys.path:  # so "uvicorn main:app" works from inside backend/
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.agents.config import MCP_SERVER  # noqa: E402
from backend.agents.team import run_ticket  # noqa: E402
from backend.audit import append_event, read_audit  # noqa: E402
from backend.models import AgentEvent, RunState  # noqa: E402

ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}

state: dict[str, Any] = {"mcp": None, "running": {}, "tasks": set()}
_mcp_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = Client(StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], cwd=str(ROOT)))
    async with client:
        state["mcp"] = client
        yield
    state["mcp"] = None


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
app.add_middleware(  # the Vite board (Problem 8) runs on port 5173
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, **args: Any) -> dict:
    """Call one MCP tool for a route and return its result as a dict."""
    client: Client = state["mcp"]
    if client is None:
        raise HTTPException(503, "MCP server is not connected")
    async with _mcp_lock:  # one call at a time on the shared connection
        result = await client.call_tool(tool, args)
    data = result.structured_content or result.data
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    return data if isinstance(data, dict) else json.loads(json.dumps(data, default=str))


def _audit(event_type: str, ticket_id: int | None, text: str, args: dict | None = None,
           run_id: str = "human") -> None:
    append_event(AgentEvent(run_id=run_id, ticket_id=ticket_id, type=event_type, agent="human",
                            text=text, args=args))


def _last_outcomes() -> dict[int, dict]:
    """Each ticket's most recent finished run, from the audit trail (survives a server restart)."""
    outcomes: dict[int, dict] = {}
    for rec in read_audit():
        if rec.get("type") == "reset":  # a reset starts the shop over: earlier runs no longer count
            outcomes.clear()
        elif rec.get("type") == "run_finished" and rec.get("ticket_id") is not None:
            outcomes[rec["ticket_id"]] = {"run_id": rec["run_id"], "time": rec["time"],
                                          "decision": rec.get("text"), **(rec.get("args") or {})}
    return outcomes


# ---------------------------------------------------------------- a) tickets

@app.get("/tickets")
async def get_tickets() -> dict:
    """The tickets on the board: status from the database, open or resolved, and the last outcome.

    A ticket counts as resolved once the team has finished a run on it (since the last reset) or
    the database says resolved; `status` keeps the detail (e.g. waiting_on_approval).
    """
    board = await mcp("list_tickets")
    outcomes = _last_outcomes()
    tickets = []
    for t in board["tickets"]:
        full = await mcp("get_ticket", ticket_id=t["id"])
        running = t["id"] in state["running"]
        done = t["status"] == "resolved" or (t["id"] in outcomes and not running)
        tickets.append({
            **full,
            "state": "resolved" if done else "open",
            "running": running,
            "run_id": state["running"].get(t["id"]),
            "last_outcome": outcomes.get(t["id"]),
        })
    return {"today": (await mcp("get_desk")).get("date_today"), "tickets": tickets}


# ---------------------------------------------------------------- b) run the team

async def _run(ticket_id: int, run: RunState) -> None:
    try:
        await run_ticket(ticket_id, run=run)  # the outcome is saved on the run_finished record
    except Exception:
        pass  # run_ticket already wrote the error to the audit trail
    finally:
        state["running"].pop(ticket_id, None)


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket_route(ticket_id: int) -> dict:
    """Start the agent team on one ticket. Returns at once; follow progress with GET /events."""
    ticket = await mcp("get_ticket", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(404, ticket.get("note", f"No ticket {ticket_id}"))
    if state["running"]:
        busy = ", ".join(str(t) for t in state["running"])
        raise HTTPException(409, f"The team is already working ticket {busy}; one ticket at a time.")
    run = RunState(ticket_id=ticket_id)
    state["running"][ticket_id] = run.run_id
    task = asyncio.create_task(_run(ticket_id, run))
    state["tasks"].add(task)
    task.add_done_callback(state["tasks"].discard)
    return {"started": True, "ticket_id": ticket_id, "run_id": run.run_id}


# ---------------------------------------------------------------- c) events

@app.get("/events")
async def get_events(since: int = Query(0, ge=0, description="Return records after this index"),
                     ticket_id: int | None = None, run_id: str | None = None,
                     limit: int = Query(200, ge=1, le=2000)) -> dict:
    """Recent agent events from the audit trail: who said what, delegations, and every tool call.

    Poll with since=<next_since from the last reply> to get only new events.
    """
    records = read_audit()
    picked = []
    for i, rec in enumerate(records[since:], start=since):
        if ticket_id is not None and rec.get("ticket_id") != ticket_id:
            continue
        if run_id and rec.get("run_id") != run_id:
            continue
        picked.append({"index": i, **rec})
    return {"next_since": len(records), "running": state["running"], "events": picked[-limit:]}


# ---------------------------------------------------------------- d) approve (the only route that moves cash)

class Decision(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the person clicking approve")
    note: str = ""


@app.get("/payments")
async def get_payments(ticket_id: int = 0) -> dict:
    """Payments the agents prepared (with status) and payments actually made."""
    return await mcp("list_payments", ticket_id=ticket_id)


@app.post("/payments/{request_id}/approve")
async def approve(request_id: int, body: Decision) -> dict:
    """A human approves a prepared payment. Refused if cash would go negative or a vendor is blocked."""
    if body.approved_by.strip().lower() in AGENT_NAMES:
        raise HTTPException(400, "Approvals must come from a person, not an agent.")
    before = await mcp("get_cash_balance")
    result = await mcp("approve_payment", request_id=request_id, approved_by=body.approved_by.strip())
    after = await mcp("get_cash_balance")
    verb = "Approved" if result.get("approved") else "Approval refused for"
    _audit("approval", result.get("ticket_id"), f"{verb} payment request {request_id} by {body.approved_by}. "
           f"{result.get('note', '')}".strip(),
           {"request_id": request_id, "result": result, "balance_before": before.get("balance"),
            "balance_after": after.get("balance"), "note": body.note or None})
    if not result.get("approved"):
        raise HTTPException(409, result.get("note", "Approval refused"))
    return {**result, "balance": after.get("balance")}


@app.post("/payments/{request_id}/reject")
async def reject(request_id: int, body: Decision) -> dict:
    """A human turns a prepared payment down. No money moves."""
    result = await mcp("reject_payment", request_id=request_id, rejected_by=body.approved_by.strip(),
                       reason=body.note)
    _audit("rejection", result.get("ticket_id"), f"Payment request {request_id} rejected by {body.approved_by}.",
           {"request_id": request_id, "result": result, "note": body.note or None})
    if not result.get("rejected"):
        raise HTTPException(409, result.get("note", "Rejection failed"))
    return result


# ---------------------------------------------------------------- e) cash

@app.get("/cash")
async def get_cash() -> dict:
    """The current checking balance from cash_accounts (and what is waiting for approval)."""
    return await mcp("get_cash_balance", account="checking")


# ---------------------------------------------------------------- f) reset

@app.post("/reset")
async def reset() -> dict:
    """Copy the original database over the working copy. The audit trail is kept (never wiped)."""
    if state["running"]:
        raise HTTPException(409, "Wait for the running ticket to finish before resetting.")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    cash = await mcp("get_cash_balance")
    _audit("reset", None, f"Working database reset from {ORIGINAL_DB.name}.",
           {"balance": cash.get("balance")}, run_id="reset")
    return {"reset": True, "balance": cash.get("balance"), "tickets": (await mcp("list_tickets"))["tickets"]}


@app.get("/")
async def index() -> dict:
    return {"service": "Campus Customs backend", "docs": "/docs",
            "routes": ["GET /tickets", "POST /tickets/{id}/run", "GET /events", "GET /payments",
                       "POST /payments/{id}/approve", "POST /payments/{id}/reject", "GET /cash", "POST /reset"]}
