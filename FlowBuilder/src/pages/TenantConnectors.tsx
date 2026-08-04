import { useEffect, useState } from "react";
import { Plug, Save } from "lucide-react";
import { api, ApiError } from "../api";
import { connectorApi, ConnectorApiError } from "../connectorApi";
import type { TenantConfig } from "../types";
import ConnectorSettingsForm from "./ConnectorSettingsForm";

interface Props {
  tenantId: string;
}

// Scope key for the tenant-wide default config (no entity_id). Distinct
// from any real entity id since entity ids are author-chosen strings.
const DEFAULT_SCOPE = "__default__";

// Config cache key - one entry per (connector, scope) pair so switching
// which branch/doctor you're configuring doesn't need a re-fetch every time.
function cacheKey(connectorId: string, scope: string): string {
  return `${connectorId}::${scope}`;
}

export default function TenantConnectors({ tenantId }: Props) {
  const [connectors, setConnectors] = useState<Record<string, string[]> | null>(null);
  const [tenant, setTenant] = useState<TenantConfig | null>(null);
  const [configs, setConfigs] = useState<Record<string, Record<string, unknown>>>({});
  const [scopeByConnector, setScopeByConnector] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busyConnector, setBusyConnector] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    Promise.all([connectorApi.listConnectors(), api.getTenant(tenantId)])
      .then(([conns, t]) => {
        if (cancelled) return;
        setConnectors(conns);
        setTenant(t);
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError(e instanceof ApiError || e instanceof ConnectorApiError ? String(e.message) : "Failed to load");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  // Lazily load each enabled connector's stored config for whichever scope
  // (tenant-wide default, or one entity) is currently selected for it - no
  // point fetching config for a connector the tenant hasn't turned on, or
  // for a scope nobody's looking at.
  useEffect(() => {
    if (!tenant || !connectors) return;
    for (const id of tenant.enabled_connectors) {
      if (!(id in connectors)) continue;
      const scope = scopeByConnector[id] ?? DEFAULT_SCOPE;
      const key = cacheKey(id, scope);
      if (key in configs) continue;
      connectorApi.getConfig(id, tenantId, scope === DEFAULT_SCOPE ? undefined : scope).then((r) => {
        setConfigs((prev) => ({ ...prev, [key]: r.config }));
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant, connectors, scopeByConnector]);

  if (loading) return <p className="muted panel-section">Loading...</p>;
  if (loadError) return <p className="error panel-section">{loadError}</p>;
  if (!tenant || !connectors) return null;

  const toggleEnabled = async (connectorId: string, enabled: boolean) => {
    setBusyConnector(connectorId);
    try {
      const nextEnabled = enabled
        ? [...tenant.enabled_connectors, connectorId]
        : tenant.enabled_connectors.filter((id) => id !== connectorId);
      const saved = await api.saveTenant(tenantId, { ...tenant, enabled_connectors: nextEnabled });
      setTenant(saved);
    } catch (e) {
      alert(`Could not update: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusyConnector(null);
    }
  };

  const saveConnectorConfig = async (connectorId: string) => {
    const scope = scopeByConnector[connectorId] ?? DEFAULT_SCOPE;
    const key = cacheKey(connectorId, scope);
    setBusyConnector(connectorId);
    try {
      const saved = await connectorApi.saveConfig(
        connectorId,
        tenantId,
        configs[key] ?? {},
        scope === DEFAULT_SCOPE ? undefined : scope
      );
      setConfigs((prev) => ({ ...prev, [key]: saved.config }));
      setSavedAt((prev) => ({ ...prev, [key]: Date.now() }));
    } catch (e) {
      alert(`Could not save connector settings: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusyConnector(null);
    }
  };

  const connectorIds = Object.keys(connectors);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Connectors</h2>
      </div>
      <p className="muted" style={{ marginBottom: 20 }}>
        Enable a connector for this tenant, then configure the settings it needs (an API key, a calendar ID, ...).
        Settings are stored per tenant in the Connector Gateway, not here - see ConnectorGateway/README.md.
      </p>

      {connectorIds.length === 0 && <p className="muted">No connectors registered on the Gateway.</p>}

      {connectorIds.map((connectorId) => {
        const enabled = tenant.enabled_connectors.includes(connectorId);
        const busy = busyConnector === connectorId;
        const scope = scopeByConnector[connectorId] ?? DEFAULT_SCOPE;
        const key = cacheKey(connectorId, scope);
        return (
          <div key={connectorId} className="settings-card">
            <div className="settings-card-header">
              <Plug size={15} />
              <h4>{connectorId}</h4>
              <div className="spacer" />
              <label className="switch">
                <input
                  type="checkbox"
                  checked={enabled}
                  disabled={busy}
                  onChange={(e) => void toggleEnabled(connectorId, e.target.checked)}
                />
                <span className="switch-track">
                  <span className="switch-thumb" />
                </span>
              </label>
            </div>

            <p className="muted">Operations: {connectors[connectorId].join(", ")}</p>

            {enabled && (
              <div className="connector-settings-body">
                {tenant.entities.length > 0 && (
                  <>
                    <label className="mini-label">Scope</label>
                    <select
                      value={scope}
                      onChange={(e) => setScopeByConnector((prev) => ({ ...prev, [connectorId]: e.target.value }))}
                    >
                      <option value={DEFAULT_SCOPE}>Default (tenant-wide)</option>
                      {tenant.entities.map((entity) => (
                        <option key={entity.id} value={entity.id}>
                          {entity.label} ({entity.type})
                        </option>
                      ))}
                    </select>
                    <p className="muted" style={{ marginTop: 4 }}>
                      {scope === DEFAULT_SCOPE
                        ? "Shared settings, used unless an entity below overrides them."
                        : "Overrides the default settings for this one entity only - e.g. its own calendar ID."}
                    </p>
                  </>
                )}

                <label className="mini-label">Settings</label>
                <ConnectorSettingsForm
                  config={configs[key] ?? {}}
                  onChange={(c) => setConfigs((prev) => ({ ...prev, [key]: c }))}
                />
                <div className="field-row-line" style={{ marginTop: 10 }}>
                  <button type="button" className="primary" disabled={busy} onClick={() => void saveConnectorConfig(connectorId)}>
                    <Save size={14} />
                    {busy ? "Saving..." : "Save settings"}
                  </button>
                  {savedAt[key] && <span className="muted">Saved</span>}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
