import { useState } from "react";
import { Eye, EyeOff, Plus, Trash2 } from "lucide-react";

function isSensitiveKey(key: string): boolean {
  return /key|token|secret|password|credential/i.test(key);
}

interface Props {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}

export default function ConnectorSettingsForm({ config, onChange }: Props) {
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const entries = Object.entries(config);

  const toggleReveal = (key: string) => {
    setRevealed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renameKey = (oldKey: string, newKey: string) => {
    const next: Record<string, unknown> = {};
    for (const [k, v] of entries) next[k === oldKey ? newKey : k] = v;
    onChange(next);
  };

  const setValue = (key: string, value: string) => onChange({ ...config, [key]: value });

  const remove = (key: string) => {
    const next = { ...config };
    delete next[key];
    onChange(next);
  };

  const add = () => {
    let name = "setting";
    let i = 1;
    while (name in config) name = `setting_${i++}`;
    onChange({ ...config, [name]: "" });
  };

  return (
    <div>
      {entries.length === 0 && <p className="muted">No settings configured yet.</p>}

      {entries.map(([key, value]) => {
        const sensitive = isSensitiveKey(key);
        const show = revealed.has(key);
        return (
          <div key={key} className="field-row-line connector-setting-row">
            <input value={key} onChange={(e) => renameKey(key, e.target.value)} placeholder="setting name" />
            <input
              type={sensitive && !show ? "password" : "text"}
              value={typeof value === "string" ? value : JSON.stringify(value)}
              onChange={(e) => setValue(key, e.target.value)}
              placeholder="value"
            />
            {sensitive && (
              <button
                type="button"
                className="icon-only"
                title={show ? "Hide value" : "Reveal value"}
                onClick={() => toggleReveal(key)}
              >
                {show ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            )}
            <button type="button" className="danger icon-only" title="Remove setting" onClick={() => remove(key)}>
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}

      <button type="button" className="link-button" onClick={add}>
        <Plus size={12} />
        add setting
      </button>
    </div>
  );
}
