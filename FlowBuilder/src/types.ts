// Mirrors TenantConfig/flow_config.py. Keep in sync by hand - there is no
// schema codegen, so a Python field added there needs a matching edit here.

export type ConditionOp = "eq" | "ne" | "in" | "not_in" | "exists" | "not_exists" | "contains";

export interface Condition {
  field: string;
  op: ConditionOp;
  value?: unknown;
}

export interface Branch {
  when: Condition[];
  match: "all" | "any";
  goto: string;
}

export type FieldFormat = "phone" | "email" | "number" | "date";

export interface FlowField {
  name: string;
  prompt: string;
  required: boolean;
  format?: FieldFormat | null;
  options?: string[] | null;
  // When set, valid answers come from the tenant's entities of this type
  // (see Entity below) instead of the static `options` list - the
  // Orchestrator fills `options` in per call from whatever entities
  // currently exist.
  entity_type?: string | null;
}

export type NodeType = "collect" | "say" | "action" | "branch" | "handoff" | "end";

export interface NodeUi {
  x: number;
  y: number;
}

export interface FlowNode {
  type: NodeType;
  fields: FlowField[];
  confirm?: string | null;
  text?: string | null;
  connector?: string | null;
  operation?: string | null;
  result_key?: string | null;
  on_error?: string | null;
  // Action nodes only: name of a collect field (elsewhere in the flow)
  // whose entity_type picked the specific resource this action runs
  // against, e.g. "branch". Lets the connector look up settings scoped to
  // that one entity instead of the tenant as a whole.
  entity_field?: string | null;
  branches: Branch[];
  next?: string | null;
  ui?: NodeUi | null;
}

export interface FlowConfig {
  flow_id: string;
  tenant_id: string;
  trigger: string;
  start?: string | null;
  nodes: Record<string, FlowNode>;
  active: boolean;
  // Legacy flat fields. The builder never authors these - it always saves
  // pure graphs - but they're kept here so TypeScript doesn't choke on a
  // GET response for a flow that hasn't been re-saved since the old format.
  collect?: FlowField[];
  confirm?: string | null;
  action?: Record<string, unknown> | null;
  on_success?: string | null;
  on_failure?: string | null;
}

// Mirrors TenantConfig/tenant_config.py.

export interface BusinessHours {
  monday?: string | null;
  tuesday?: string | null;
  wednesday?: string | null;
  thursday?: string | null;
  friday?: string | null;
  saturday?: string | null;
  sunday?: string | null;
  timezone: string;
}

export interface Entity {
  id: string;
  type: string;
  label: string;
  aliases: string[];
}

export interface TenantConfig {
  tenant_id: string;
  business_name: string;
  greeting: string;
  system_prompt_extra: string;
  language: string;
  voice?: string | null;
  business_hours: BusinessHours;
  escalation_phone?: string | null;
  capabilities: string[];
  enabled_connectors: string[];
  entities: Entity[];
  active: boolean;
}

export function emptyNode(type: NodeType): FlowNode {
  return {
    type,
    fields: [],
    confirm: null,
    text: type === "say" ? "" : type === "handoff" ? "" : null,
    connector: null,
    operation: null,
    result_key: null,
    on_error: null,
    entity_field: null,
    branches: type === "branch" ? [{ when: [], match: "all", goto: "" }] : [],
    next: null,
    ui: null,
  };
}
