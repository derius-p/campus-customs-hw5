"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

How the loop works
- Every agent is a PydanticAI Agent on gpt-6-luna with its prompt from backend/prompts/<name>.md.
- Every agent gets the same delegation tool, ask_agent(agent, task): it runs the other agent's own
  loop (model -> tools -> model ...) and hands back that agent's answer. So any agent can delegate
  to any other: Boss -> Inventory -> Accounting, Facilities -> Accounting, and so on.
- Guards keep the team from looping: no asking yourself, no asking anyone already in the current
  chain (so no A -> B -> A), at most MAX_DEPTH levels, at most MAX_DELEGATIONS per ticket, a
  team-wide token and tool-call budget per ticket, and request/tool/token caps on every agent run.
- Shop facts come only from the MCP server (mcp_server/server.py). One server process is shared by
  the whole team for a ticket; each agent only sees the MCP tools its job needs (AGENT_TOOLS).
  The human-only tools (approve_payment, reject_payment) are never given to any agent.
- Every loop step (each model response, delegation, MCP call and result) is an AgentEvent on
  RunState and is appended to output/audit_trail.json as it happens.
- The Boss returns a TicketOutcome; specialists return plain-text answers.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import TextPart, ToolCallPart

from backend.agents.config import (
    BOSS_LIMITS,
    MAX_DELEGATIONS,
    MAX_DEPTH,
    MAX_TICKET_TOKENS,
    MAX_TICKET_TOOL_CALLS,
    PROMPTS_DIR,
    SPECIALIST_LIMITS,
    TOOL_RESULT_CHARS,
    build_mcp_toolset,
    build_model,
)
from backend.audit import append_event
from backend.models import AGENT_NAMES, AGENT_TITLES, AgentName, RunState, TeamDeps, TicketOutcome

# MCP tools each agent may see (everything comes from data/campus_customs_new.db through the server).
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": {"get_desk", "list_tickets", "get_ticket", "get_cash_balance", "list_payments", "update_ticket"},
    "inventory": {"get_desk", "get_ticket", "check_stock", "list_vendors", "check_vendor_invoices"},
    "accounting": {"get_desk", "get_ticket", "get_cash_balance", "get_invoice", "check_vendor_invoices",
                   "check_stock", "check_margin", "get_lease", "list_payments", "prepare_payment"},
    "facilities": {"get_desk", "get_ticket", "get_lease"},
    "customer_service": {"get_desk", "get_ticket", "check_stock"},
}
HUMAN_ONLY_TOOLS = {"approve_payment", "reject_payment"}  # only the backend's approve/reject buttons
SIGNED_TOOLS = {"prepare_payment": "prepared_by", "update_ticket": "updated_by"}  # stamped with the agent's name
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())


class TicketBudgetExceeded(RuntimeError):
    pass


