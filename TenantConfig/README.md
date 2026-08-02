# Tenant Config Service

Per-business settings, so one deployment can serve many businesses without
code changes. This is the service that makes the bot "generic" in the sense
of the original goal - everything a business wants to customize lives here
as data instead of as a hardcoded literal in the Orchestrator.

## What moved here from code

| Was hardcoded in | Now configured per tenant |
|---|---|
| Orchestrator (`greeting_text`) | `greeting` |
| NLU service (`DEFAULT_SYSTEM_PROMPT`) | `system_prompt_extra` (appended to the base prompt) |
| Nowhere - didn't exist | business hours, escalation phone, capabilities, enabled connectors |

## Storage

Two interchangeable backends, chosen by `TENANT_DB_URL`:

- **SQL** (MySQL now, Postgres later) via SQLAlchemy
- **JSON files** as a zero-setup fallback when `TENANT_DB_URL` is unset

Switching databases is a connection-string change, nothing more:

```
MySQL:      mysql+pymysql://user:password@localhost:3306/vapilu
PostgreSQL: postgresql+psycopg://user:password@localhost:5432/vapilu
SQLite:     sqlite:///tenants.db
```

The table it creates is identical across all three:

```sql
CREATE TABLE tenants (
    tenant_id VARCHAR(64) NOT NULL,
    config JSON NOT NULL,
    PRIMARY KEY (tenant_id)
)
```

**Why one JSON column instead of a column per setting:** adding a field to
`tenant_config.py` then needs no migration - old rows simply lack the key,
and pydantic fills in the default when loading. The tradeoff is that you
can't index or query individual settings. If "find all tenants with booking
enabled" ever needs to be fast, promote that one field to a real column
then; the rest can stay in JSON.

### MySQL setup

Create the database once (the table itself is created automatically on
first run):

```sql
CREATE DATABASE vapilu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

`utf8mb4` matters if any tenant config might contain non-English text or
emoji - MySQL's older `utf8` can't store them.

## Setup

```
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `TENANT_DB_URL` - your MySQL connection string (create the database first,
  see MySQL setup above). Or comment it out to use JSON files instead.
- `TENANT_SERVICE_TOKEN` - a random string

Then run:

```
uvicorn tenant_service:app --reload --port 8004
```

## Create some tenants

```
python seed_tenants.py
```

This creates two realistic examples (a bike repair shop and a dental clinic)
so you can hear how differently the same bot behaves with different configs.
Look at `seed_tenants.py` to see what a real config contains - especially
`system_prompt_extra`, which is where most of the per-business behavior
actually comes from.

## Try it

In the Orchestrator's `.env`, set:

```
TENANT_ID=bike-shop
```

Then run a call. The bot should greet you as Omar's Bicycle Repair, know the
tune-up price, and decline to sell you a new bike. Change to
`TENANT_ID=dental-clinic`, restart the call, and it's a dental receptionist
that refuses to give medical advice - same code, different config.

Leave `TENANT_ID` unset and it falls back to generic defaults.

## API

```
GET    /health
GET    /tenants?token=...                 -> {"tenant_ids": [...]}
GET    /tenants/{tenant_id}?token=...      -> full config
PUT    /tenants/{tenant_id}?token=...      -> create or replace (body = full config)
DELETE /tenants/{tenant_id}?token=...      -> delete
```

## Notes

- **Failure is non-fatal.** If this service is down or a tenant_id is
  unknown, the Orchestrator logs it and falls back to generic defaults
  rather than refusing the call. A config lookup problem shouldn't mean a
  customer can't reach anyone.
- **Adding a new setting**: add it to `tenant_config.py` with a default.
  Existing stored tenants don't have the field, and pydantic fills the
  default in automatically - no migration needed.
- **`voice` and `business_hours` are stored but not yet used.** The TTS
  service doesn't do per-tenant voices yet, and nothing checks whether the
  business is currently open. Both are wired for when you want them.
