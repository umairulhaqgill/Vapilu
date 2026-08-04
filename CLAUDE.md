# Vapilu — multi-tenant AI voice agent platform

A generic voice/chat bot platform that any business can configure to handle
inbound calls: greet callers, understand them, complete tasks (booking,
lookups), and hand off to a human when needed. One deployment serves many
businesses; everything business-specific is configuration, not code.

## Architecture

Six backend services, each its own folder with its own venv and `.env`,
plus one frontend (`FlowBuilder/`, a Vite dev server, no venv/`.env` in
the same sense - see its own README).

| Service | Folder | Port | Role |
|---|---|---|---|
| STT | `STT/` | 8000 | Speech to text (Deepgram) |
| Orchestrator | `Orchestrator/` | 8001 | Conversation state machine, flow execution |
| NLU | `NLU/` | 8002 | LLM replies + field extraction (Claude via OpenRouter, or a local Ollama fallback) |
| TTS | `TTS/` | 8003 | Text to speech (Piper, local) |
| Tenant Config | `TenantConfig/` | 8004 | Per-business settings and flow definitions (MySQL) |
| Connector Gateway | `ConnectorGateway/` | 8005 | Generic plugin registry action nodes call into (booking, calendar, CRM, ...) |
| Flow Builder | `FlowBuilder/` | 5173 | Admin UI: tenant settings, visual flow editor, browser call tester |

