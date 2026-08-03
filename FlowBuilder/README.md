# Vapilu Flow Builder

A visual editor for tenant flow graphs, so a flow can be authored without
hand-writing JSON. Talks to the Tenant Config Service (`TenantConfig/`,
port 8004).

**This is a developer tool, not a tenant-facing one.** The Tenant Config
Service currently uses one shared token that grants full access to every
tenant's data. Do not deploy this UI anywhere a tenant could reach it, and
do not add tenant login to it - per-user auth with server-side tenant
scoping has to land in the Tenant Config Service first. See the "Known
gaps that matter" section of the root `CLAUDE.md`.

## Run it

```
npm install
npm run dev
```

Requires the Tenant Config Service running at `http://localhost:8004`
(`cd ../TenantConfig && python -m uvicorn tenant_service:app --port 8004`)
with CORS already configured to allow `http://localhost:5173` and
`http://127.0.0.1:5173`.

Copy `.env.example` to `.env` and set `VITE_TENANT_SERVICE_TOKEN` to match
`TENANT_SERVICE_TOKEN` in `TenantConfig/.env`.

## What's here

- **Tenant list -> flow list -> flow editor**, drill-down navigation with
  local component state (no router - three screens doesn't need one).
- **Canvas** (`src/editor/Canvas.tsx`): React Flow. Nodes are draggable;
  drag from a node's handle to another node to wire `next` / `on_error` /
  a branch arm's `goto`. Positions are stored in an optional `ui: {x, y}`
  field on each node (added to `FlowConfig` in `TenantConfig/flow_config.py`
  - the schema had no notion of layout before this). Nodes without a
  position get one from a simple BFS-depth auto-layout
  (`src/editor/layout.ts`) that isn't written back until the node is
  actually moved.
- **Side panel** (`src/editor/NodePanel.tsx` + `src/editor/panels/*`):
  editors per node type. Branch conditions render as dropdowns
  (field / op / value) rather than free text, mirroring the structured
  `Condition` model server-side - there's no expression parser to keep in
  sync.
- **Validation** (`src/editor/validate.ts`): a hand-ported mirror of
  `FlowConfig.validate_graph` in `TenantConfig/flow_config.py`, so problems
  (dangling gotos, unreachable nodes, branches with no fallback, etc.)
  show up as you edit rather than only on save. Keep the two in sync by
  hand if the Python side changes - there's no shared schema.
- **Save** always sends a pure graph: the legacy flat fields (`collect`,
  `action`, `on_success`, `on_failure`) are cleared on every PUT, so a
  flow that started in the old flat format gets normalized to a graph the
  first time it's edited here, rather than being written back as a
  half-flat/half-graph hybrid.

## Backend changes made alongside this

- `FlowNode.ui: dict | None` in `TenantConfig/flow_config.py` - canvas
  position, opaque to the flow engine.
- `GET /tenants/{id}/flows?include_inactive=true` in
  `TenantConfig/tenant_service.py` - the flow list needs to show (and let
  you re-activate) inactive flows, not just the active ones the
  Orchestrator loads at call time.
- CORS middleware on the Tenant Config Service, scoped to the Vite dev
  server's two origins - needed for any browser client, not just this one.
