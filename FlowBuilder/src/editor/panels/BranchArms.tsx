import { Plus, Trash2, X } from "lucide-react";
import type { Branch, Condition, ConditionOp } from "../../types";

const OPS: ConditionOp[] = ["eq", "ne", "in", "not_in", "exists", "not_exists", "contains"];

interface Props {
  branches: Branch[];
  nodeIds: string[];
  knownFields: string[];
  onChange: (branches: Branch[]) => void;
}

export default function BranchArms({ branches, nodeIds, knownFields, onChange }: Props) {
  const updateArm = (i: number, patch: Partial<Branch>) =>
    onChange(branches.map((b, idx) => (idx === i ? { ...b, ...patch } : b)));

  const removeArm = (i: number) => onChange(branches.filter((_, idx) => idx !== i));

  const addArm = () => onChange([...branches, { when: [], match: "all", goto: "" }]);

  const updateCondition = (armIdx: number, condIdx: number, patch: Partial<Condition>) => {
    const arm = branches[armIdx];
    const when = arm.when.map((c, idx) => (idx === condIdx ? { ...c, ...patch } : c));
    updateArm(armIdx, { when });
  };

  const addCondition = (armIdx: number) => {
    const arm = branches[armIdx];
    updateArm(armIdx, { when: [...arm.when, { field: knownFields[0] ?? "", op: "eq", value: "" }] });
  };

  const removeCondition = (armIdx: number, condIdx: number) => {
    const arm = branches[armIdx];
    updateArm(armIdx, { when: arm.when.filter((_, idx) => idx !== condIdx) });
  };

  return (
    <div className="panel-section">
      <div className="panel-section-header">
        <h4>Branch arms (evaluated in order)</h4>
        <button type="button" onClick={addArm}>
          <Plus size={14} />
          Add arm
        </button>
      </div>

      <datalist id="known-fields">
        {knownFields.map((f) => (
          <option key={f} value={f} />
        ))}
      </datalist>

      {branches.map((arm, i) => {
        const isFallback = arm.when.length === 0;
        return (
          <div key={i} className={`arm-row${isFallback ? " arm-fallback" : ""}`}>
            <div className="arm-row-header">
              <span className={`arm-badge${isFallback ? " arm-badge-fallback" : ""}`}>
                {isFallback ? "Fallback" : `Arm ${i + 1}`}
              </span>
              {isFallback && <span className="muted">always matches</span>}
              <div className="spacer" />
              <button type="button" className="danger icon-only" title="Remove arm" onClick={() => removeArm(i)}>
                <Trash2 size={13} />
              </button>
            </div>

            {!isFallback && (
              <div className="field-row-line">
                <span className="muted">match</span>
                <select value={arm.match} onChange={(e) => updateArm(i, { match: e.target.value as "all" | "any" })}>
                  <option value="all">all conditions</option>
                  <option value="any">any condition</option>
                </select>
              </div>
            )}

            {arm.when.length > 0 && (
              <div className="condition-columns">
                <span className="mini-label">Field</span>
                <span className="mini-label">Operator</span>
                <span className="mini-label">Value</span>
                <span />
              </div>
            )}

            {arm.when.map((c, ci) => (
              <div key={ci} className="field-row-line condition-row">
                <input
                  list="known-fields"
                  placeholder="field"
                  value={c.field}
                  onChange={(e) => updateCondition(i, ci, { field: e.target.value })}
                />
                <select value={c.op} onChange={(e) => updateCondition(i, ci, { op: e.target.value as ConditionOp })}>
                  {OPS.map((op) => (
                    <option key={op} value={op}>{op}</option>
                  ))}
                </select>
                {c.op !== "exists" && c.op !== "not_exists" ? (
                  <input
                    placeholder={c.op === "in" || c.op === "not_in" ? "comma,separated,values" : "value"}
                    value={
                      Array.isArray(c.value) ? c.value.join(", ") : (c.value as string | number | undefined) ?? ""
                    }
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (c.op === "in" || c.op === "not_in") {
                        updateCondition(i, ci, { value: raw.split(",").map((s) => s.trim()).filter(Boolean) });
                      } else {
                        updateCondition(i, ci, { value: raw });
                      }
                    }}
                  />
                ) : (
                  <span />
                )}
                <button
                  type="button"
                  className="danger icon-only"
                  title="Remove condition"
                  onClick={() => removeCondition(i, ci)}
                >
                  <X size={14} />
                </button>
              </div>
            ))}

            <button type="button" className="link-button" onClick={() => addCondition(i)}>
              <Plus size={12} />
              condition
            </button>

            <div className="field-row-line arm-goto-row">
              <span className="muted">goto</span>
              <select value={arm.goto} onChange={(e) => updateArm(i, { goto: e.target.value })}>
                <option value="">(choose target node)</option>
                {nodeIds.map((id) => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>
          </div>
        );
      })}

      {branches.length > 0 && !branches.some((b) => b.when.length === 0) && (
        <p className="warning">No fallback arm - this branch can dead-end if nothing matches.</p>
      )}
    </div>
  );
}
