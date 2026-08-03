import type { FlowConfig, FlowNode, NodeType } from "../types";
import { emptyNode } from "../types";

const TYPE_PREFIX: Record<NodeType, string> = {
  collect: "collect",
  say: "say",
  action: "action",
  branch: "branch",
  handoff: "handoff",
  end: "end",
};

function freshNodeId(flow: FlowConfig, type: NodeType): string {
  const prefix = TYPE_PREFIX[type];
  let n = 1;
  while (`${prefix}_${n}` in flow.nodes) n += 1;
  return `${prefix}_${n}`;
}

export function addNode(flow: FlowConfig, type: NodeType, at?: { x: number; y: number }): { flow: FlowConfig; id: string } {
  const id = freshNodeId(flow, type);
  const node = emptyNode(type);
  if (at) node.ui = at;
  const nodes = { ...flow.nodes, [id]: node };
  const start = flow.start ?? id;
  return { flow: { ...flow, nodes, start }, id };
}

export function replaceNode(flow: FlowConfig, nodeId: string, node: FlowNode): FlowConfig {
  return { ...flow, nodes: { ...flow.nodes, [nodeId]: node } };
}

export function patchNode(flow: FlowConfig, nodeId: string, patch: Partial<FlowNode>): FlowConfig {
  const existing = flow.nodes[nodeId];
  if (!existing) return flow;
  return replaceNode(flow, nodeId, { ...existing, ...patch });
}

// Renames a node's key and rewrites every reference to it (next, on_error,
// branch gotos, and `start`) so the graph doesn't silently break.
export function renameNode(flow: FlowConfig, oldId: string, newId: string): FlowConfig {
  if (oldId === newId || !newId.trim()) return flow;
  if (newId in flow.nodes) return flow;

  const nodes: Record<string, FlowNode> = {};
  for (const [id, node] of Object.entries(flow.nodes)) {
    const renamedId = id === oldId ? newId : id;
    nodes[renamedId] = {
      ...node,
      next: node.next === oldId ? newId : node.next,
      on_error: node.on_error === oldId ? newId : node.on_error,
      branches: node.branches.map((b) => (b.goto === oldId ? { ...b, goto: newId } : b)),
    };
  }

  return {
    ...flow,
    start: flow.start === oldId ? newId : flow.start,
    nodes,
  };
}

// Removes a node and clears (rather than silently rewrites) any reference
// to it, so the resulting dangling-goto shows up in validation instead of
// disappearing.
export function deleteNode(flow: FlowConfig, nodeId: string): FlowConfig {
  const nodes: Record<string, FlowNode> = {};
  for (const [id, node] of Object.entries(flow.nodes)) {
    if (id === nodeId) continue;
    nodes[id] = {
      ...node,
      next: node.next === nodeId ? null : node.next,
      on_error: node.on_error === nodeId ? null : node.on_error,
      branches: node.branches.map((b) => (b.goto === nodeId ? { ...b, goto: "" } : b)),
    };
  }
  return {
    ...flow,
    start: flow.start === nodeId ? null : flow.start,
    nodes,
  };
}

export function setNodePosition(flow: FlowConfig, nodeId: string, x: number, y: number): FlowConfig {
  return patchNode(flow, nodeId, { ui: { x, y } });
}

// Field names known anywhere in the graph - every `collect` field name plus
// every action `result_key` - so the condition editor can offer them as
// dropdown options instead of making the author retype them by hand.
// Doesn't restrict to ancestors of a given node; a flow this small doesn't
// need that precision, and being permissive is safer than hiding a valid
// field because the traversal missed a path.
export function graphFields(flow: FlowConfig): string[] {
  const names = new Set<string>();
  for (const node of Object.values(flow.nodes)) {
    for (const f of node.fields) if (f.name) names.add(f.name);
    if (node.result_key) names.add(node.result_key);
  }
  return Array.from(names).sort();
}
