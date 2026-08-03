import { useEffect, useState } from "react";
import { Building2, Clock, PlugZap, Save } from "lucide-react";
import { api, ApiError } from "../api";
import type { BusinessHours, TenantConfig } from "../types";

const DAYS: { key: keyof BusinessHours; label: string }[] = [
  { key: "monday", label: "Mon" },
  { key: "tuesday", label: "Tue" },
  { key: "wednesday", label: "Wed" },
  { key: "thursday", label: "Thu" },
  { key: "friday", label: "Fri" },
  { key: "saturday", label: "Sat" },
  { key: "sunday", label: "Sun" },
];
const DEFAULT_HOURS = "09:00-17:00";

interface Props {
  tenantId: string;
}

function splitList(raw: string): string[] {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

export default function TenantSettings({ tenantId }: Props) {
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [savedJson, setSavedJson] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api
      .getTenant(tenantId)
      .then((c) => {
        if (cancelled) return;
        setConfig(c);
        setSavedJson(JSON.stringify(c));
      })
      .catch((e) => !cancelled && setLoadError(e instanceof ApiError ? String(e.message) : "Failed to load tenant"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  if (loading) return <p className="muted panel-section">Loading...</p>;
  if (loadError) return <p className="error panel-section">{loadError}</p>;
  if (!config) return null;

  const dirty = JSON.stringify(config) !== savedJson;
  const patch = (p: Partial<TenantConfig>) => setConfig({ ...config, ...p });
  const patchHours = (p: Partial<BusinessHours>) => setConfig({ ...config, business_hours: { ...config.business_hours, ...p } });

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await api.saveTenant(tenantId, config);
      setConfig(saved);
      setSavedJson(JSON.stringify(saved));
    } catch (e) {
      setSaveError(e instanceof ApiError ? String(e.message) : e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Settings</h2>
        <div className="spacer" />
        {dirty && <span className="dirty-dot" title="Unsaved changes" />}
        <button type="button" className="primary" onClick={() => void save()} disabled={saving}>
          <Save size={14} />
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {saveError && <p className="error">{saveError}</p>}

      <div className="settings-card">
        <div className="settings-card-header">
          <Building2 size={15} />
          <h4>Business info</h4>
        </div>

        <label className="mini-label">Business name</label>
        <input value={config.business_name} onChange={(e) => patch({ business_name: e.target.value })} />

        <label className="mini-label">Greeting (spoken at the start of every call)</label>
        <textarea rows={2} value={config.greeting} onChange={(e) => patch({ greeting: e.target.value })} />

        <label className="mini-label">System prompt extra (business context, services, policies)</label>
        <textarea
          rows={5}
          value={config.system_prompt_extra}
          onChange={(e) => patch({ system_prompt_extra: e.target.value })}
        />

        <div className="field-row-line">
          <div>
            <label className="mini-label">Language</label>
            <input value={config.language} onChange={(e) => patch({ language: e.target.value })} />
          </div>
          <div>
            <label className="mini-label">Voice (Piper model filename, blank for default)</label>
            <input value={config.voice ?? ""} onChange={(e) => patch({ voice: e.target.value || null })} />
          </div>
        </div>

        <label className="mini-label">Escalation phone (blank = no human handoff)</label>
        <input
          value={config.escalation_phone ?? ""}
          onChange={(e) => patch({ escalation_phone: e.target.value || null })}
        />

        <label className="checkbox" style={{ marginTop: 12 }}>
          <input type="checkbox" checked={config.active} onChange={(e) => patch({ active: e.target.checked })} />
          Active
        </label>
      </div>

      <div className="settings-card">
        <div className="settings-card-header">
          <Clock size={15} />
          <h4>Business hours</h4>
        </div>

        <div className="hours-grid">
          {DAYS.map(({ key, label }) => {
            const value = config.business_hours[key] ?? null;
            const isOpen = value !== null;
            return (
              <div key={key} className="hours-row">
                <span className="hours-day">{label}</span>
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={isOpen}
                    onChange={(e) => patchHours({ [key]: e.target.checked ? DEFAULT_HOURS : null })}
                  />
                  <span className="switch-track">
                    <span className="switch-thumb" />
                  </span>
                </label>
                {isOpen ? (
                  <input
                    className="hours-input"
                    placeholder="09:00-17:00"
                    value={value}
                    onChange={(e) => patchHours({ [key]: e.target.value })}
                  />
                ) : (
                  <span className="muted hours-closed">Closed</span>
                )}
              </div>
            );
          })}
        </div>

        <label className="mini-label">Timezone</label>
        <input
          value={config.business_hours.timezone}
          onChange={(e) => patchHours({ timezone: e.target.value })}
        />
      </div>

      <div className="settings-card">
        <div className="settings-card-header">
          <PlugZap size={15} />
          <h4>Capabilities &amp; integrations</h4>
        </div>

        <label className="mini-label">Capabilities (comma separated - fed to the LLM so it knows its own scope)</label>
        <input
          value={config.capabilities.join(", ")}
          onChange={(e) => patch({ capabilities: splitList(e.target.value) })}
        />

        <label className="mini-label">Enabled connectors (comma separated)</label>
        <input
          value={config.enabled_connectors.join(", ")}
          onChange={(e) => patch({ enabled_connectors: splitList(e.target.value) })}
        />
      </div>
    </div>
  );
}
