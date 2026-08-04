// Separate client for the Connector Gateway (port 8005) - a different
// service from Tenant Config (api.ts), with its own token. Same runtime-
// hostname-default pattern as api.ts: see that file for why.

const BASE = import.meta.env.VITE_CONNECTOR_GATEWAY_URL ?? `http://${window.location.hostname}:8005`;
const TOKEN = import.meta.env.VITE_CONNECTOR_GATEWAY_TOKEN ?? "";

export class ConnectorApiError extends Error {
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
    throw new ConnectorApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// entityId omitted (or undefined) reads/writes the tenant-wide default
// config. Pass it to scope to one entity (a specific branch's calendar id)
// instead - see ConnectorGateway/connector_config_store.py.
function configPath(connectorId: string, tenantId: string, entityId?: string): string {
  const path = `/connectors/${encodeURIComponent(connectorId)}/tenants/${encodeURIComponent(tenantId)}/config`;
  return entityId ? `${path}?entity_id=${encodeURIComponent(entityId)}` : path;
}

export const connectorApi = {
  // connector_id -> operation names, e.g. {"booking": ["cancel_booking", "check_availability", "create_booking"]}
  listConnectors: () => request<Record<string, string[]>>("/connectors"),

  getConfig: (connectorId: string, tenantId: string, entityId?: string) =>
    request<{ config: Record<string, unknown> }>(configPath(connectorId, tenantId, entityId)),

  saveConfig: (connectorId: string, tenantId: string, config: Record<string, unknown>, entityId?: string) =>
    request<{ config: Record<string, unknown> }>(configPath(connectorId, tenantId, entityId), {
      method: "PUT",
      body: JSON.stringify({ config }),
    }),

  deleteConfig: (connectorId: string, tenantId: string, entityId?: string) =>
    request<{ deleted: boolean }>(configPath(connectorId, tenantId, entityId), { method: "DELETE" }),
};
