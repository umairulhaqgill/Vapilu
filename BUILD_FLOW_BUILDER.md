# Task: flow builder UI (phase 1, super-admin only)

Read `CLAUDE.md` first for the system architecture and the flow graph model.

## What to build

A standalone web app for authoring tenant flow graphs visually, so a flow
can be created without hand-writing JSON.

**Stack:** React + Vite (plain React, not Next.js — this is a single-page
tool, no SSR needed). Its own folder at `FlowBuilder/`, separate from the
Python services.

**Talks to:** the Tenant Config Service at `http://localhost:8004`, using
the existing shared token (see the auth note at the bottom — this matters).

## Screens

**1. Tenant list** — `GET /tenants`, click through to a tenant.

**2. Flow list for a tenant** — `GET /tenants/{id}/flows`. Create, open,
delete, toggle active.

**3. Flow editor** — the main piece:

- Canvas with nodes as boxes and edges as arrows. Drag to reposition, drag
  from a node's edge handle to connect. React Flow is a reasonable library
  choice here; use it unless you have a better suggestion.
- Node palette to add: collect, branch, action, say, handoff, end
- Side panel to edit the selected node:
  - **collect** — field list (name, prompt, required, format dropdown
    [phone/email/number/date], options list), plus optional confirm text
  - **branch** — ordered arms; each arm is a list of conditions built from
    dropdowns (field / op / value) with an all-or-any toggle, plus a goto
    target. An arm with no conditions is the fallback — make that visually
    obvious, since a graph without one can dead-end.
  - **action** — connector, operation, result_key, next, on_error
  - **say** — text, with `{field}` placeholder insertion from known fields
  - **handoff** — text
- Live validation panel — `PUT` returns
  `400 {"detail": {"graph_problems": [...]}}`. Also validate client-side as
  the user edits so problems appear before they hit save: dangling gotos,
  unreachable nodes, branches with no arms, actions missing connector.
- Save via `PUT /flows/{flow_id}`

## Important constraints

**Node positions aren't in the schema.** `FlowConfig` has no x/y. Either
add an optional `ui` dict to the node schema in
`TenantConfig/flow_config.py` (preferred — one field, no migration since
config is a JSON column), or auto-layout on load. Don't silently drop
positions on save.

**Keep the round-trip lossless.** Load a flow, save it unchanged, and the
stored JSON should be equivalent. Legacy flat flows auto-convert to graphs
on load — be careful not to write back a broken hybrid.

**The condition editor is why conditions are structured data.** Each
condition is `{field, op, value}` with ops eq / ne / in / not_in / exists /
not_exists / contains. Render as dropdowns; the `field` dropdown should
offer field names collected anywhere earlier in the graph.

## Auth — read this before wiring anything

The Tenant Config Service currently uses **one shared token that grants
full access to every tenant**. This build is **super-admin only**. Do not
add tenant login, and do not design anything that implies a tenant could
use this yet.

Exposing this UI to tenants with the current API would let any tenant read
and edit every other tenant's flows. Hiding it in the UI is not a fix —
curl bypasses the UI. Per-user auth with server-side tenant scoping is a
separate piece of work that must come before any tenant logs in.

Put the token in a `.env` (Vite: `VITE_TENANT_SERVICE_TOKEN`) and note in
the README that this is a developer tool, not a tenant-facing one.

## Suggested order

1. Scaffold + API client + tenant/flow lists (proves connectivity)
2. Read-only canvas rendering an existing flow (`book_appointment` from
   `seed_flows.py` is a good test — it branches)
3. Node editing panel
4. Edge creation/deletion
5. Validation panel
6. Save round-trip

Get step 2 working against real data before building editors — if the
canvas can't faithfully render a flow that already exists, editing it will
be worse.
