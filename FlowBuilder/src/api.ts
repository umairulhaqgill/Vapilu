import type { FlowConfig } from "./types";

const BASE = import.meta.env.VITE_TENANT_SERVICE_URL ?? "http://localhost:8004";
const TOKEN = import.meta.env.VITE_TENANT_SERVICE_TOKEN ?? "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function withToken(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
  return `${BASE}${path}${TOKEN ? `${sep}token=${encodeURIComponent(TOKEN)}` : ""}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(withToken(path), {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listTenants: () => request<{ tenant_ids: string[] }>("/tenants"),

  listFlows: (tenantId: string, includeInactive = true) =>
    request<{ flows: FlowConfig[] }>(
      `/tenants/${encodeURIComponent(tenantId)}/flows?include_inactive=${includeInactive}`
    ),

  getFlow: (flowId: string) => request<FlowConfig>(`/flows/${encodeURIComponent(flowId)}`),

  saveFlow: (flowId: string, flow: FlowConfig) =>
    request<FlowConfig>(`/flows/${encodeURIComponent(flowId)}`, {
      method: "PUT",
      body: JSON.stringify(flow),
    }),

  deleteFlow: (flowId: string) =>
    request<{ deleted: string }>(`/flows/${encodeURIComponent(flowId)}`, { method: "DELETE" }),
};
