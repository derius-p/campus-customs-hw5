import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import { api, API_BASE } from "./api";
import {
  AGENTS, AGENT_BY_ID, TOOL_LABELS, agentName, argsText, clock, latestRunId, liveStatus, money, prettyDate, summarize,
} from "./agents";
import type { AgentEvent, AgentName, CashInfo, PaymentsReply, Ticket, TicketOutcome } from "./types";
import "./App.css";
import BrandLockup from "./components/BrandLockup";
import YaleY from "./components/YaleY";
import Portrait from "./components/Portrait";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};
const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_on_approval: "Awaiting approval",
  needs_human: "Needs a human",
  resolved: "Resolved",
};

type CashPoint = { time: number; balance: number; delta: number; label: string };
type Toast = { id: number; kind: "ok" | "warn" | "error"; text: string };

// ------------------------------------------------------------------ small hooks

function useTween(value: number | undefined, ms = 900) {
  const [shown, setShown] = useState(value ?? 0);
  const from = useRef(value ?? 0);
  useEffect(() => {
    if (value == null) return;
    if (ms <= 0) {
      setShown(value);
      from.current = value;
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(a + (value - a) * eased);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
}

// ------------------------------------------------------------------ app

export default function App() {
  const [today, setToday] = useState<string>("");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  // ?ticket=103&view=summary opens the board on one ticket (used for the resolved-board screenshots)
  const params = new URLSearchParams(window.location.search);
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get("ticket")) || null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [payments, setPayments] = useState<PaymentsReply>({ requests: [], payments_made: [] });
  const [cash, setCash] = useState<CashInfo | null>(null);
  const [cashHistory, setCashHistory] = useState<CashPoint[]>([]);
  const [flash, setFlash] = useState<"down" | "up" | null>(null);
  const [view, setView] = useState<"live" | "summary">(() => (params.get("view") === "summary" ? "summary" : "live"));
  const [approver, setApprover] = useState(() => localStorage.getItem("cc-approver") ?? "");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const lastBalance = useRef<number | null>(null);
  const wasRunning = useRef<Record<number, boolean>>({});

  const toast = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  useEffect(() => localStorage.setItem("cc-approver", approver), [approver]);

  const anyRunning = tickets.some((t) => t.running);
  const selected = tickets.find((t) => t.id === selectedId) ?? null;

  // --- polling: fast while the team is working, slower when idle
  const refresh = useCallback(async () => {
    try {
      const [tk, c, p] = await Promise.all([api.tickets(), api.cash(), api.payments()]);
      setOffline(false);
      setToday(tk.today);
      setTickets(tk.tickets);
      setPayments(p);
      setCash(c);
      if (lastBalance.current !== null && c.balance !== lastBalance.current) {
        const delta = c.balance - lastBalance.current;
        const paid = p.payments_made[p.payments_made.length - 1];
        const label = delta < 0 && paid ? `${paid.kind.replace("_", " ")} · approved by ${paid.approved_by}` : "Database reset";
        setCashHistory((h) => [...h, { time: Date.now(), balance: c.balance, delta, label }]);
        setFlash(delta < 0 ? "down" : "up");
        setTimeout(() => setFlash(null), 1600);
      }
      if (lastBalance.current === null) setCashHistory([{ time: Date.now(), balance: c.balance, delta: 0, label: "Opening balance" }]);
      lastBalance.current = c.balance;
      setSelectedId((id) => id ?? tk.tickets[0]?.id ?? null);
      for (const t of tk.tickets) {
        if (wasRunning.current[t.id] && !t.running) {
          toast("ok", `Ticket ${t.id} finished: ${STATUS_LABEL[t.status] ?? t.status}.`);
          if (t.id === selectedId) setView("summary");
        }
        wasRunning.current[t.id] = t.running;
      }
    } catch {
      setOffline(true);
    }
  }, [selectedId, toast]);

  const refreshEvents = useCallback(async () => {
    if (selectedId == null) return;
    try {
      const r = await api.events(selectedId);
      setEvents(r.events);
    } catch {
      /* shown by the offline banner */
    }
  }, [selectedId]);

  useEffect(() => {
    let stop = false;
    let timer: number;
    const loop = async () => {
      await Promise.all([refresh(), refreshEvents()]);
      if (!stop) timer = window.setTimeout(loop, anyRunning ? 1200 : 4000);
    };
    loop();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [refresh, refreshEvents, anyRunning]);

  // --- the run on screen: the one going now, else the latest one for this ticket
  const runId = selected?.run_id ?? latestRunId(events);
  const runEvents = useMemo(() => (runId ? events.filter((e) => e.run_id === runId) : []), [events, runId]);
  const humanEvents = useMemo(
    () => events.filter((e) => e.agent === "human" && (e.type === "approval" || e.type === "rejection")),
    [events],
  );
  const live = useMemo(() => liveStatus(runEvents), [runEvents]);
  const outcome: TicketOutcome | undefined =
    selected?.last_outcome && selected.last_outcome.run_id === runId ? selected.last_outcome.outcome : undefined;
  const finishedRecord = runEvents.find((e) => e.type === "run_finished");

  // --- actions
  const runTeam = async (id: number) => {
    setBusy(`run-${id}`);
    try {
      await api.run(id);
      setSelectedId(id);
      setView("live");
      wasRunning.current[id] = true;
      toast("ok", `The team is on ticket ${id}.`);
      await refresh();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const decide = async (requestId: number, approve: boolean) => {
    if (!approver.trim()) {
      toast("warn", "Type your name in “Approving as” first. Approvals are signed by a person.");
      return;
    }
    setBusy(`pay-${requestId}`);
    try {
      if (approve) {
        const r = await api.approve(requestId, approver.trim());
        toast("ok", `Paid ${money(r.amount as number)} to ${r.payee}. Checking is now ${money(r.new_balance as number)}.`);
      } else {
        await api.reject(requestId, approver.trim(), "Rejected on the board");
        toast("warn", `Request ${requestId} rejected. No money moved.`);
      }
      await Promise.all([refresh(), refreshEvents()]);
    } catch (e) {
      toast("error", (e as Error).message);
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    if (!window.confirm("Reset the shop to the original database? Payments, ticket updates and cash go back to the start. The audit trail is kept.")) return;
    setBusy("reset");
    try {
      const r = await api.reset();
      lastBalance.current = r.balance;
      setCashHistory([{ time: Date.now(), balance: r.balance, delta: 0, label: "Reset to opening balance" }]);
      toast("ok", `Shop reset. Checking is back to ${money(r.balance)}.`);
      setView("live");
      await Promise.all([refresh(), refreshEvents()]);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const pending = payments.requests.filter((r) => r.status === "pending");
  const decided = payments.requests.filter((r) => r.status !== "pending").slice().reverse();
  const resolvedCount = tickets.filter((t) => t.state === "resolved").length;

  return (
    <div className="desk">
      <Header today={today} cash={cash} flash={flash} history={cashHistory} onReset={reset} resetting={busy === "reset"} disabled={anyRunning} />

      {offline && (
        <div className="offline">
          Can’t reach the backend at <code>{API_BASE}</code>. Start it from <code>backend/</code> with{" "}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="layout">
        {/* ---------------- tickets */}
        <aside className="col tickets-col">
          <div className="col-head">
            <h2>Tickets</h2>
            <span className="muted">{resolvedCount} of {tickets.length} resolved</span>
          </div>
          <div className="progress"><span style={{ width: `${tickets.length ? (resolvedCount / tickets.length) * 100 : 0}%` }} /></div>
          {tickets.map((t) => (
            <TicketCard
              key={t.id}
              t={t}
              selected={t.id === selectedId}
              onSelect={() => setSelectedId(t.id)}
              onRun={() => runTeam(t.id)}
              disabled={anyRunning || busy !== null}
              pendingCount={pending.filter((p) => p.ticket_id === t.id).length}
            />
          ))}
        </aside>

        {/* ---------------- the agent floor */}
        <section className="col floor-col">
          {selected ? (
            <>
              <div className="ticket-banner">
                <div>
                  <div className="eyebrow">Ticket {selected.id} · {TYPE_LABEL[selected.type] ?? selected.type}</div>
                  <h1>{selected.subject}</h1>
                  <p className="quote">“{splitNotes(selected.notes).request}” <span className="muted">— {selected.requester}</span></p>
                  {splitNotes(selected.notes).desk.length > 0 && (
                    <ul className="desk-notes">
                      {splitNotes(selected.notes).desk.map((n, i) => <li key={i}>{n}</li>)}
                    </ul>
                  )}
                </div>
                <div className="tabs">
                  <button className={view === "live" ? "on" : ""} onClick={() => setView("live")}>Live</button>
                  <button className={view === "summary" ? "on" : ""} onClick={() => setView("summary")}>Summary</button>
                </div>
              </div>

              <div className="agents-row">
                {AGENTS.map((a) => (
                  <AgentTile key={a.id} id={a.id} live={live[a.id]} running={selected.running} />
                ))}
              </div>

              {view === "live" ? (
                <Timeline events={runEvents} running={selected.running} />
              ) : (
                <Summary events={runEvents} outcome={outcome} finished={finishedRecord} running={selected.running} />
              )}
            </>
          ) : (
            <div className="empty">Pick a ticket to begin.</div>
          )}
        </section>

        {/* ---------------- approvals + cash */}
        <aside className="col money-col">
          <div className="col-head">
            <h2>Approvals</h2>
            {pending.length > 0 && <span className="count">{pending.length}</span>}
          </div>
          <label className="approver">
            <span>Approving as</span>
            <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" />
          </label>
          {pending.length === 0 && <p className="muted small">Nothing is waiting. Agents can only prepare payments; a person approves them here.</p>}
          {pending.map((r) => {
            const after = (cash?.balance ?? 0) - r.amount;
            return (
              <div key={r.id} className={`pay-card ${r.ticket_id === selectedId ? "mine" : ""}`}>
                <div className="pay-top">
                  <span className={`kind k-${r.kind}`}>{r.kind.replace("_", " ")}</span>
                  <span className="muted small">#{r.id} · ticket {r.ticket_id ?? "—"}</span>
                </div>
                <div className="pay-amount">{money(r.amount)}</div>
                <div className="pay-payee">to {r.payee}</div>
                <p className="pay-reason">{r.reason}</p>
                <div className={`pay-after ${after < 0 ? "neg" : ""}`}>
                  Checking after: <b>{money(after)}</b>
                  {after < 0 && <span> · not enough cash, will be refused</span>}
                </div>
                <div className="muted small">Prepared by {agentName(r.prepared_by)}</div>
                <div className="pay-actions">
                  <button className="btn approve" disabled={busy !== null} onClick={() => decide(r.id, true)}>Approve &amp; pay</button>
                  <button className="btn ghost" disabled={busy !== null} onClick={() => decide(r.id, false)}>Reject</button>
                </div>
              </div>
            );
          })}

          {decided.length > 0 && (
            <>
              <h3 className="sub">Decided</h3>
              {decided.map((r) => (
                <div key={r.id} className={`decided d-${r.status}`}>
                  <span>{r.status}</span>
                  <b>{money(r.amount)}</b> {r.payee}
                  <div className="muted small">{r.decided_by}{r.decision_note ? ` · ${r.decision_note}` : ""}</div>
                </div>
              ))}
            </>
          )}

          <h3 className="sub">Cash ledger</h3>
          <Ledger history={cashHistory} />
          {humanEvents.length > 0 && (
            <p className="muted small">Every approval is written to the audit trail with the approver’s name.</p>
          )}
        </aside>
      </main>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ header + cash

function Header(props: {
  today: string; cash: CashInfo | null; flash: "down" | "up" | null; history: CashPoint[];
  onReset: () => void; resetting: boolean; disabled: boolean;
}) {
  const { today, cash, flash, history, onReset, resetting, disabled } = props;
  // ?shot=1 (screenshots) shows the balance at once instead of counting to it
  const shown = useTween(cash?.balance, new URLSearchParams(window.location.search).has("shot") ? 0 : 900);
  const last = history[history.length - 1];
  return (
    <header className="top">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <YaleY />
        </span>
        <BrandLockup />
        <div className="brand-divider" />
        <div>
          <div className="brand-name">Operations Desk</div>
          <div className="brand-sub">Multi-agent team · Chapel Street, New Haven</div>
        </div>
      </div>
      <div className="top-right">
        <div className="shop-date">
          <span>Shop date</span>
          <b>{prettyDate(today)}</b>
        </div>
        <div className={`cash ${flash ?? ""}`}>
          <span className="cash-label">Checking</span>
          <span className="cash-amount">{cash ? money(shown) : "—"}</span>
          <span className="cash-sub">
            {last && last.delta !== 0 ? (
              <em className={last.delta < 0 ? "neg" : "pos"}>{last.delta < 0 ? "−" : "+"}{money(Math.abs(last.delta))}</em>
            ) : null}
            {cash && cash.pending_requests_total > 0
              ? ` ${money(cash.pending_requests_total)} awaiting approval`
              : " nothing pending"}
          </span>
          <Sparkline points={history.map((h) => h.balance)} />
        </div>
        <button className="btn reset" onClick={onReset} disabled={resetting || disabled} title="Copy the original database over the working copy">
          {resetting ? "Resetting…" : "Reset shop"}
        </button>
      </div>
    </header>
  );
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <svg className="spark" viewBox="0 0 100 24" />;
  const max = Math.max(...points), min = Math.min(...points, 0);
  const span = max - min || 1;
  const xy = points.map((p, i) => `${(i / (points.length - 1)) * 100},${22 - ((p - min) / span) * 20}`);
  return (
    <svg className="spark" viewBox="0 0 100 24" preserveAspectRatio="none">
      <polyline points={xy.join(" ")} fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Ledger({ history }: { history: CashPoint[] }) {
  return (
    <ol className="ledger">
      {history.slice().reverse().map((h) => (
        <li key={h.time}>
          <span className="muted small">{new Date(h.time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</span>
          <span className="ledger-label">{h.label}</span>
          {h.delta !== 0 && <span className={h.delta < 0 ? "neg" : "pos"}>{h.delta < 0 ? "−" : "+"}{money(Math.abs(h.delta))}</span>}
          <b>{money(h.balance)}</b>
        </li>
      ))}
    </ol>
  );
}

// ------------------------------------------------------------------ tickets

function TicketCard(props: {
  t: Ticket; selected: boolean; onSelect: () => void; onRun: () => void; disabled: boolean; pendingCount: number;
}) {
  const { t, selected, onSelect, onRun, disabled, pendingCount } = props;
  const detail = t.sku
    ? `${t.sku} · size ${t.size} · qty ${t.qty}`
    : t.lease_id
      ? `Lease ${t.lease_id}`
      : t.invoice_id
        ? `Invoice ${t.invoice_id}`
        : "";
  const badge = t.running ? "running" : t.state;
  return (
    <div className={`ticket ${selected ? "selected" : ""} b-${badge}`} onClick={onSelect}>
      <div className="ticket-top">
        <span className="ticket-id">#{t.id}</span>
        <span className="type">{TYPE_LABEL[t.type] ?? t.type}</span>
      </div>
      <div className="ticket-subject">{t.subject}</div>
      <div className="ticket-req">{t.requester}</div>
      {detail && <div className="ticket-detail">{detail}{t.invoice_id && t.sku ? ` · invoice ${t.invoice_id}` : ""}</div>}
      <div className="ticket-foot">
        <span className={`badge ${badge}`}>
          {t.running ? "Agents working" : t.state === "resolved" ? "Resolved" : "Open"}
        </span>
        {!t.running && t.status !== "open" && t.status !== "resolved" && (
          <span className="status-detail">{STATUS_LABEL[t.status] ?? t.status}</span>
        )}
        {pendingCount > 0 && <span className="status-detail warn">{pendingCount} to approve</span>}
      </div>
      <button
        className="btn run"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          onRun();
        }}
      >
        {t.running ? "Ops Team working…" : t.state === "resolved" ? "Reactivate Ops Team" : "Activate Ops Team"}
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ agent floor

function AgentTile({ id, live, running }: { id: AgentName; live: { state: string; action: string; tools: number }; running: boolean }) {
  const a = AGENT_BY_ID[id];
  const state = !running && live.state === "idle" ? "idle" : live.state;
  return (
    <div className={`agent s-${state}`} style={{ ["--c" as string]: a.color }} title={`${a.person}, ${a.title}. ${a.role}.`}>
      <div className="agent-head">
        <Portrait agent={id} size={64} ring={a.color} />
        <div className="agent-id">
          <div className="agent-name">{a.person}</div>
          <div className="agent-subtitle">{a.name}</div>
          <div className="agent-title">{a.title}</div>
        </div>
      </div>
      <div className="agent-state">
        <span className="dot" />
        {state === "working" ? "Working" : state === "waiting" ? "Waiting" : state === "done" ? "Done" : state === "error" ? "Error" : "Idle"}
        {live.tools > 0 && <span className="tools-n">{live.tools} tool{live.tools === 1 ? "" : "s"}</span>}
      </div>
      <div className="agent-action" title={live.action}>{live.action}</div>
    </div>
  );
}

function Timeline({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [events.length, running]);
  const results = useMemo(() => {
    const m = new Map<string, AgentEvent>();
    for (const e of events) if (e.type === "tool_result" && e.tool_call_id) m.set(e.tool_call_id, e);
    return m;
  }, [events]);
  if (!events.length) {
    return <div className="empty">No run yet for this ticket. Press <b>Activate Ops Team</b> and watch the agents work here.</div>;
  }
  return (
    <div className="timeline">
      {events.map((e) => (
        <TimelineItem key={e.index} e={e} result={e.tool_call_id ? results.get(e.tool_call_id) : undefined} />
      ))}
      {running && (
        <div className="tl-item typing"><span /><span /><span /></div>
      )}
      <div ref={end} />
    </div>
  );
}

function Who({ id }: { id: string }) {
  const a = AGENT_BY_ID[id as AgentName];
  return (
    <span className="who" style={{ ["--c" as string]: a?.color ?? "#59636e" }}>
      {a ? <Portrait agent={a.id} size={24} ring={a.color} /> : <i>•</i>}
      {agentName(id)}
      {a && <small>{a.name}</small>}
    </span>
  );
}

function TimelineItem({ e, result }: { e: AgentEvent; result?: AgentEvent }) {
  const indent = { marginLeft: `${(e.depth ?? 0) * 22}px` };
  const time = <span className="tl-time">{clock(e.time)}</span>;
  switch (e.type) {
    case "run_started":
      return <div className="tl-item system">{time}<b>Ticket handed to the Boss.</b></div>;
    case "agent_started":
      return (
        <div className="tl-item start" style={indent}>{time}<Who id={e.agent} /> picked up the task</div>
      );
    case "delegation":
      return (
        <div className="tl-item delegation" style={indent}>
          {time}
          <div><Who id={e.agent} /> <span className="arrow">asks</span> <Who id={e.target ?? ""} /></div>
          <p className="task">{e.text}</p>
        </div>
      );
    case "tool_call":
      return (
        <div className="tl-item tool" style={indent}>
          {time}
          <Who id={e.agent} />
          <span className="tool-chip">{TOOL_LABELS[e.tool ?? ""] ?? e.tool}</span>
          <code className="tool-args">{e.tool}({argsText(e.args)})</code>
          {result?.text && (
            <details>
              <summary>result</summary>
              <pre>{pretty(result.text)}</pre>
            </details>
          )}
        </div>
      );
    case "model_step":
      if (!e.text) return null;
      return (
        <div className="tl-item says" style={indent}>
          {time}<Who id={e.agent} />
          <div className="bubble"><Markdown>{e.text}</Markdown></div>
        </div>
      );
    case "agent_finished": {
      const isOutcome = e.agent === "boss" && e.text?.trim().startsWith("{");
      return (
        <div className="tl-item finished" style={indent}>
          {time}<Who id={e.agent} /> {isOutcome ? "filed the final decision" : "reported back"}
          {!isOutcome && e.text && <div className="bubble answer"><Markdown>{e.text}</Markdown></div>}
        </div>
      );
    }
    case "run_finished":
      return (
        <div className="tl-item system done">
          {time}<b>Run finished.</b> {e.text}
          {e.usage && (
            <span className="usage">
              {e.usage.requests} model calls · {(e.usage.input_tokens + e.usage.output_tokens).toLocaleString()} tokens · {e.usage.tool_calls} tool calls · {e.usage.delegations} handoffs
            </span>
          )}
        </div>
      );
    case "delegation_refused":
    case "tool_blocked":
    case "error":
      return <div className="tl-item alert" style={indent}>{time}<Who id={e.agent} /> {e.type.replace("_", " ")}: {e.text}</div>;
    default:
      return null;
  }
}

/** The requester's words come first; lines the agents add with update_ticket look like "[date agent] note". */
function splitNotes(notes: string | null) {
  const lines = (notes ?? "").split("\n").map((l) => l.trim()).filter(Boolean);
  const isDesk = (l: string) => /^\[\d{4}-\d{2}-\d{2} [a-z_]+\]/.test(l);
  return { request: lines.filter((l) => !isDesk(l)).join(" "), desk: lines.filter(isDesk) };
}

function pretty(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

// ------------------------------------------------------------------ summary

function Summary({ events, outcome, finished, running }: {
  events: AgentEvent[]; outcome?: TicketOutcome; finished?: AgentEvent; running: boolean;
}) {
  const per = useMemo(() => summarize(events), [events]);
  if (!events.length) return <div className="empty">Run the team on this ticket to see what each agent did.</div>;
  return (
    <div className="summary">
      {running && <div className="note">The team is still working. This summary fills in as agents finish.</div>}
      {outcome && (
        <div className="outcome">
          <div className="outcome-head">
            <span className="eyebrow">Boss’s decision</span>
            <span className={`badge st-${outcome.status}`}>{STATUS_LABEL[outcome.status] ?? outcome.status}</span>
          </div>
          <p className="decision">{outcome.decision}</p>
          <p>{outcome.summary}</p>
          {outcome.open_questions.length > 0 && (
            <div className="questions">
              <b>For a human:</b>
              <ul>{outcome.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </div>
          )}
          {outcome.customer_drafts.map((d, i) => (
            <div key={i} className="draft">
              <div className="draft-head"><span className="eyebrow">Draft, not sent</span> To: {d.to}</div>
              <div className="draft-subject">{d.subject}</div>
              <div className="draft-body">{d.body}</div>
            </div>
          ))}
          {finished?.usage && (
            <div className="muted small">
              {finished.usage.requests} model calls · {(finished.usage.input_tokens + finished.usage.output_tokens).toLocaleString()} tokens · {finished.usage.tool_calls} tool calls · {finished.usage.delegations} handoffs
            </div>
          )}
        </div>
      )}
      <div className="per-agent">
        {per.map((s) => {
          const a = AGENT_BY_ID[s.agent];
          const isOutcome = s.agent === "boss" && s.answer?.trim().startsWith("{");
          return (
            <div key={s.agent} className="pa" style={{ ["--c" as string]: a.color }}>
              <div className="pa-head">
                <Portrait agent={s.agent} size={44} ring={a.color} />
                <div><b>{a.person}</b><div className="agent-subtitle">{a.name}</div></div>
              </div>
              <div className="pa-meta">
                {s.askedBy.length > 0 && <span>Asked by {[...new Set(s.askedBy)].join(", ")}</span>}
                {s.delegatedTo.length > 0 && <span>Asked {s.delegatedTo.join(", ")}</span>}
              </div>
              <div className="pa-tools">
                {Object.entries(s.tools).map(([t, n]) => (
                  <span key={t} className="tool-chip">{TOOL_LABELS[t] ?? t}{n > 1 ? ` ×${n}` : ""}</span>
                ))}
                {Object.keys(s.tools).length === 0 && <span className="muted small">No tools used</span>}
              </div>
              {s.answer && !isOutcome && <div className="pa-answer"><Markdown>{s.answer}</Markdown></div>}
              {isOutcome && outcome && <div className="pa-answer">{outcome.decision}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
