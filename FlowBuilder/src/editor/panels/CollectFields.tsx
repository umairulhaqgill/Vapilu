import { Plus, Trash2 } from "lucide-react";
import type { FieldFormat, FlowField } from "../../types";

const FORMATS: FieldFormat[] = ["phone", "email", "number", "date"];

interface Props {
  fields: FlowField[];
  confirm: string | null | undefined;
  onChange: (fields: FlowField[]) => void;
  onChangeConfirm: (confirm: string | null) => void;
}

export default function CollectFields({ fields, confirm, onChange, onChangeConfirm }: Props) {
  const update = (i: number, patch: Partial<FlowField>) => {
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  };
  const remove = (i: number) => onChange(fields.filter((_, idx) => idx !== i));
  const add = () =>
    onChange([...fields, { name: "", prompt: "", required: true, format: null, options: null, entity_type: null }]);

  return (
    <div className="panel-section">
      <div className="panel-section-header">
        <h4>Fields to collect</h4>
        <button type="button" onClick={add}>
          <Plus size={14} />
          Add field
        </button>
      </div>

      {fields.length === 0 && <p className="muted">No fields yet.</p>}

      {fields.map((f, i) => (
        <div key={i} className="field-card">
          <div className="field-card-header">
            <span className="field-card-index">{i + 1}</span>
            <input
              className="field-name-input"
              placeholder="field name (e.g. phone)"
              value={f.name}
              onChange={(e) => update(i, { name: e.target.value })}
            />
            <label className="checkbox">
              <input
                type="checkbox"
                checked={f.required}
                onChange={(e) => update(i, { required: e.target.checked })}
              />
              required
            </label>
            <button type="button" className="danger icon-only" title="Remove field" onClick={() => remove(i)}>
              <Trash2 size={14} />
            </button>
          </div>

          <label className="mini-label">Prompt (what to ask the caller for)</label>
          <input
            value={f.prompt}
            onChange={(e) => update(i, { prompt: e.target.value })}
          />

          <div className="field-row-line">
            <div>
              <label className="mini-label">Format</label>
              <select
                value={f.format ?? ""}
                onChange={(e) => update(i, { format: (e.target.value || null) as FieldFormat | null })}
              >
                <option value="">no format check</option>
                {FORMATS.map((fmt) => (
                  <option key={fmt} value={fmt}>{fmt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mini-label">Options (comma separated, optional)</label>
              <input
                disabled={!!f.entity_type}
                placeholder={f.entity_type ? "set by entity type below" : ""}
                value={f.options?.join(", ") ?? ""}
                onChange={(e) => {
                  const raw = e.target.value;
                  const options = raw.trim() ? raw.split(",").map((s) => s.trim()).filter(Boolean) : null;
                  update(i, { options });
                }}
              />
            </div>
            <div>
              <label className="mini-label">Entity type (dynamic options, optional)</label>
              <input
                placeholder="e.g. branch"
                value={f.entity_type ?? ""}
                onChange={(e) => {
                  const entity_type = e.target.value || null;
                  update(i, { entity_type, ...(entity_type ? { options: null } : {}) });
                }}
              />
            </div>
          </div>
          {f.entity_type && (
            <p className="muted" style={{ marginTop: 4 }}>
              Choices come from this tenant's "{f.entity_type}" entities (Entities tab) each call, instead of a
              fixed list.
            </p>
          )}
        </div>
      ))}

      <div className="panel-section-header">
        <h4>Confirm before continuing (optional)</h4>
      </div>
      <textarea
        placeholder="e.g. Booking you in for {preferred_day}. Have I got that right?"
        value={confirm ?? ""}
        onChange={(e) => onChangeConfirm(e.target.value || null)}
        rows={2}
      />
    </div>
  );
}
