import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { BusinessHours, TenantConfig } from "../types";

const DAYS: (keyof BusinessHours)[] = [
  "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
];

interface Props {
  tenantId: string;
  onBack: () => void;
}

function splitList(raw: string): string[] {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

export default function TenantSettings({ tenantId, onBack }: Props) {
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
        <button type="button" onClick={onBack}>&larr; Flows</button>
        <h2>{tenantId} - Settings</h2>
        <div className="spacer" />
        {dirty && <span className="dirty-dot" title="Unsaved changes" />}
        <button type="button" onClick={() => void save()} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {saveError && <p className="error">{saveError}</p>}

      <div className="panel-section">
        <label>Business name</label>
        <input value={config.business_name} onChange={(e) => patch({ business_name: e.target.value })} />

        <label>Greeting (spoken at the start of every call)</label>
        <textarea rows={2} value={config.greeting} onChange={(e) => patch({ greeting: e.target.value })} />

        <label>System prompt extra (business context, services, policies)</label>
        <textarea
          rows={5}
          value={config.system_prompt_extra}
          onChange={(e) => patch({ system_prompt_extra: e.target.value })}
        />

        <div className="field-row-line">
          <div>
            <label>Language</label>
            <input value={config.language} onChange={(e) => patch({ language: e.target.value })} />
          </div>
          <div>
            <label>Voice (Piper model filename, blank for default)</label>
            <input value={config.voice ?? ""} onChange={(e) => patch({ voice: e.target.value || null })} />
          </div>
        </div>

        <label>Escalation phone (blank = no human handoff)</label>
        <input
          value={config.escalation_phone ?? ""}
          onChange={(e) => patch({ escalation_phone: e.target.value || null })}
        />

        <label className="checkbox" style={{ marginTop: 10 }}>
          <input type="checkbox" checked={config.active} onChange={(e) => patch({ active: e.target.checked })} />
          Active
        </label>
      </div>

      <div className="panel-section">
        <div className="panel-section-header">
          <h4>Business hours</h4>
        </div>
        {DAYS.map((day) => (
          <div key={day} className="field-row-line">
            <span className="muted" style={{ width: 90, flex: "0 0 auto", textTransform: "capitalize" }}>{day}</span>
            <input
              placeholder="09:00-17:00 (blank = closed)"
              value={config.business_hours[day] ?? ""}
              onChange={(e) => patchHours({ [day]: e.target.value || null })}
            />
          </div>
        ))}
        <label>Timezone</label>
        <input
          value={config.business_hours.timezone}
          onChange={(e) => patchHours({ timezone: e.target.value })}
        />
      </div>

      <div className="panel-section">
        <label>Capabilities (comma separated - fed to the LLM so it knows its own scope)</label>
        <input
          value={config.capabilities.join(", ")}
          onChange={(e) => patch({ capabilities: splitList(e.target.value) })}
        />

        <label>Enabled connectors (comma separated)</label>
        <input
          value={config.enabled_connectors.join(", ")}
          onChange={(e) => patch({ enabled_connectors: splitList(e.target.value) })}
        />
      </div>
    </div>
  );
}
