import { Handle, Position, type NodeProps } from "reactflow";
import type { Branch, FlowNode } from "../types";

export interface FlowNodeBoxData {
  nodeId: string;
  node: FlowNode;
  isStart: boolean;
}

const TYPE_COLOR: Record<FlowNode["type"], string> = {
  collect: "#2563eb",
  say: "#059669",
  action: "#d97706",
  branch: "#7c3aed",
  handoff: "#dc2626",
  end: "#475569",
};

function summarizeBranch(b: Branch, i: number): string {
  if (b.when.length === 0) return "else (fallback)";
  const parts = b.when.map((c) => `${c.field} ${c.op} ${c.value ?? ""}`.trim());
  return `${i + 1}. ${parts.join(b.match === "all" ? " AND " : " OR ")}`;
}

function outputHandles(node: FlowNode): { id: string; label: string }[] {
  switch (node.type) {
    case "collect":
    case "say":
      return [{ id: "next", label: "next" }];
    case "action":
      return [
        { id: "next", label: "✓ success" },
        { id: "on_error", label: "✗ error" },
      ];
    case "branch":
      return node.branches.map((b, i) => ({ id: `branch-${i}`, label: summarizeBranch(b, i) }));
    default:
      return [];
  }
}

function bodyPreview(node: FlowNode): string {
  switch (node.type) {
    case "collect":
      return node.fields.length ? node.fields.map((f) => f.name).join(", ") : "(no fields)";
    case "say":
      return node.text || "(empty)";
    case "handoff":
      return node.text || "(empty)";
    case "action":
      return `${node.connector ?? "?"}.${node.operation ?? "?"}${node.result_key ? ` -> ${node.result_key}` : ""}`;
    case "branch":
      return `${node.branches.length} arm${node.branches.length === 1 ? "" : "s"}`;
    case "end":
      return "Stops the flow";
    default:
      return "";
  }
}

export default function FlowNodeBox({ data, selected }: NodeProps<FlowNodeBoxData>) {
  const { nodeId, node, isStart } = data;
  const color = TYPE_COLOR[node.type];
  const outputs = outputHandles(node);
  const handleCount = Math.max(outputs.length, 1);

  return (
    <div
      style={{
        width: 240,
        borderRadius: 8,
        borderTop: selected ? `2px solid ${color}` : "1px solid #334155",
        borderRight: selected ? `2px solid ${color}` : "1px solid #334155",
        borderBottom: selected ? `2px solid ${color}` : "1px solid #334155",
        borderLeft: `6px solid ${color}`,
        background: "#1e293b",
        color: "#e2e8f0",
        boxShadow: selected ? "0 0 0 3px rgba(37,99,235,0.25)" : "0 1px 2px rgba(0,0,0,0.4)",
        fontSize: 12,
      }}
    >
      <Handle type="target" position={Position.Left} id="in" style={{ background: "#94a3b8" }} />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 10px",
          borderBottom: "1px solid #334155",
          fontWeight: 600,
        }}
      >
        <span style={{ textTransform: "uppercase", color, letterSpacing: 0.5 }}>{node.type}</span>
        {isStart && (
          <span style={{ fontSize: 10, background: "#166534", color: "#bbf7d0", padding: "1px 6px", borderRadius: 4 }}>
            START
          </span>
        )}
      </div>
      <div style={{ padding: "8px 10px" }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{nodeId}</div>
        <div style={{ color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {bodyPreview(node)}
        </div>
      </div>

      {outputs.map((h, i) => (
        <Handle
          key={h.id}
          type="source"
          position={Position.Right}
          id={h.id}
          title={h.label}
          style={{ top: `${((i + 1) / (handleCount + 1)) * 100}%`, background: color }}
        />
      ))}
    </div>
  );
}
