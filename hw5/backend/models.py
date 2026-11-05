"""Data types for the Campus Customs agent team (backend).

- AgentName: the five roles
- AgentEvent: one step of a ticket run (who did what), for the board and the audit trail
- RunState / TeamDeps: what every agent run carries: the ticket, the delegation chain, budgets
- PaymentRequest, CustomerDraft, TicketOutcome: what the Boss reports when a ticket is done
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")
AGENT_TITLES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AgentEvent(BaseModel):
    """One step of an agent loop: an agent starting or finishing, a delegation, or an MCP tool call."""

    run_id: str
    ticket_id: int | None
    time: str = Field(default_factory=now_iso)
    type: Literal["run_started", "agent_started", "model_step", "delegation", "delegation_refused",
                  "tool_call", "tool_result", "tool_blocked", "agent_finished", "run_finished",
                  "approval", "rejection", "reset", "error"]
    agent: AgentName | Literal["human", "system"]
    chain: list[str] = Field(default_factory=list)  # who asked whom to get here, e.g. ["boss", "inventory"]
    depth: int = 0  # 0 = Boss, 1 = asked by the Boss, 2 = asked by a specialist
    step: int | None = None  # model step number within this agent's run (1, 2, ...)
    model: str | None = None  # model that produced a model_step (must be gpt-6-luna)
    target: AgentName | None = None  # for delegations: who was asked
    tool: str | None = None  # for MCP tool calls
    tool_call_id: str | None = None  # links a tool_call to its tool_result
    args: dict[str, Any] | None = None
    text: str | None = None  # the task, reply, tool result, or error
    usage: dict[str, int] | None = None  # tokens and requests for a model step or a finished agent


@dataclass
class RunState:
    """Shared by every agent working one ticket: the event log and the team-wide budgets."""

    ticket_id: int | None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    events: list[AgentEvent] = field(default_factory=list)
    delegations: int = 0
    tool_calls: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    listeners: list[Any] = field(default_factory=list)  # callbacks (e.g. the audit trail, the live board)

    def emit(self, **data: Any) -> AgentEvent:
        event = AgentEvent(run_id=self.run_id, ticket_id=self.ticket_id, **data)
        self.events.append(event)
        for listener in self.listeners:
            listener(event)
        return event


@dataclass
class TeamDeps:
    """What one agent run receives: who it is, how it got here, and the shared run state."""

    agent: AgentName
    run: RunState
    chain: tuple[AgentName, ...] = ()  # agents above this one in the current delegation chain
    depth: int = 0


class PaymentRequest(BaseModel):
    """A payment an agent has prepared. It is NOT paid until a human approves it."""

    request_id: int | None = Field(default=None, description="The payment_requests id from prepare_payment / list_payments.")
    kind: Literal["invoice", "rent", "purchase_order"]
    ref_id: int | None = Field(description="Invoice id, lease id, or (for a purchase order) vendor id.")
    payee: str
    amount: float = Field(gt=0)
    reason: str


class CustomerDraft(BaseModel):
    """A message drafted for a customer or requester. Drafts stay on the board; nothing is sent."""

    to: str
    subject: str
    body: str


class TicketOutcome(BaseModel):
    """The Boss's final report on a ticket."""

    ticket_id: int
    decision: str = Field(description="The Boss's call on the ticket, in one or two sentences.")
    summary: str = Field(description="What the team found and did, citing the facts from the tools.")
    agents_consulted: list[AgentName] = Field(description="Agents that worked on this ticket, in order.")
    payments_requested: list[PaymentRequest] = Field(
        default_factory=list, description="Payments prepared for human approval (not yet paid).")
    customer_drafts: list[CustomerDraft] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list, description="Anything a human still needs to decide.")
    status: Literal["resolved", "waiting_on_approval", "needs_human"] = "waiting_on_approval"
