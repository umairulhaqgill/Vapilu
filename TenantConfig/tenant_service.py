"""
Tenant Config Service - per-business settings, so one deployment can serve
many businesses without code changes.

  Orchestrator  --HTTP GET-->  This service  -->  tenants/*.json

Everything that used to be a hardcoded literal (greeting text, system
prompt, voice) lives here instead, keyed by tenant_id. The Orchestrator
loads a tenant's config at the start of each call and behaves accordingly.

Run with:
    uvicorn tenant_service:app --reload --port 8004
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from flow_config import FlowConfig
from tenant_config import TenantConfig
from tenant_store import create_store

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tenant-config")

app = FastAPI(title="Tenant Config Service")

# Only the Flow Builder (FlowBuilder/, a browser app) needs CORS - the
# Orchestrator talks to this service server-to-server, where CORS doesn't
# apply. Vite's dev server binds both hostnames; browsers treat them as
# different origins, so both are listed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# TENANT_DB_URL decides the backend. Set it for MySQL/Postgres; leave it
# unset to fall back to JSON files (no database needed).
store = create_store(
    db_url=os.environ.get("TENANT_DB_URL"),
    data_dir=os.environ.get("TENANT_DATA_DIR", "tenants"),
)
logger.info("Tenant storage backend: %s", type(store).__name__)

TENANT_SERVICE_TOKEN = os.environ.get("TENANT_SERVICE_TOKEN")
if not TENANT_SERVICE_TOKEN:
    logger.warning(
        "TENANT_SERVICE_TOKEN is not set - this service is UNAUTHENTICATED. "
        "Fine for local testing, not for anything public."
    )


def check_token(token: str | None):
    if TENANT_SERVICE_TOKEN and token != TENANT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid token")


@app.get("/health")
async def health():
    return {"status": "ok", "tenants": len(store.list_ids())}


@app.get("/tenants")
async def list_tenants(token: str | None = None):
    check_token(token)
    return {"tenant_ids": store.list_ids()}


@app.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str, token: str | None = None):
    check_token(token)
    try:
        config = store.get(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if config is None:
        raise HTTPException(status_code=404, detail=f"No tenant with id {tenant_id!r}")
    return config.model_dump()


@app.put("/tenants/{tenant_id}")
async def upsert_tenant(tenant_id: str, config: TenantConfig, token: str | None = None):
    """Creates or replaces a tenant's config."""
    check_token(token)
    if config.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail=f"tenant_id in URL ({tenant_id!r}) doesn't match body ({config.tenant_id!r})",
        )
    try:
        saved = store.save(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Saved config for tenant %s", tenant_id)
    return saved.model_dump()


@app.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, token: str | None = None):
    check_token(token)
    try:
        deleted = store.delete(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No tenant with id {tenant_id!r}")
    logger.info("Deleted tenant %s", tenant_id)
    return {"deleted": tenant_id}


# --- Flows ---

@app.get("/tenants/{tenant_id}/flows")
async def list_flows(tenant_id: str, token: str | None = None, include_inactive: bool = False):
    """
    Flows for a tenant. Active only by default - that's what the
    Orchestrator calls at the start of every call. Management UIs (the
    flow builder) pass include_inactive=true to see and re-activate
    disabled flows too.
    """
    check_token(token)
    try:
        flows = store.get_flows(tenant_id, include_inactive=include_inactive)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"flows": [f.model_dump() for f in flows]}


@app.get("/flows/{flow_id}")
async def get_flow(flow_id: str, token: str | None = None):
    check_token(token)
    try:
        flow = store.get_flow(flow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if flow is None:
        raise HTTPException(status_code=404, detail=f"No flow with id {flow_id!r}")
    return flow.model_dump()


@app.put("/flows/{flow_id}")
async def upsert_flow(flow_id: str, flow: FlowConfig, token: str | None = None):
    check_token(token)
    if flow.flow_id != flow_id:
        raise HTTPException(
            status_code=400,
            detail=f"flow_id in URL ({flow_id!r}) doesn't match body ({flow.flow_id!r})",
        )
    # Validate the graph before storing. A dangling goto or unreachable
    # node otherwise only surfaces mid-call, which is the worst time.
    problems = flow.validate_graph()
    if problems:
        raise HTTPException(status_code=400, detail={"graph_problems": problems})

    try:
        saved = store.save_flow(flow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Saved flow %s for tenant %s", flow_id, flow.tenant_id)
    return saved.model_dump()


@app.delete("/flows/{flow_id}")
async def delete_flow(flow_id: str, token: str | None = None):
    check_token(token)
    try:
        deleted = store.delete_flow(flow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No flow with id {flow_id!r}")
    logger.info("Deleted flow %s", flow_id)
    return {"deleted": flow_id}
