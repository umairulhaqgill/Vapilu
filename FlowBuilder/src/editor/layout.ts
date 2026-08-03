import type { FlowConfig, NodeUi } from "../types";

const COLUMN_WIDTH = 300;
const ROW_HEIGHT = 150;

// Assigns x/y to any node missing `ui` (a fresh node, or a flow loaded
// from before positions existed). Reachable nodes are laid out in columns
// by BFS depth from start; nodes the graph can't reach yet (e.g. mid-edit,
// or a stray import) get a row of their own below so they stay visible
// rather than stacking at the origin.
export function layoutMissingPositions(flow: FlowConfig): Record<string, NodeUi> {
  const positions: Record<string, NodeUi> = {};
  for (const [id, node] of Object.entries(flow.nodes)) {
    if (node.ui) positions[id] = node.ui;
  }

  const depth: Record<string, number> = {};
  if (flow.start && flow.start in flow.nodes) {
    const queue: [string, number][] = [[flow.start, 0]];
    while (queue.length) {
      const [name, d] = queue.shift()!;
      if (name in depth) continue;
      depth[name] = d;
      const node = flow.nodes[name];
      if (!node) continue;
      const targets = [node.next, node.on_error, ...node.branches.map((b) => b.goto)];
      for (const t of targets) {
        if (t && !(t in depth)) queue.push([t, d + 1]);
      }
    }
  }

  const columnCounts: Record<number, number> = {};
  let maxDepth = 0;
  for (const id of Object.keys(flow.nodes)) {
    if (id in positions) continue;
    const d = depth[id];
    if (d === undefined) continue;
    maxDepth = Math.max(maxDepth, d);
    const row = columnCounts[d] ?? 0;
    columnCounts[d] = row + 1;
    positions[id] = { x: d * COLUMN_WIDTH, y: row * ROW_HEIGHT };
  }

  let orphanIndex = 0;
  const orphanRowY = (maxDepth + 1) * ROW_HEIGHT + 100;
  for (const id of Object.keys(flow.nodes)) {
    if (id in positions) continue;
    positions[id] = { x: orphanIndex * COLUMN_WIDTH, y: orphanRowY };
    orphanIndex += 1;
  }

  return positions;
}
