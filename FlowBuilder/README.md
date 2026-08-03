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
- **Call Test** (`src/pages/CallTest.tsx` + `src/call/*`): a second tab
  that connects to the Orchestrator's `ws://localhost:8001/ws/call`
  directly from the browser and lets you talk to any tenant's bot without
  the Python mic client. Plays the same role as
  `Orchestrator/test_call_mic.py`, including the same client-first local
  VAD barge-in (`src/call/vad.ts` is a line-for-line port of
  `local_vad.py`) - the point being to exercise the real interruption
  path, not a simplified one. Unlike the Python client it requests
  `echoCancellation` via `getUserMedia`, so real acoustic AEC applies and
  headphones aren't strictly required (see CLAUDE.md's "No echo
  cancellation" note, which is about the Python client specifically).
  `src/call/CallSession.ts` owns the WebSocket + mic + playback lifecycle
  as a plain class, not a hook - it manages mutable audio objects that
  don't belong in React state.

## Backend changes made alongside this

- `FlowNode.ui: dict | None` in `TenantConfig/flow_config.py` - canvas
  position, opaque to the flow engine.
- `GET /tenants/{id}/flows?include_inactive=true` in
  `TenantConfig/tenant_service.py` - the flow list needs to show (and let
  you re-activate) inactive flows, not just the active ones the
  Orchestrator loads at call time.
- CORS middleware on the Tenant Config Service, scoped to the Vite dev
  server's two origins - needed for any browser client, not just this one.
- `caller_transcript` event added to the Orchestrator's `/ws/call`
  WebSocket (`Orchestrator/orchestrator_service.py`) - the server already
  knew what STT heard, but never sent it to the client. Purely additive;
  existing clients (`test_call_mic.py`) ignore unknown events.

## Call Test - requires the full pipeline

Unlike the Flows tab (Tenant Config Service only), Call Test needs all
four voice services up: STT (8000), Orchestrator (8001), NLU (8002), TTS
(8003) - `..\run_all.ps1` from the project root starts all of them plus
Tenant Config. Set `VITE_ORCHESTRATOR_TOKEN` in `.env` to match
`ORCHESTRATOR_TOKEN` in `Orchestrator/.env`.
