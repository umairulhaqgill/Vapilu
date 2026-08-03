import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import { api, ApiError } from "../api";
import type { FlowConfig, NodeType } from "../types";
import Canvas from "../editor/Canvas";
import NodePalette from "../editor/NodePalette";
import NodePanel from "../editor/NodePanel";
import ValidationPanel from "../editor/ValidationPanel";
import { validateGraph } from "../editor/validate";
import { addNode } from "../editor/flowOps";

interface Props {
  flowId: string;
}

export default function FlowEditor({ flowId }: Props) {
  const [flow, setFlow] = useState<FlowConfig | null>(null);
  const [savedJson, setSavedJson] = useState<string>("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [serverProblems, setServerProblems] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api
      .getFlow(flowId)
      .then((f) => {
        if (cancelled) return;
        setFlow(f);
        setSavedJson(JSON.stringify(f));
      })
      .catch((e) => !cancelled && setLoadError(e instanceof ApiError ? String(e.message) : "Failed to load flow"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [flowId]);

  const clientProblems = useMemo(() => (flow ? validateGraph(flow) : []), [flow]);
  const dirty = flow ? JSON.stringify(flow) !== savedJson : false;

  if (loading) return <p className="muted">Loading flow...</p>;
  if (loadError) return <p className="error">{loadError}</p>;
  if (!flow) return null;

  const handleAdd = (type: NodeType) => {
    const { flow: next, id } = addNode(flow, type, { x: 40, y: 40 + Object.keys(flow.nodes).length * 40 });
    setFlow(next);
    setSelectedNodeId(id);
  };

  const handleSave = async () => {
    setSaving(true);
    setServerProblems(null);
    try {
      // The builder only ever authors graphs - never resend legacy flat
      // fields, so a flow loaded from the old format doesn't get saved
      // back as a broken half-graph/half-flat hybrid.
      const toSave: FlowConfig = {
        ...flow,
        collect: [],
        confirm: null,
        action: null,
        on_success: null,
        on_failure: null,
      };
      const saved = await api.saveFlow(flowId, toSave);
      setFlow(saved);
      setSavedJson(JSON.stringify(saved));
    } catch (e) {
      if (e instanceof ApiError && e.detail && typeof e.detail === "object" && "graph_problems" in (e.detail as object)) {
        setServerProblems((e.detail as { graph_problems: string[] }).graph_problems);
      } else {
        alert(`Save failed: ${e instanceof Error ? e.message : e}`);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="editor-layout">
      <div className="editor-toolbar">
        <h2>{flow.flow_id}</h2>
        <span className="muted">{flow.trigger}</span>
        <div className="spacer" />
        {dirty && <span className="dirty-dot" title="Unsaved changes" />}
        <button type="button" className="primary" onClick={handleSave} disabled={saving || clientProblems.length > 0}>
          <Save size={14} />
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      <NodePalette onAdd={handleAdd} />

      <div className="editor-body">
        <div className="canvas-wrap">
          <Canvas flow={flow} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} onChangeFlow={setFlow} />
        </div>
        <div className="side-rail">
          <ValidationPanel clientProblems={clientProblems} serverProblems={serverProblems} />
          {selectedNodeId && flow.nodes[selectedNodeId] ? (
            <NodePanel
              key={selectedNodeId}
              flow={flow}
              nodeId={selectedNodeId}
              onChangeFlow={setFlow}
              onSelectNode={setSelectedNodeId}
            />
          ) : (
            <p className="muted panel-section">Select a node to edit it, or add one from the palette above.</p>
          )}
        </div>
      </div>
    </div>
  );
}
