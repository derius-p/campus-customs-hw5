// Shapes of what the backend returns (see backend/main.py and backend/models.py).

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface PaymentRequestOut {
  request_id?: number | null;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  payee: string;
  amount: number;
  reason: string;
}

export interface CustomerDraft {
  to: string;
  subject: string;
  body: string;
}

export interface TicketOutcome {
  ticket_id: number;
  decision: string;
  summary: string;
  agents_consulted: AgentName[];
  payments_requested: PaymentRequestOut[];
  customer_drafts: CustomerDraft[];
  open_questions: string[];
  status: "resolved" | "waiting_on_approval" | "needs_human";
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  state: "open" | "resolved";
  running: boolean;
  run_id: string | null;
  last_outcome: { run_id: string; time: string; decision: string; outcome?: TicketOutcome } | null;
}

export interface TicketsReply {
  today: string;
  tickets: Ticket[];
}

export interface AgentEvent {
  index: number;
  run_id: string;
  ticket_id: number | null;
  time: string;
  type:
    | "run_started" | "agent_started" | "model_step" | "delegation" | "delegation_refused"
    | "tool_call" | "tool_result" | "tool_blocked" | "agent_finished" | "run_finished"
    | "approval" | "rejection" | "reset" | "error";
  agent: AgentName | "human" | "system";
  chain?: string[];
  depth?: number;
  step?: number;
  model?: string;
  target?: AgentName;
  tool?: string;
  tool_call_id?: string;
  args?: Record<string, unknown>;
  text?: string;
  usage?: Record<string, number>;
}

export interface EventsReply {
  next_since: number;
  running: Record<string, string>;
  events: AgentEvent[];
}

export interface PaymentRow {
  id: number;
  ticket_id: number | null;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number;
  payee: string;
  amount: number;
  sku: string | null;
  size: string | null;
  qty: number | null;
  reason: string;
  prepared_by: string;
  status: "pending" | "approved" | "rejected" | "refused";
  created_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  payment_id: number | null;
}

export interface PaymentMade {
  id: number;
  kind: string;
  ref_id: number;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
}

export interface PaymentsReply {
  requests: PaymentRow[];
  payments_made: PaymentMade[];
}

export interface CashInfo {
  name: string;
  balance: number;
  date: string;
  pending_requests_total: number;
  balance_after_pending: number;
}
