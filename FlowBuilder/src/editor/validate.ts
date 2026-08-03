import type { FlowConfig } from "../types";

// Mirrors FlowConfig.validate_graph / ._reachable in
// TenantConfig/flow_config.py line for line, so problems surface in the
// editor before a PUT round-trips them back from the server.
export function validateGraph(flow: FlowConfig): string[] {
  const problems: string[] = [];
  const nodeNames = Object.keys(flow.nodes);

  if (nodeNames.length === 0) return ["flow has no nodes"];

  if (!flow.start) {
    problems.push("flow has no start node");
  } else if (!(flow.start in flow.nodes)) {
    problems.push(`start node ${JSON.stringify(flow.start)} does not exist`);
  }

  for (const name of nodeNames) {
    const node = flow.nodes[name];
    const targets: string[] = [];
    if (node.next) targets.push(node.next);
    if (node.on_error) targets.push(node.on_error);
    for (const b of node.branches) targets.push(b.goto);

    for (const target of targets) {
      if (!(target in flow.nodes)) {
        problems.push(`node ${JSON.stringify(name)} points to missing node ${JSON.stringify(target)}`);
      }
    }

    if (node.type === "branch" && node.branches.length === 0) {
      problems.push(`branch node ${JSON.stringify(name)} has no branches`);
    }
    if ((node.type === "collect" || node.type === "say") && !node.next) {
      problems.push(`node ${JSON.stringify(name)} has no next node`);
    }
    if (node.type === "action" && (!node.connector || !node.operation)) {
      problems.push(`action node ${JSON.stringify(name)} needs connector and operation`);
    }
  }

  const reachable = reachableFrom(flow);
  for (const name of nodeNames) {
    if (!reachable.has(name)) {
      problems.push(`node ${JSON.stringify(name)} is unreachable`);
    }
  }

  return problems;
}

function reachableFrom(flow: FlowConfig): Set<string> {
  if (!flow.start || !(flow.start in flow.nodes)) return new Set();
  const seen = new Set<string>();
  const stack = [flow.start];
  while (stack.length) {
    const name = stack.pop()!;
    if (seen.has(name) || !(name in flow.nodes)) continue;
    seen.add(name);
    const node = flow.nodes[name];
    const targets = [node.next, node.on_error, ...node.branches.map((b) => b.goto)];
    for (const t of targets) {
      if (t) stack.push(t);
    }
  }
  return seen;
}
