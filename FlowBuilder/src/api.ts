import type { FlowConfig, TenantConfig } from "./types";

// Falls back to whatever host the browser actually used to load this page
// (window.location.hostname), not a hardcoded default - a LAN IP set in
// .env drifts on every DHCP renewal (this broke once already), while
// "reuse the address that got us here" is correct whether that's
// localhost, 127.0.0.1, or a LAN IP, and never goes stale. Set
// VITE_TENANT_SERVICE_URL explicitly only if the API genuinely lives on a
// different host than this page does.
const BASE = import.meta.env.VITE_TENANT_SERVICE_URL ?? `http://${window.location.hostname}:8004`;
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

  getTenant: (tenantId: string) => request<TenantConfig>(`/tenants/${encodeURIComponent(tenantId)}`),

  saveTenant: (tenantId: string, config: TenantConfig) =>
    request<TenantConfig>(`/tenants/${encodeURIComponent(tenantId)}`, {
      method: "PUT",
      body: JSON.stringify(config),
    }),

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
