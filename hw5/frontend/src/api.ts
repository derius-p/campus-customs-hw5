// Every call the board makes goes to the FastAPI backend (Problem 7), which gets shop facts from the MCP server.
import type { CashInfo, EventsReply, PaymentsReply, TicketsReply } from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((body as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
  return body as T;
}

export const api = {
  tickets: () => call<TicketsReply>("/tickets"),
  run: (ticketId: number) => call<{ started: boolean; run_id: string }>(`/tickets/${ticketId}/run`, { method: "POST" }),
  events: (ticketId: number, limit = 1000) => call<EventsReply>(`/events?ticket_id=${ticketId}&limit=${limit}`),
  payments: () => call<PaymentsReply>("/payments"),
  approve: (requestId: number, approvedBy: string) =>
    call<Record<string, unknown>>(`/payments/${requestId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (requestId: number, rejectedBy: string, note: string) =>
    call<Record<string, unknown>>(`/payments/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ approved_by: rejectedBy, note }),
    }),
  cash: () => call<CashInfo>("/cash"),
  reset: () => call<{ reset: boolean; balance: number }>("/reset", { method: "POST" }),
};
