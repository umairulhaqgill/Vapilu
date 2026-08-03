import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Connection,
  type Edge,
  type Node,
  type NodeDragHandler,
  type NodeMouseHandler,
  type OnConnect,
  type OnEdgesDelete,
} from "reactflow";
import "reactflow/dist/style.css";
import type { FlowConfig } from "../types";
import FlowNodeBox, { type FlowNodeBoxData } from "./FlowNodeBox";
import { layoutMissingPositions } from "./layout";
import { patchNode, setNodePosition } from "./flowOps";

const nodeTypes = { flowNode: FlowNodeBox };

interface CanvasProps {
  flow: FlowConfig;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  onChangeFlow: (next: FlowConfig) => void;
}

export default function Canvas({ flow, selectedNodeId, onSelectNode, onChangeFlow }: CanvasProps) {
  const positions = useMemo(() => layoutMissingPositions(flow), [flow]);

  const nodes: Node<FlowNodeBoxData>[] = useMemo(
    () =>
      Object.entries(flow.nodes).map(([id, node]) => ({
        id,
        type: "flowNode",
        position: positions[id] ?? { x: 0, y: 0 },
        data: { nodeId: id, node, isStart: flow.start === id },
        selected: id === selectedNodeId,
      })),
    [flow, positions, selectedNodeId]
  );

  const edges: Edge[] = useMemo(() => {
    const list: Edge[] = [];
    for (const [id, node] of Object.entries(flow.nodes)) {
      if (node.next && node.next in flow.nodes) {
        list.push(edgeFor(id, "next", node.next));
      }
      if (node.on_error && node.on_error in flow.nodes) {
        list.push(edgeFor(id, "on_error", node.on_error, "error", "#dc2626"));
      }
      node.branches.forEach((b, i) => {
        if (b.goto && b.goto in flow.nodes) {
          list.push(edgeFor(id, `branch-${i}`, b.goto, b.when.length ? undefined : "else", "#7c3aed"));
        }
      });
    }
    return list;
  }, [flow]);

  const onNodeDragStop: NodeDragHandler = useCallback(
    (_evt, dragged) => {
      // A plain click registers as a zero-distance drag. Skip the commit
      // in that case so merely selecting a node doesn't mark the flow
      // dirty by writing back its auto-computed layout position.
      const before = positions[dragged.id];
      if (before && before.x === dragged.position.x && before.y === dragged.position.y) return;
      onChangeFlow(setNodePosition(flow, dragged.id, dragged.position.x, dragged.position.y));
    },
    [flow, onChangeFlow, positions]
  );

  const onNodeClick: NodeMouseHandler = useCallback((_evt, n) => onSelectNode(n.id), [onSelectNode]);

  const onConnect: OnConnect = useCallback(
    (conn: Connection) => {
      if (!conn.source || !conn.target || !conn.sourceHandle) return;
      const node = flow.nodes[conn.source];
      if (!node) return;
      if (conn.sourceHandle === "next") {
        onChangeFlow(patchNode(flow, conn.source, { next: conn.target }));
      } else if (conn.sourceHandle === "on_error") {
        onChangeFlow(patchNode(flow, conn.source, { on_error: conn.target }));
      } else if (conn.sourceHandle.startsWith("branch-")) {
        const idx = Number(conn.sourceHandle.slice("branch-".length));
        const branches = node.branches.map((b, i) => (i === idx ? { ...b, goto: conn.target as string } : b));
        onChangeFlow(patchNode(flow, conn.source, { branches }));
      }
    },
    [flow, onChangeFlow]
  );

  const onEdgesDelete: OnEdgesDelete = useCallback(
    (deleted) => {
      let next = flow;
      for (const e of deleted) {
        const handle = e.sourceHandle;
        const node = next.nodes[e.source];
        if (!node || !handle) continue;
        if (handle === "next") next = patchNode(next, e.source, { next: null });
        else if (handle === "on_error") next = patchNode(next, e.source, { on_error: null });
        else if (handle.startsWith("branch-")) {
          const idx = Number(handle.slice("branch-".length));
          const branches = node.branches.map((b, i) => (i === idx ? { ...b, goto: "" } : b));
          next = patchNode(next, e.source, { branches });
        }
      }
      if (next !== flow) onChangeFlow(next);
    },
    [flow, onChangeFlow]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeDragStop={onNodeDragStop}
      onNodeClick={onNodeClick}
      onPaneClick={() => onSelectNode(null)}
      onConnect={onConnect}
      onEdgesDelete={onEdgesDelete}
      deleteKeyCode={["Backspace", "Delete"]}
      fitView
      proOptions={{ hideAttribution: true }}
    >
      <Background color="var(--border)" />
      <Controls />
      <MiniMap pannable zoomable style={{ background: "var(--bg)" }} />
    </ReactFlow>
  );
}

function edgeFor(source: string, sourceHandle: string, target: string, label?: string, color?: string): Edge {
  return {
    id: `${source}:${sourceHandle}->${target}`,
    source,
    target,
    sourceHandle,
    targetHandle: "in",
    label,
    style: color ? { stroke: color } : undefined,
    labelStyle: { fill: "var(--text)", fontSize: 10 },
    labelBgStyle: { fill: "var(--bg-elevated)" },
    labelBgPadding: [4, 2],
    markerEnd: { type: MarkerType.ArrowClosed, color: color ?? "#64748b" },
  };
}
