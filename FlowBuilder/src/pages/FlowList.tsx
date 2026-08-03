import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { FlowConfig } from "../types";

interface Props {
  tenantId: string;
  onOpenFlow: (flowId: string) => void;
  onBack: () => void;
}

export default function FlowList({ tenantId, onOpenFlow, onBack }: Props) {
  const [flows, setFlows] = useState<FlowConfig[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newId, setNewId] = useState("");
  const [newTrigger, setNewTrigger] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    setError(null);
    api
      .listFlows(tenantId, true)
      .then((r) => setFlows(r.flows))
      .catch((e) => setError(e instanceof ApiError ? String(e.message) : "Failed to load flows"));
  };

  useEffect(load, [tenantId]);

  const createFlow = async () => {
    const flow_id = newId.trim();
    const trigger = newTrigger.trim();
    if (!flow_id || !trigger) return;
    setBusy(true);
    try {
      const flow: FlowConfig = {
        flow_id,
        tenant_id: tenantId,
        trigger,
        start: "start",
        nodes: { start: { type: "end", fields: [], branches: [], ui: { x: 40, y: 40 } } },
        active: true,
      };
      await api.saveFlow(flow_id, flow);
      onOpenFlow(flow_id);
    } catch (e) {
      alert(`Could not create flow: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (flow: FlowConfig) => {
    setBusy(true);
    try {
      await api.saveFlow(flow.flow_id, { ...flow, active: !flow.active });
      load();
    } catch (e) {
      alert(`Could not update flow: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (flow: FlowConfig) => {
    if (!confirm(`Delete flow "${flow.flow_id}"? This cannot be undone.`)) return;
    setBusy(true);
    try {
      await api.deleteFlow(flow.flow_id);
      load();
    } catch (e) {
      alert(`Could not delete flow: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <button type="button" onClick={onBack}>&larr; Tenants</button>
        <h2>{tenantId}</h2>
      </div>

      {error && <p className="error">{error}</p>}
      {!flows && !error && <p className="muted">Loading...</p>}

      {flows && (
        <table className="list-table">
          <thead>
            <tr>
              <th>Flow ID</th>
              <th>Trigger</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {flows.map((f) => (
              <tr key={f.flow_id} className={f.active ? "" : "inactive-row"}>
                <td>
                  <button type="button" className="link-button" onClick={() => onOpenFlow(f.flow_id)}>
                    {f.flow_id}
                  </button>
                </td>
                <td className="muted">{f.trigger}</td>
                <td>
                  <button type="button" disabled={busy} onClick={() => toggleActive(f)}>
                    {f.active ? "Active" : "Inactive"}
                  </button>
                </td>
                <td>
                  <button type="button" className="danger" disabled={busy} onClick={() => remove(f)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {flows.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">No flows yet for this tenant.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      <div className="panel-section">
        {!creating ? (
          <button type="button" onClick={() => setCreating(true)}>+ New flow</button>
        ) : (
          <div className="field-row-line">
            <input placeholder="flow_id (e.g. book_appointment)" value={newId} onChange={(e) => setNewId(e.target.value)} />
            <input placeholder="trigger - when this flow applies" value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)} />
            <button type="button" disabled={busy || !newId.trim() || !newTrigger.trim()} onClick={createFlow}>
              Create
            </button>
            <button type="button" onClick={() => setCreating(false)}>Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
