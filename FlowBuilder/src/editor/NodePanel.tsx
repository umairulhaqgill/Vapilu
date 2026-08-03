import { useState } from "react";
import { Flag, Trash2 } from "lucide-react";
import type { FlowConfig, FlowNode } from "../types";
import { deleteNode, graphFields, patchNode, renameNode } from "./flowOps";
import { NODE_TYPE_META } from "./nodeTypeMeta";
import CollectFields from "./panels/CollectFields";
import BranchArms from "./panels/BranchArms";

interface Props {
  flow: FlowConfig;
  nodeId: string;
  onChangeFlow: (next: FlowConfig) => void;
  onSelectNode: (id: string | null) => void;
}

export default function NodePanel({ flow, nodeId, onChangeFlow, onSelectNode }: Props) {
  const node = flow.nodes[nodeId];
  const [draftId, setDraftId] = useState(nodeId);

  if (!node) return null;

  const patch = (p: Partial<FlowNode>) => onChangeFlow(patchNode(flow, nodeId, p));
  const nodeIds = Object.keys(flow.nodes);
  const knownFields = graphFields(flow);
  const meta = NODE_TYPE_META[node.type];
  const Icon = meta.icon;
  const isStart = flow.start === nodeId;

  const commitRename = () => {
    const trimmed = draftId.trim();
    if (!trimmed || trimmed === nodeId) {
      setDraftId(nodeId);
      return;
    }
    if (trimmed in flow.nodes) {
      alert(`Node "${trimmed}" already exists.`);
      setDraftId(nodeId);
      return;
    }
    const next = renameNode(flow, nodeId, trimmed);
    onChangeFlow(next);
    onSelectNode(trimmed);
  };

  const remove = () => {
    if (!confirm(`Delete node "${nodeId}"? References to it will be cleared, not rewritten.`)) return;
    onChangeFlow(deleteNode(flow, nodeId));
    onSelectNode(null);
  };

  return (
    <div className="node-panel">
      <div className="node-panel-header" style={{ borderLeftColor: meta.color }}>
        <span className="node-panel-icon" style={{ background: `${meta.color}22`, color: meta.color }}>
          <Icon size={16} />
        </span>
        <div className="node-panel-heading">
          <div className="node-panel-type" style={{ color: meta.color }}>
            {meta.label} node {isStart && <span className="node-panel-start-badge">START</span>}
          </div>
          <input
            className="node-panel-id-input"
            value={draftId}
            onChange={(e) => setDraftId(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
        </div>
      </div>

      <div className="node-panel-actions">
        <button type="button" disabled={isStart} onClick={() => onChangeFlow({ ...flow, start: nodeId })}>
          <Flag size={13} />
          {isStart ? "Is start node" : "Set as start"}
        </button>
        <button type="button" className="danger" onClick={remove}>
          <Trash2 size={13} />
          Delete node
        </button>
      </div>

      {node.type === "collect" && (
        <CollectFields
          fields={node.fields}
          confirm={node.confirm}
          onChange={(fields) => patch({ fields })}
          onChangeConfirm={(confirm) => patch({ confirm })}
        />
      )}

      {(node.type === "collect" || node.type === "say") && (
        <div className="panel-section">
          <label className="mini-label">Next node</label>
          <select value={node.next ?? ""} onChange={(e) => patch({ next: e.target.value || null })}>
            <option value="">(none - dead end)</option>
            {nodeIds.filter((id) => id !== nodeId).map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </div>
      )}

      {node.type === "say" && (
        <div className="panel-section">
          <label className="mini-label">Text ({"{field}"} placeholders allowed)</label>
          <textarea rows={3} value={node.text ?? ""} onChange={(e) => patch({ text: e.target.value })} />
          {knownFields.length > 0 && (
            <p className="muted">Known fields: {knownFields.map((f) => `{${f}}`).join(", ")}</p>
          )}
        </div>
      )}

      {node.type === "handoff" && (
        <div className="panel-section">
          <label className="mini-label">Text spoken before transferring</label>
          <textarea rows={3} value={node.text ?? ""} onChange={(e) => patch({ text: e.target.value })} />
        </div>
      )}

      {node.type === "action" && (
        <div className="panel-section">
          <label className="mini-label">Connector</label>
          <input value={node.connector ?? ""} onChange={(e) => patch({ connector: e.target.value || null })} />

          <label className="mini-label">Operation</label>
          <input value={node.operation ?? ""} onChange={(e) => patch({ operation: e.target.value || null })} />

          <label className="mini-label">Result key (where the result lands in collected values)</label>
          <input value={node.result_key ?? ""} onChange={(e) => patch({ result_key: e.target.value || null })} />

          <div className="field-row-line" style={{ marginTop: 10 }}>
            <div>
              <label className="mini-label">Next (on success)</label>
              <select value={node.next ?? ""} onChange={(e) => patch({ next: e.target.value || null })}>
                <option value="">(none - dead end)</option>
                {nodeIds.filter((id) => id !== nodeId).map((id) => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mini-label">On error</label>
              <select value={node.on_error ?? ""} onChange={(e) => patch({ on_error: e.target.value || null })}>
                <option value="">(none - dead end)</option>
                {nodeIds.filter((id) => id !== nodeId).map((id) => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {node.type === "branch" && (
        <BranchArms
          branches={node.branches}
          nodeIds={nodeIds.filter((id) => id !== nodeId)}
          knownFields={knownFields}
          onChange={(branches) => patch({ branches })}
        />
      )}

      {node.type === "end" && <p className="muted panel-section">Ends the flow. Nothing else to configure.</p>}
    </div>
  );
}