def _short(value: Any, limit: int = TOOL_RESULT_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _chain(deps: TeamDeps) -> list[str]:
    return [*deps.chain, deps.agent]


def _over_budget(run: RunState) -> str | None:
    if run.input_tokens + run.output_tokens >= MAX_TICKET_TOKENS:
        return f"ticket token budget used ({run.input_tokens + run.output_tokens:,} of {MAX_TICKET_TOKENS:,})"
    if run.tool_calls >= MAX_TICKET_TOOL_CALLS:
        return f"ticket tool-call budget used ({run.tool_calls} of {MAX_TICKET_TOOL_CALLS})"
    return None


async def _log_mcp_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    """Wraps every MCP tool call: blocks human-only tools, signs writes, and logs call + result."""
    deps, run = ctx.deps, ctx.deps.run
    call_id = getattr(ctx, "tool_call_id", None)
    base = dict(agent=deps.agent, tool=name, tool_call_id=call_id, chain=_chain(deps), depth=deps.depth)
    if name in HUMAN_ONLY_TOOLS or name not in AGENT_TOOLS[deps.agent]:
        run.emit(type="tool_blocked", args=args, text="Agents may not call this tool.", **base)
        return {"error": f"{name} is not available to {deps.agent}. Payments are approved only by a human."}
    if reason := _over_budget(run):
        run.emit(type="tool_blocked", args=args, text=reason, **base)
        return {"error": f"Stopped: {reason}. Finish with what you have."}
    if name in SIGNED_TOOLS:
        args = {**args, SIGNED_TOOLS[name]: deps.agent}  # the server records who prepared / updated it
    if name == "prepare_payment" and not args.get("ticket_id") and run.ticket_id:
        args = {**args, "ticket_id": run.ticket_id}  # link the payment to the ticket being worked
    run.tool_calls += 1
    run.emit(type="tool_call", args=args, **base)
    try:
        result = await call_tool(name, args)
    except Exception as exc:  # e.g. the server rejects made-up arguments; the agent is asked to retry
        run.emit(type="error", text=f"{name} rejected: {type(exc).__name__}: {_short(str(exc), 600)}", **base)
        raise
    run.emit(type="tool_result", text=_short(result), **base)
    return result


MCP = build_mcp_toolset(process_tool_call=_log_mcp_call)


def load_prompt(name: AgentName) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _team_note(ctx: RunContext[TeamDeps]) -> str:
    """Added to every agent's instructions on each run: who it can still ask, and the budget left."""
    deps, run = ctx.deps, ctx.deps.run
    blocked = set(deps.chain) | {deps.agent}
    if deps.depth >= MAX_DEPTH or run.delegations >= MAX_DELEGATIONS:
        can_ask = "nobody (delegation limit reached); answer with what your own tools show"
    else:
        can_ask = ", ".join(n for n in AGENT_NAMES if n not in blocked) or "nobody"
    used = run.input_tokens + run.output_tokens
    return (
        f"Delegation chain so far: {' -> '.join(_chain(deps))}. You may ask: {can_ask}. "
        f"Delegations left for this ticket: {max(0, MAX_DELEGATIONS - run.delegations)}. "
        f"Team budget used: {used:,} of {MAX_TICKET_TOKENS:,} tokens, {run.tool_calls} of "
        f"{MAX_TICKET_TOOL_CALLS} tool calls. Be efficient: don't repeat a lookup you already have."
    )


async def ask_agent(ctx: RunContext[TeamDeps], agent: AgentName, task: str) -> str:
    """Ask another member of the team to do a specific piece of work and return their answer.

    Args:
        agent: who to ask: boss, inventory, accounting, facilities, or customer_service.
        task: a precise request with the ids and values they need (ticket id, SKU, size, qty, invoice or lease id).
    """
    me, run = ctx.deps, ctx.deps.run

    def refuse(reason: str) -> str:
        run.emit(type="delegation_refused", agent=me.agent, target=agent, text=f"{reason} | task: {task}",
                 chain=_chain(me), depth=me.depth)
        return f"Refused: {reason}"

    if agent == me.agent:
        return refuse(f"you are {agent}; do this yourself.")
    if agent in me.chain:
        return refuse(f"{agent} is already waiting on this chain ({' -> '.join(_chain(me))}); answer them instead.")
    if me.depth >= MAX_DEPTH:
        return refuse("delegation depth limit reached; answer with what your own tools show.")
    if run.delegations >= MAX_DELEGATIONS:
        return refuse("this ticket has used all its delegations; finish with what you have.")
    if reason := _over_budget(run):
        return refuse(f"{reason}; finish with what you have.")

    run.delegations += 1
    run.emit(type="delegation", agent=me.agent, target=agent, text=task, chain=_chain(me), depth=me.depth)
    sub = TeamDeps(agent=agent, run=run, chain=tuple(_chain(me)), depth=me.depth + 1)
    try:
        answer = await run_agent(agent, task, sub)
    except Exception as exc:  # a failed specialist shouldn't crash the whole ticket
        run.emit(type="error", agent=agent, text=f"{type(exc).__name__}: {exc}", chain=_chain(sub), depth=sub.depth)
        return f"{AGENT_TITLES[agent]} could not finish: {type(exc).__name__}: {exc}"
    return str(answer)


def _build_agent(name: AgentName) -> Agent[TeamDeps, Any]:
    allowed = AGENT_TOOLS[name]
    agent = Agent(
        build_model(),
        name=name,
        deps_type=TeamDeps,
        output_type=TicketOutcome if name == "boss" else str,
        instructions=load_prompt(name),
        tools=[ask_agent],
        toolsets=[MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
        retries=2,
    )
    agent.instructions(_team_note)
    return agent


AGENTS: dict[AgentName, Agent[TeamDeps, Any]] = {name: _build_agent(name) for name in AGENT_NAMES}


async def run_agent(name: AgentName, task: str, deps: TeamDeps) -> Any:
    """Runs one agent's loop step by step, logging each model response and its token use."""
    run = deps.run
    where = dict(chain=_chain(deps), depth=deps.depth)
    run.emit(type="agent_started", agent=name, text=task, **where)
    limits = BOSS_LIMITS if name == "boss" else SPECIALIST_LIMITS
    step = 0
    async with AGENTS[name].iter(task, deps=deps, usage_limits=limits) as agent_run:
        async for node in agent_run:
            if not Agent.is_call_tools_node(node):
                continue
            step += 1
            response = node.model_response
            text = "\n".join(p.content for p in response.parts if isinstance(p, TextPart)).strip()
            calls = [{"tool": p.tool_name, "args": p.args_as_dict(), "tool_call_id": p.tool_call_id}
                     for p in response.parts if isinstance(p, ToolCallPart)]
            used = response.usage
            run.model_requests += 1
            run.input_tokens += used.input_tokens or 0
            run.output_tokens += used.output_tokens or 0
            run.emit(type="model_step", agent=name, step=step, model=response.model_name,
                     text=_short(text) if text else None, args={"tool_calls": calls} if calls else None,
                     usage={"input_tokens": used.input_tokens or 0, "output_tokens": used.output_tokens or 0},
                     **where)
            if reason := _over_budget(run):
                raise TicketBudgetExceeded(reason)
        result = agent_run.result
    output = result.output
    usage = result.usage
    text = output.model_dump_json() if hasattr(output, "model_dump_json") else str(output)
    run.emit(type="agent_finished", agent=name, text=_short(text), step=step,
             usage={"requests": usage.requests, "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0}, **where)
    return output


def ticket_task(ticket_id: int) -> str:
    return (f"Work ticket {ticket_id}. Read it with get_ticket first, then handle it under the shop rules. "
            f"Keep the ticket's status current with update_ticket as you go.")


async def run_ticket(ticket_id: int, run: RunState | None = None, audit: bool = True) -> tuple[TicketOutcome, RunState]:
    """Hands one ticket to the Boss and returns its TicketOutcome plus the full event log.

    The Boss gets only the ticket id; it reads the ticket itself through the MCP server.
    """
    run = run or RunState(ticket_id=ticket_id)
    if audit and append_event not in run.listeners:
        run.listeners.append(append_event)
    task = ticket_task(ticket_id)
    run.emit(type="run_started", agent="system", text=task)
    try:
        async with MCP:  # one MCP server process for the whole team on this ticket
            outcome = await run_agent("boss", task, TeamDeps(agent="boss", run=run))
    except Exception as exc:
        run.emit(type="error", agent="system", text=f"{type(exc).__name__}: {exc}")
        raise
    run.emit(type="run_finished", agent="system", text=outcome.decision,
             args={"outcome": outcome.model_dump(mode="json")},
             usage={"requests": run.model_requests, "input_tokens": run.input_tokens,
                    "output_tokens": run.output_tokens, "tool_calls": run.tool_calls,
                    "delegations": run.delegations})
    return outcome, run
