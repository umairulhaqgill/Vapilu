"""
Connector Gateway - the generic seam between a flow's `action` nodes and
whatever real backend does the work (a booking system, a calendar, a CRM
lookup). The Orchestrator used to fake this entirely: log what it would
have called and continue the graph as if it succeeded. This is the real
thing.

  Orchestrator  --HTTP POST /call-->  This service  --> a connector module

Deliberately generic: `connector` and `operation` are just strings looked
up in a registry (connectors/registry.py). This service has no idea what
"booking" means - it just dispatches. Every vendor- or business-specific
detail lives inside one connector module, same "one file, one vendor"
shape as stt_client.py / nlu_client.py / tts_client.py / tenant_store.py.
Adding a real Google Calendar connector later means adding one file and
one line in registry.py - nothing here changes.

Split into its own service (rather than a module inside the Orchestrator)
so a slow or misbehaving external API - Google's OAuth token refresh, a
CRM's rate limit - can't sit directly in the same process handling live
call audio. The cost is one extra network hop per action node and a
service to run; see CLAUDE.md for the tradeoff as discussed.

Also owns per-tenant connector settings (connector_config_store.py) - an
OAuth token, a calendar ID, an API key. Deliberately not stored in the
Tenant Config Service: these are connector-shaped, not tenant-shaped, and
credential-shaped, not business-config-shaped - see README.md. Every
/call looks the tenant's config up (via _tenant_id, which the Orchestrator
already sends) and merges it into `values["_config"]` before invoking the
handler, so a connector that needs credentials just reads
`values["_config"]` - no signature change, no Orchestrator involvement.

Run with:
    uvicorn connector_gateway_service:app --reload --port 8005
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from connector_config_store import create_store
from connectors.base import ConnectorError
from connectors.registry import get_operation, list_connectors

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("connector-gateway")

app = FastAPI(title="Connector Gateway")

# Only the Flow Builder (a browser app) needs CORS - the Orchestrator
# talks to this service server-to-server. Regex rather than a fixed
# origin list, same reasoning as the Tenant Config Service: the browser
# can reach the same Vite dev server as localhost, 127.0.0.1, or a LAN IP
# depending on how it's addressed, and a hardcoded IP here would go stale
# on the next DHCP renewal.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://[\w.\-]+:5173$",
    allow_methods=["*"],
    allow_headers=["*"],
)

store = create_store(
    db_url=os.environ.get("CONNECTOR_DB_URL"),
    data_dir=os.environ.get("CONNECTOR_DATA_DIR", "connector_configs"),
)
logger.info("Connector config storage backend: %s", type(store).__name__)

CONNECTOR_GATEWAY_TOKEN = os.environ.get("CONNECTOR_GATEWAY_TOKEN")
if not CONNECTOR_GATEWAY_TOKEN:
    logger.warning(
        "CONNECTOR_GATEWAY_TOKEN is not set - this service is UNAUTHENTICATED. "
        "Fine for local testing, not for anything public."
    )


def check_token(token: str | None):
    if CONNECTOR_GATEWAY_TOKEN and token != CONNECTOR_GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid token")


class CallRequest(BaseModel):
    connector: str
    operation: str
    values: dict = {}
    token: str | None = None


class ConfigBody(BaseModel):
    config: dict


@app.get("/health")
async def health():
    return {"status": "ok", "connectors": list(list_connectors())}


@app.get("/connectors")
async def connectors(token: str | None = None):
    """What's registered and what each one can do - lets a caller (or the
    Flow Builder UI) discover valid connector/operation pairs instead of
    guessing at free-text strings."""
    check_token(token)
    return list_connectors()


@app.get("/connectors/{connector_id}/tenants/{tenant_id}/config")
async def get_connector_config(connector_id: str, tenant_id: str, entity_id: str | None = None, token: str | None = None):
    """entity_id omitted (or None) reads the tenant-wide default config.
    Pass it to read one entity's own settings instead (a specific branch's
    calendar id) - see connector_config_store.py."""
    check_token(token)
    try:
        return {"config": store.get(tenant_id, connector_id, entity_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/connectors/{connector_id}/tenants/{tenant_id}/config")
async def save_connector_config(
    connector_id: str, tenant_id: str, body: ConfigBody, entity_id: str | None = None, token: str | None = None,
):
    check_token(token)
    try:
        saved = store.save(tenant_id, connector_id, body.config, entity_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Saved %s config for tenant %s%s", connector_id, tenant_id,
                f" entity {entity_id}" if entity_id else "")
    return {"config": saved}


@app.delete("/connectors/{connector_id}/tenants/{tenant_id}/config")
async def delete_connector_config(connector_id: str, tenant_id: str, entity_id: str | None = None, token: str | None = None):
    check_token(token)
    try:
        deleted = store.delete(tenant_id, connector_id, entity_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="no config to delete")
    return {"deleted": True}


@app.post("/call")
async def call(request: CallRequest):
    """
    Runs one connector operation. Always returns 200 with an {ok, ...}
    body rather than raising for a connector-level failure (unknown
    connector, unknown operation, or a ConnectorError from the operation
    itself) - the Orchestrator treats any non-ok result the same way, by
    routing the flow's on_error path, and shouldn't need to distinguish
    "the HTTP call failed" from "the operation reported failure".
    """
    check_token(request.token)

    handler = get_operation(request.connector, request.operation)
    if handler is None:
        logger.warning("unknown connector/operation: %s.%s", request.connector, request.operation)
        return {"ok": False, "error": f"unknown connector/operation: {request.connector}.{request.operation}"}

    values = dict(request.values)
    tenant_id = values.get("_tenant_id")
    entity_id = values.get("_entity_id")
    if tenant_id:
        try:
            config = store.get(tenant_id, request.connector)
            # Entity-scoped settings (this one branch's calendar id)
            # override the tenant-wide defaults (a shared API key) rather
            # than replace them outright, so a tenant doesn't have to
            # repeat every shared setting on every entity.
            if entity_id:
                config = {**config, **store.get(tenant_id, request.connector, entity_id)}
            values["_config"] = config
        except ValueError:
            values["_config"] = {}
    else:
        values["_config"] = {}

    logger.info("CALL %s.%s values=%s", request.connector, request.operation, request.values)
    try:
        result = await handler(values)
        return {"ok": True, "result": result}
    except ConnectorError as e:
        logger.info("connector reported failure: %s", e)
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("unexpected error in %s.%s: %s", request.connector, request.operation, e)
        return {"ok": False, "error": "internal connector error"}
