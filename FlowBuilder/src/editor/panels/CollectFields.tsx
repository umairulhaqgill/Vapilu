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
    onChange([...fields, { name: "", prompt: "", required: true, format: null, options: null }]);

  return (
    <div className="panel-section">
      <div className="panel-section-header">
        <h4>Fields to collect</h4>
        <button type="button" onClick={add}>+ Add field</button>
      </div>

      {fields.length === 0 && <p className="muted">No fields yet.</p>}

      {fields.map((f, i) => (
        <div key={i} className="field-row">
          <div className="field-row-line">
            <input
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
            <button type="button" className="danger" onClick={() => remove(i)}>Remove</button>
          </div>
          <input
            placeholder="prompt - what to ask the caller for"
            value={f.prompt}
            onChange={(e) => update(i, { prompt: e.target.value })}
          />
          <div className="field-row-line">
            <select
              value={f.format ?? ""}
              onChange={(e) => update(i, { format: (e.target.value || null) as FieldFormat | null })}
            >
              <option value="">no format check</option>
              {FORMATS.map((fmt) => (
                <option key={fmt} value={fmt}>{fmt}</option>
              ))}
            </select>
            <input
              placeholder="options, comma separated (optional)"
              value={f.options?.join(", ") ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                const options = raw.trim() ? raw.split(",").map((s) => s.trim()).filter(Boolean) : null;
                update(i, { options });
              }}
            />
          </div>
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
