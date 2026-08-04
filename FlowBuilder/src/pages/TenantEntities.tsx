import { useEffect, useState } from "react";
import { Layers, Plus, Save, Trash2 } from "lucide-react";
import { api, ApiError } from "../api";
import type { Entity, TenantConfig } from "../types";

interface Props {
  tenantId: string;
}

function slugify(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export default function TenantEntities({ tenantId }: Props) {
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

  const patchEntity = (index: number, patch: Partial<Entity>) => {
    const entities = config.entities.map((e, i) => (i === index ? { ...e, ...patch } : e));
    setConfig({ ...config, entities });
  };

  const removeEntity = (index: number) => {
    setConfig({ ...config, entities: config.entities.filter((_, i) => i !== index) });
  };

  const addEntity = () => {
    let id = "entity";
    let n = 1;
    const ids = new Set(config.entities.map((e) => e.id));
    while (ids.has(id)) id = `entity_${n++}`;
    setConfig({ ...config, entities: [...config.entities, { id, type: "", label: "", aliases: [] }] });
  };

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

  const types = [...new Set(config.entities.map((e) => e.type).filter(Boolean))];

  return (
    <div className="page">
      <div className="page-header">
        <h2>Entities</h2>
        <div className="spacer" />
        {dirty && <span className="dirty-dot" title="Unsaved changes" />}
        <button type="button" className="primary" onClick={() => void save()} disabled={saving}>
          <Save size={14} />
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      <p className="muted" style={{ marginBottom: 20 }}>
        Selectable resources this tenant has - branches, doctors, class sessions. Give a collect field in the flow
        editor a matching "entity type" and its choices come from here automatically, kept in sync as you add or
        rename one. A connector's settings can also be scoped to a specific entity (its own calendar ID) from the
        Connectors tab.
      </p>

      {saveError && <p className="error">{saveError}</p>}

      <div className="settings-card">
        <div className="settings-card-header">
          <Layers size={15} />
          <h4>Entities</h4>
        </div>

        {config.entities.length === 0 && <p className="muted">No entities yet.</p>}

        {config.entities.map((entity, i) => (
          <div key={i} className="field-row-line connector-setting-row" style={{ alignItems: "flex-start" }}>
            <div>
              <label className="mini-label">Label</label>
              <input
                value={entity.label}
                placeholder="DHA Branch"
                onChange={(e) => {
                  const label = e.target.value;
                  const autoId = !entity.id || entity.id === slugify(entity.label);
                  patchEntity(i, { label, ...(autoId ? { id: slugify(label) } : {}) });
                }}
              />
            </div>
            <div>
              <label className="mini-label">Type</label>
              <input
                value={entity.type}
                placeholder="branch"
                list="entity-types"
                onChange={(e) => patchEntity(i, { type: e.target.value })}
              />
            </div>
            <div>
              <label className="mini-label">Id (stable - used by connectors)</label>
              <input value={entity.id} onChange={(e) => patchEntity(i, { id: e.target.value })} />
            </div>
            <div style={{ flex: 2 }}>
              <label className="mini-label">Aliases (comma separated, optional)</label>
              <input
                value={entity.aliases.join(", ")}
                placeholder="downtown, the DHA one"
                onChange={(e) =>
                  patchEntity(i, {
                    aliases: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  })
                }
              />
            </div>
            <button
              type="button"
              className="danger icon-only"
              title="Remove entity"
              style={{ marginTop: 20 }}
              onClick={() => removeEntity(i)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}

        <datalist id="entity-types">
          {types.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>

        <button type="button" className="link-button" onClick={addEntity}>
          <Plus size={12} />
          add entity
        </button>
      </div>
    </div>
  );
}
