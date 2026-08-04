# Connector Gateway

The generic seam between a flow's `action` nodes and whatever real backend
does the work (a booking system, a calendar, a CRM lookup). Previously
`drive_flow` in the Orchestrator faked this entirely - logged what it
would have called and continued as if it had succeeded. This is the real
thing.

```
Orchestrator  --HTTP POST /call-->  This service  -->  a connector module
```

## Why generic, not "the booking app"

The flow model already treats `connector` / `operation` / `values` /
`result_key` as domain-agnostic - any node can call any connector with
any operation. This service stays generic too: it's a plugin registry.
`connector` is just a string name looked up in `connectors/registry.py`;
every vendor- or business-specific detail lives inside one connector
module, same "one file, one vendor" shape as `stt_client.py` /
`nlu_client.py` / `tts_client.py` / `tenant_store.py` elsewhere in this
project. Adding a real Google Calendar connector later means adding one
file with the right `CONNECTOR_ID`/`OPERATIONS` shape and one line in
`registry.py` - nothing in the Orchestrator, the flow engine, or other
connectors changes.

## What's here

- `connectors/base.py` - the interface every connector implements:
  `CONNECTOR_ID: str` and `OPERATIONS: dict[str, async (values) -> dict]`.
  Raise `ConnectorError` for an expected failure (slot's taken, a
  required field is missing) - it comes back as `{"ok": false, "error":
  ...}`, not a 500, and routes the flow's `on_error` path.
- `connectors/mock_booking.py` - `CONNECTOR_ID = "booking"`. In-memory,
  no real calendar behind it - proves the plumbing end-to-end (including
  the failure path: a slot really does fill up and really does reject
  the next booking) without needing real credentials for anything yet.
  Scoped per tenant (via `_tenant_id` in `values`) so two tenants
  booking "Tuesday" never collide.
- `connectors/registry.py` - explicit registry (`_MODULES = [mock_booking]`),
  not filesystem auto-discovery. Adding a connector is one import + one
  line here, and it's obvious from reading the file what's registered.
- `connector_config_store.py` - per-tenant, per-connector settings (an API
  key, a calendar ID). Same SQL-with-JSON-fallback shape as
  `TenantConfig/tenant_store.py`, and deliberately owned here rather than
  in the Tenant Config Service - see "Per-tenant connector settings" below.

## Per-tenant connector settings

Every connector can need per-tenant configuration - which calendar to
book against, which CRM instance, an API key. That's stored here, not in
the Tenant Config Service: it's connector-shaped (a totally different set
of fields per connector) and credential-shaped (more sensitive than
`business_name`/`greeting`), not general business config. See
`connector_config_store.py`'s docstring for the full reasoning.

`enabled_connectors` (which connectors a tenant has turned on) is the one
piece that *does* stay in `TenantConfig` - it's a plain business toggle,
not a credential.

Every `/call` looks the calling tenant's config up (via `_tenant_id`,
already present in `values` - the Orchestrator injects it) and merges it
into `values["_config"]` before invoking the connector's handler, so a
connector that needs settings just reads `values["_config"]` - no change
to the `Operation` signature, no Orchestrator involvement. See
`connectors/mock_booking.py`'s `_max_per_slot()` for a real example of a
connector reading it.

Manage these through the Flow Builder's per-tenant **Connectors** tab, or
directly:

```
GET    /connectors/{connector_id}/tenants/{tenant_id}/config?token=...
PUT    /connectors/{connector_id}/tenants/{tenant_id}/config?token=...   body: {"config": {...}}
DELETE /connectors/{connector_id}/tenants/{tenant_id}/config?token=...
```

## Why its own service

Split out from the Orchestrator (rather than a module inside it) so a
slow or misbehaving external API - Google's OAuth token refresh, a CRM's
rate limit - can't sit directly in the same process handling live call
audio. The cost is one extra network hop per action node and a service
to run.

## Setup

```
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `CONNECTOR_GATEWAY_TOKEN` - a random string, and the same value goes in
  the Orchestrator's `.env` (and the Flow Builder's, as
  `VITE_CONNECTOR_GATEWAY_TOKEN`).
- `CONNECTOR_DB_URL` - same "vapilu" MySQL database the other services
  use (a new table, `connector_configs`). Leave unset to fall back to
  JSON files in `CONNECTOR_DATA_DIR` instead.

```
uvicorn connector_gateway_service:app --reload --port 8005
```

Or just use `..\run_all.ps1` / `..\run_all_browser.ps1` from the project
root, which start this alongside everything else.

## API

```
GET  /health
GET  /connectors?token=...                -> {"booking": ["cancel_booking", "check_availability", "create_booking"]}
POST /call  {connector, operation, values, token}
                                           -> {"ok": true,  "result": {...}}
                                           -> {"ok": false, "error": "..."}
```

`/call` always returns `200` - a connector-level failure (unknown
connector, unknown operation, or a raised `ConnectorError`) is reported
in the body, not as an HTTP error status, because the Orchestrator treats
every non-`ok` result the same way regardless of why it failed.

## Adding a real connector (e.g. Google Calendar)

1. New file, e.g. `connectors/google_calendar.py`, with a `CONNECTOR_ID`
   (the string flows will reference) and an `OPERATIONS` dict matching
   `connectors/base.py`'s shape.
2. Read per-tenant credentials (an OAuth token, a calendar ID) from
   `values["_config"]` inside each operation - never hardcoded, never in
   the Orchestrator, which shouldn't need to know which calendar vendor
   is behind a flow's `connector` field any more than it needs to know
   which STT vendor is behind transcription. Each tenant sets their own
   via the per-tenant config API (see above) or the Flow Builder's
   Connectors tab.
3. Add the module to `_MODULES` in `registry.py`.
4. Point a tenant's flow at it by setting the `action` node's `connector`
   field to whatever `CONNECTOR_ID` you chose - no Orchestrator or flow
   engine changes needed.

`preferred_day` (or whatever field a flow collects for scheduling) is
caller-spoken free text captured via LLM extraction, not a normalized
date - a real calendar connector will need actual date/time parsing and
almost certainly the tenant's timezone (already stored in
`TenantConfig.business_hours.timezone`, just not threaded through to
connector calls yet).