Start everything with `.\run_all.ps1` from the project root (mic-based
testing) or `.\run_all_browser.ps1` (browser-based testing via Flow
Builder's Call Test tab - no physical mic needed). Both free ports
8000-8005 (+ 5173 for the browser variant), launch each service in its
own window via `start_*.ps1`, and wait for each to accept connections.

### Call path

```
Caller mic
  -> Orchestrator (ws://8001/ws/call?token=...&tenant_id=...)
     -> STT Service (ws://8000/ws/transcribe)  -> Deepgram
     -> NLU Service (http://8002/reply/stream) -> OpenRouter -> Claude
     -> TTS Service (ws://8003/ws/synthesize)  -> Piper
  <- streamed audio back to caller
```

## Key design decisions (and why)

**Provider wrappers.** Each service has exactly one file that knows which
vendor is behind it: `stt_client.py`, `nlu_client.py`, `tts_client.py`,
`tenant_store.py`. Swapping Deepgram for another STT, or Piper for Cartesia,
means rewriting that one file. Nothing else imports the vendor SDK.

**Streaming everywhere.** NLU streams token deltas; those are chunked into
complete sentences (`sentence_chunker.py`) and sent to TTS as each sentence
finishes, so the bot starts speaking sentence 1 while the LLM is still
generating sentence 2. `PlaybackClock` in `orchestrator_service.py` tracks
when audio will actually finish playing rather than sleeping per sentence -
sleeping per sentence inserted an audible gap while the next one
synthesized.

**Barge-in is client-first.** `local_vad.py` (pure Python, energy-based)
detects speech in ~100ms on the client and flushes its own playback buffer
immediately, without waiting for a server round trip. The server is told in
parallel so it can cancel generation and reconnect TTS. STT's own
`speech_started` is available as a backstop but is OFF by default
(`STT_BARGE_IN=false`) - it fired dozens of spurious events per call.

Pure-Python VAD rather than `webrtcvad` because this machine's Application
Control policy blocks unsigned native extensions (it blocked Piper's
`espeakbridge.dll` until the policy was relaxed).

**No echo cancellation.** Local VAD hears the bot's own voice on speakers.
Headphones required for the mic test client. A browser client would get AEC
free via `getUserMedia({echoCancellation: true})`; real phone calls handle
it at the network/handset level.

**Flows are graphs, executed in-process.** See below. Flow *definitions*
live in the Tenant Config Service (config, and storage already exists).
Flow *execution* lives in `Orchestrator/flow_engine.py` as a module, not a
separate service - it's a state machine over call state the Orchestrator
already owns, and a network hop per turn would sit on the latency-critical
path.

## Flow model

A flow is a directed graph. Nodes:

| Type | Does |
|---|---|
| `collect` | Gathers `fields` from the caller, optional `confirm`, then `next` |
| `branch` | Evaluates `branches` in order, takes the first match |
| `action` | Calls `connector`.`operation`, result lands in values via `result_key`, has `on_error` |
| `say` | Speaks `text` with `{field}` placeholders, then `next` |
| `handoff` | Transfer to a human, ends the flow |
| `end` | Stop |

The division that keeps this from being an IVR: **within** a node the LLM is
free (phrases questions naturally, accepts several answers at once, handles
digressions); **between** nodes the graph is deterministic (the engine
evaluates conditions against collected values; the model gets no say).

The model is never asked "do you have enough to book this?" - that is
answered by checking which required fields are empty. That is what makes
"always collect a phone number" a guarantee rather than a tendency.

Conditions are structured data (`{"field": "x", "op": "eq", "value": "y"}`),
not expression strings - no parser, no `eval`, and a builder UI can render
them as dropdowns directly.

Field extraction uses LLM tool calling in the same streaming call as the
reply (one round trip, not two). Tool call arguments arrive as fragments
that must be reassembled by index - see `nlu_client.get_reply_stream`.

**Entities - "which branch/doctor/session?"** A `collect` field can name an
`entity_type` (e.g. `"branch"`) instead of a hardcoded `options` list; its
choices come from the tenant's `entities` (Tenant Config, managed via the
Flow Builder's Entities tab) and stay current as the tenant adds or renames
one - `orchestrator_service.inject_entity_options` fills `options` in per
call, so `flow_engine.py` never learns entities exist at all, it just sees
an ordinary enum field. Once the caller picks one,
`orchestrator_service.stamp_entity_ids` resolves the spoken label (or an
alias) to the entity's stable id and stores it as `_{field}_id` - e.g.
`_branch_id` - underscore-prefixed so it never leaks into a spoken
`{field}` placeholder or the LLM's "already collected" summary. An action
node can name one of these fields via `entity_field` so the Connector
Gateway looks up settings scoped to that specific entity (its own calendar
ID) rather than the tenant as a whole - see
`ConnectorGateway/README.md`'s "Per-tenant connector settings" section.

Graphs are validated on save (`validate_graph`): dangling gotos, unreachable
nodes, branches with no arms, actions missing a connector. Legacy flat flows
(a `collect` list plus an `action`) auto-convert to graphs on load.

## Storage

Tenant Config uses SQLAlchemy so the database is a connection-string change:

```
MySQL (current): mysql+pymysql://user:pass@localhost:3306/vapilu
PostgreSQL:      postgresql+psycopg://user:pass@localhost:5432/vapilu
SQLite:          sqlite:///tenants.db
```

Two tables, both storing config as a single JSON column so adding a field to
the pydantic schema needs no migration:

- `tenants` — `tenant_id` (PK, VARCHAR 64), `config` (JSON)
- `flows` — `flow_id` (PK), `tenant_id` (indexed), `active`, `config` (JSON)

Leaving `TENANT_DB_URL` unset falls back to JSON files.

## Current state

**Working:** full voice loop (mic -> transcript -> LLM -> speech), barge-in
with resume, conversation memory within a call, per-tenant greeting and
system prompt, graph flows with branching and validation. A visual flow
builder / admin UI (`FlowBuilder/`) covers tenant settings, flow editing,
and a browser-based call tester. Action nodes call a real Connector
Gateway (`ConnectorGateway/`, port 8005) - `drive_flow` in
`orchestrator_service.py` used to fake success; now it makes a real HTTP
call and the flow's `on_error` path fires on a real failure, not just a
theoretical one.

**Real but mock-backed:** the only connector registered so far
(`connectors/mock_booking.py`, `CONNECTOR_ID = "booking"`) is a real
in-memory implementation - genuine conflict-checking, tenant-scoped, a
day really does fill up - but there's no actual calendar behind it yet.
The Gateway is a generic plugin registry (see `ConnectorGateway/README.md`)
specifically so a real connector (Google Calendar, Cal.com, a CRM) is a
new file plus one registry line, not a rewrite - nothing in the
Orchestrator or flow engine needs to change when one lands.

Each connector can have per-tenant settings (an API key, a calendar ID),
stored in the Gateway's own DB-or-JSON-file store
(`connector_config_store.py`, same dual-backend shape as
`tenant_store.py`) rather than in Tenant Config - see
`ConnectorGateway/README.md`'s "Per-tenant connector settings" section.
`/call` merges a tenant's config into `values["_config"]` before invoking
a connector, so a connector reads its own settings without any
Orchestrator involvement. Manageable per tenant via the Flow Builder's
Connectors tab, or directly through
`/connectors/{id}/tenants/{id}/config`.

**Not built:** Channel Gateway (telephony), Session Store (Redis),
Outbound Scheduler, Escalation service, Analytics, Admin API auth (the
Flow Builder is still gated by the same single shared token as everything
else - see "Known gaps" below - plus a dummy client-side login screen
that doesn't check credentials against anything real).

## Known gaps that matter

**Auth is a single shared token per service.** Every service checks one
secret from its `.env`. This is fine while only the developer has access.
It is NOT safe to expose to tenants: one token grants full access to all
tenants' data, so a tenant with the token could read and edit any other
tenant's flows. A UI could hide that; curl would bypass the UI in seconds.
**Real per-user auth with tenant scoping must be built server-side before
any tenant logs in.** This is the intended next-but-one piece.

**Microphone signal quality.** `calibrate_vad.py` recommended a threshold
of 93 on the dev machine, which is very low - it suggests either low mic
gain or speech and background noise sitting close together. Worth raising
Windows input gain and re-running calibration before tuning VAD further; no
threshold works if the two overlap.

**Piper voice quality** is noticeably synthetic. Fine for development. If
"sounds human" becomes the priority, rewrite `tts_client.py` for Cartesia
(~80ms to first audio) or Deepgram Aura-2 (same vendor as STT). Note Piper's
maintained fork is GPL-3.0, which is worth reviewing before commercial
distribution.

**Latency knobs not yet tried:** `NLU_MODEL=anthropic/claude-haiku-4.5` in
`NLU/.env` (Haiku is faster than Sonnet; untested), and caching the
greeting's synthesized audio at startup rather than re-synthesizing per
call.

## Environment notes (this machine)

Windows with an Application Control policy that has blocked things before:

- Run uvicorn as `python -m uvicorn ...`, never the bare `uvicorn.exe`
- `Unblock-File` any downloaded `.ps1` before running it
- PowerShell scripts must be ASCII-only and saved with a UTF-8 BOM, or
  Windows PowerShell 5.1 mangles them
- Health checks use raw TCP against `127.0.0.1`, not HTTP against
  `localhost` - HTTP from PowerShell was being blocked or misrouted while
  browsers worked fine
- Each project has its own venv; check with
  `python -c "import sys; print(sys.prefix)"` when imports fail unexpectedly

## Conventions worth keeping

- Every service: `/health` endpoint, shared-token auth via query param or
  body, structured logging with a short connection id (`[a1b2c3d4]`)
- Downstream failures degrade rather than kill the call: NLU unreachable ->
  fallback message; TTS unreachable -> text still flows; tenant lookup
  fails -> generic defaults
- Comments explain *why*, especially where something non-obvious was the
  fix for a real bug (the flow stage check outside the extraction branch;
  the playback clock; the non-blocking TTS close)
