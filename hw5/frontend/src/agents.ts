// Agent identities and helpers that turn the raw event stream into "who is doing what".
import type { AgentEvent, AgentName } from "./types";

// Each agent is played by the Yale officer whose job best matches it (Yale officers list, 2026–27).
export const AGENTS: {
  id: AgentName; name: string; person: string; title: string; role: string; glyph: string; color: string;
}[] = [
  { id: "boss", name: "Boss", person: "Maurie McInnis", title: "President",
    role: "Reads tickets, routes work, decides", glyph: "★", color: "#00356b" },
  { id: "inventory", name: "Inventory", person: "Geoffrey Chatas", title: "Senior Vice President for Operations",
    role: "Stock, shortfalls, restock", glyph: "▦", color: "#2f7d6d" },
  { id: "accounting", name: "Accounting", person: "Katrina Spencer", title: "Vice President for Finance, CFO & Treasurer",
    role: "Cash, invoices, margins, payments", glyph: "$", color: "#a8742a" },
  { id: "facilities", name: "Facilities", person: "Mike Bellamy", title: "Vice President for Facilities, Campus Development & Sustainability",
    role: "Lease, rent, landlord", glyph: "⌂", color: "#6a4c93" },
  { id: "customer_service", name: "Customer Service", person: "Renee Kopkowski", title: "Vice President for Communications",
    role: "Drafts replies to requesters", glyph: "✉", color: "#b5485d" },
];

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<AgentName, (typeof AGENTS)[number]>;

/** The person playing the agent (e.g. "Katrina Spencer"); roleName gives the job ("Accounting"). */
export const agentName = (id: string | undefined) =>
  id && id in AGENT_BY_ID ? AGENT_BY_ID[id as AgentName].person : id === "human" ? "Human" : id === "system" ? "Desk" : id ?? "";

export const roleName = (id: string | undefined) =>
  id && id in AGENT_BY_ID ? AGENT_BY_ID[id as AgentName].name : agentName(id);

export const TOOL_LABELS: Record<string, string> = {
  get_desk: "Check shop date",
  list_tickets: "List tickets",
  get_ticket: "Read ticket",
  check_stock: "Check stock",
  check_margin: "Check margin",
  list_vendors: "List vendors",
  check_vendor_invoices: "Vendor invoices",
  get_invoice: "Read invoice",
  get_lease: "Read lease",
  get_cash_balance: "Cash balance",
  list_payments: "List payments",
  prepare_payment: "Prepare payment",
  update_ticket: "Update ticket",
};

export type AgentLive = {
  state: "idle" | "working" | "waiting" | "done" | "error";
  action: string;
  tools: number;
};

/** The latest run in a list of events for one ticket (by run_started order). */
export function latestRunId(events: AgentEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) if (events[i].type === "run_started") return events[i].run_id;
  return null;
}

export function argsText(args: Record<string, unknown> | undefined): string {
  if (!args) return "";
  return Object.entries(args)
    .filter(([k, v]) => v !== "" && v !== 0 && v !== null && k !== "prepared_by" && k !== "updated_by" && k !== "reason" && k !== "note")
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

/** What each agent is doing right now (or did last) in this run. */
export function liveStatus(events: AgentEvent[]): Record<AgentName, AgentLive> {
  const live = Object.fromEntries(
    AGENTS.map((a) => [a.id, { state: "idle", action: "Waiting for work", tools: 0 } as AgentLive]),
  ) as Record<AgentName, AgentLive>;
  const open: Record<string, number> = {};
  for (const e of events) {
    const a = e.agent as AgentName;
    if (!(a in live)) continue;
    const s = live[a];
    switch (e.type) {
      case "agent_started":
        open[a] = (open[a] ?? 0) + 1;
        s.state = "working";
        s.action = "Reading the task";
        break;
      case "model_step":
        if (s.state !== "done") s.action = e.text ? "Thinking it over" : "Deciding next step";
        break;
      case "tool_call":
        s.tools += 1;
        s.state = "working";
        s.action = `${TOOL_LABELS[e.tool ?? ""] ?? e.tool} · ${argsText(e.args)}`.replace(/ · $/, "");
        break;
      case "delegation":
        s.state = "waiting";
        s.action = `Waiting on ${agentName(e.target)}`;
        break;
      case "agent_finished":
        open[a] = Math.max(0, (open[a] ?? 1) - 1);
        if (!open[a]) {
          s.state = "done";
          s.action = "Finished and reported back";
        }
        for (const other of Object.values(live)) if (other.state === "waiting" && other.action === `Waiting on ${agentName(a)}`) {
          other.state = "working";
          other.action = `Reading ${agentName(a)}'s answer`;
        }
        break;
      case "error":
        s.state = "error";
        s.action = e.text ?? "Error";
        break;
    }
  }
  return live;
}

export type AgentSummary = {
  agent: AgentName;
  tasks: string[];
  askedBy: string[];
  delegatedTo: string[];
  tools: Record<string, number>;
  answer: string | null;
};

/** A short "what did each agent do" summary for a finished run. */
export function summarize(events: AgentEvent[]): AgentSummary[] {
  const out = new Map<AgentName, AgentSummary>();
  const get = (a: AgentName) => {
    if (!out.has(a)) out.set(a, { agent: a, tasks: [], askedBy: [], delegatedTo: [], tools: {}, answer: null });
    return out.get(a)!;
  };
  for (const e of events) {
    const a = e.agent as AgentName;
    if (!(a in AGENT_BY_ID)) continue;
    const s = get(a);
    if (e.type === "agent_started" && e.text) {
      s.tasks.push(e.text);
      const chain = e.chain ?? [];
      if (chain.length > 1) s.askedBy.push(agentName(chain[chain.length - 2]));
    }
    if (e.type === "delegation" && e.target) s.delegatedTo.push(agentName(e.target));
    if (e.type === "tool_call" && e.tool) s.tools[e.tool] = (s.tools[e.tool] ?? 0) + 1;
    if (e.type === "agent_finished" && e.text) s.answer = e.text;
  }
  return AGENTS.map((a) => out.get(a.id)).filter((x): x is AgentSummary => !!x);
}

export const money = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export const prettyDate = (iso: string | null | undefined) => {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
};

export const clock = (iso: string) => new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
