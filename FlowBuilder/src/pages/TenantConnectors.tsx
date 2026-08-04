import { useEffect, useState } from "react";
import { Plug, Save } from "lucide-react";
import { api, ApiError } from "../api";
import { connectorApi, ConnectorApiError } from "../connectorApi";
import type { TenantConfig } from "../types";
import ConnectorSettingsForm from "./ConnectorSettingsForm";

interface Props {
  tenantId: string;
}

export default function TenantConnectors({ tenantId }: Props) {
  const [connectors, setConnectors] = useState<Record<string, string[]> | null>(null);
  const [tenant, setTenant] = useState<TenantConfig | null>(null);
  const [configs, setConfigs] = useState<Record<string, Record<string, unknown>>>({});
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

  // Lazily load each enabled connector's stored config once we know what's
  // registered and what's enabled - no point fetching config for a
  // connector the tenant hasn't turned on.
  useEffect(() => {
    if (!tenant || !connectors) return;
    for (const id of tenant.enabled_connectors) {
      if (id in connectors && !(id in configs)) {
        connectorApi.getConfig(id, tenantId).then((r) => {
          setConfigs((prev) => ({ ...prev, [id]: r.config }));
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant, connectors]);

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
    setBusyConnector(connectorId);
    try {
      const saved = await connectorApi.saveConfig(connectorId, tenantId, configs[connectorId] ?? {});
      setConfigs((prev) => ({ ...prev, [connectorId]: saved.config }));
      setSavedAt((prev) => ({ ...prev, [connectorId]: Date.now() }));
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
                <label className="mini-label">Settings</label>
                <ConnectorSettingsForm
                  config={configs[connectorId] ?? {}}
                  onChange={(c) => setConfigs((prev) => ({ ...prev, [connectorId]: c }))}
                />
                <div className="field-row-line" style={{ marginTop: 10 }}>
                  <button type="button" className="primary" disabled={busy} onClick={() => void saveConnectorConfig(connectorId)}>
                    <Save size={14} />
                    {busy ? "Saving..." : "Save settings"}
                  </button>
                  {savedAt[connectorId] && <span className="muted">Saved</span>}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
