"""
Tenant storage.

Two interchangeable backends behind one interface:

  - SqlTenantStore  - MySQL now, Postgres/SQLite later. Uses SQLAlchemy, so
                      switching databases is a connection-string change
                      rather than a rewrite.
  - JsonTenantStore - flat files, no database needed. Useful for quick local
                      work or if you want to hand-edit configs in a text
                      editor.

Which one you get is decided by TENANT_DB_URL (see create_store at the
bottom). Everything above this file - the service, the Orchestrator - only
sees the TenantStore interface and has no idea which is in use.

Schema note: the config is stored as a single JSON column rather than one
column per setting. That's deliberate. Adding a new field to
tenant_config.py then needs no migration: old rows simply lack the key, and
pydantic fills in the default when loading. The cost is that you can't
index or query on individual settings - if you later need "find all tenants
with booking enabled" to be fast, promote that specific field to a real
column then.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy import JSON, Boolean, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from flow_config import FlowConfig
from tenant_config import TenantConfig


class TenantStore(ABC):
    """The interface every backend implements."""

    @abstractmethod
    def get(self, tenant_id: str) -> TenantConfig | None: ...

    @abstractmethod
    def save(self, config: TenantConfig) -> TenantConfig: ...

    @abstractmethod
    def delete(self, tenant_id: str) -> bool: ...

    @abstractmethod
    def list_ids(self) -> list[str]: ...

    # --- Flows ---

    @abstractmethod
    def get_flows(self, tenant_id: str, include_inactive: bool = False) -> list[FlowConfig]:
        """Flows for a tenant. Active only by default; called at the start of
        every call, where inactive flows must never be selectable. Pass
        include_inactive=True for management UIs that need to see (and
        re-activate) disabled flows too."""

    @abstractmethod
    def get_flow(self, flow_id: str) -> FlowConfig | None: ...

    @abstractmethod
    def save_flow(self, flow: FlowConfig) -> FlowConfig: ...

    @abstractmethod
    def delete_flow(self, flow_id: str) -> bool: ...

    @staticmethod
    def _validate_id(tenant_id: str):
        """
        Rejects ids that could escape the storage location or break queries.
        Matters most for the JSON backend (where a tenant_id becomes a file
        path) but applied everywhere so both backends behave identically.
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        if "/" in tenant_id or "\\" in tenant_id or ".." in tenant_id:
            raise ValueError(f"Invalid tenant_id: {tenant_id!r}")
        if len(tenant_id) > 64:
            raise ValueError("tenant_id cannot be longer than 64 characters")


# --------------------------------------------------------------------------
# SQL backend
# --------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class TenantRow(Base):
    __tablename__ = "tenants"

    # VARCHAR(64) rather than an unbounded string: MySQL can't index TEXT
    # columns without an explicit prefix length, and this is the primary key.
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # SQLAlchemy's JSON type maps to the right native type per database -
    # JSON on MySQL, JSONB-capable JSON on Postgres, TEXT on SQLite.
    config: Mapped[dict] = mapped_column(JSON, nullable=False)


class FlowRow(Base):
    __tablename__ = "flows"

    flow_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Indexed separately from the JSON blob because "all flows for tenant X"
    # runs on every single call - that one has to be a real query, not a
    # scan of JSON documents.
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)


class SqlTenantStore(TenantStore):
    def __init__(self, db_url: str, echo: bool = False):
        # pool_pre_ping avoids the classic MySQL "server has gone away" error
        # after a connection has sat idle - MySQL closes idle connections and
        # SQLAlchemy would otherwise hand out a dead one.
        self._engine = create_engine(db_url, echo=echo, pool_pre_ping=True)
        self._Session = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    def get(self, tenant_id: str) -> TenantConfig | None:
        self._validate_id(tenant_id)
        with self._Session() as session:
            row = session.get(TenantRow, tenant_id)
            if row is None:
                return None
            return TenantConfig(**row.config)

    def save(self, config: TenantConfig) -> TenantConfig:
        self._validate_id(config.tenant_id)
        with self._Session() as session:
            row = session.get(TenantRow, config.tenant_id)
            if row is None:
                row = TenantRow(tenant_id=config.tenant_id, config=config.model_dump())
                session.add(row)
            else:
                row.config = config.model_dump()
            session.commit()
        return config

    def delete(self, tenant_id: str) -> bool:
        self._validate_id(tenant_id)
        with self._Session() as session:
            row = session.get(TenantRow, tenant_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def list_ids(self) -> list[str]:
        with self._Session() as session:
            return sorted(session.scalars(select(TenantRow.tenant_id)).all())

    def get_flows(self, tenant_id: str, include_inactive: bool = False) -> list[FlowConfig]:
        self._validate_id(tenant_id)
        with self._Session() as session:
            conditions = [FlowRow.tenant_id == tenant_id]
            if not include_inactive:
                conditions.append(FlowRow.active.is_(True))
            rows = session.scalars(select(FlowRow).where(*conditions)).all()
            return [FlowConfig(**row.config) for row in rows]

    def get_flow(self, flow_id: str) -> FlowConfig | None:
        self._validate_id(flow_id)
        with self._Session() as session:
            row = session.get(FlowRow, flow_id)
            return FlowConfig(**row.config) if row else None

    def save_flow(self, flow: FlowConfig) -> FlowConfig:
        self._validate_id(flow.flow_id)
        self._validate_id(flow.tenant_id)
        with self._Session() as session:
            row = session.get(FlowRow, flow.flow_id)
            if row is None:
                row = FlowRow(
                    flow_id=flow.flow_id,
                    tenant_id=flow.tenant_id,
                    active=flow.active,
                    config=flow.model_dump(),
                )
                session.add(row)
            else:
                row.tenant_id = flow.tenant_id
                row.active = flow.active
                row.config = flow.model_dump()
            session.commit()
        return flow

    def delete_flow(self, flow_id: str) -> bool:
        self._validate_id(flow_id)
        with self._Session() as session:
            row = session.get(FlowRow, flow_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True


# --------------------------------------------------------------------------
# JSON file backend
# --------------------------------------------------------------------------

class JsonTenantStore(TenantStore):
    def __init__(self, data_dir: str = "tenants"):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, tenant_id: str) -> Path:
        self._validate_id(tenant_id)
        return self._dir / f"{tenant_id}.json"

    def get(self, tenant_id: str) -> TenantConfig | None:
        path = self._path(tenant_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return TenantConfig(**json.load(f))

    def save(self, config: TenantConfig) -> TenantConfig:
        with open(self._path(config.tenant_id), "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2)
        return config

    def delete(self, tenant_id: str) -> bool:
        path = self._path(tenant_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def _flow_dir(self) -> Path:
        d = self._dir / "flows"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_flows(self, tenant_id: str, include_inactive: bool = False) -> list[FlowConfig]:
        self._validate_id(tenant_id)
        flows = []
        for path in self._flow_dir().glob("*.json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("tenant_id") != tenant_id:
                continue
            if not include_inactive and not data.get("active", True):
                continue
            flows.append(FlowConfig(**data))
        return flows

    def get_flow(self, flow_id: str) -> FlowConfig | None:
        self._validate_id(flow_id)
        path = self._flow_dir() / f"{flow_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return FlowConfig(**json.load(f))

    def save_flow(self, flow: FlowConfig) -> FlowConfig:
        self._validate_id(flow.flow_id)
        self._validate_id(flow.tenant_id)
        with open(self._flow_dir() / f"{flow.flow_id}.json", "w", encoding="utf-8") as f:
            json.dump(flow.model_dump(), f, indent=2)
        return flow

    def delete_flow(self, flow_id: str) -> bool:
        self._validate_id(flow_id)
        path = self._flow_dir() / f"{flow_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True


# --------------------------------------------------------------------------

def create_store(db_url: str | None, data_dir: str = "tenants") -> TenantStore:
    """
    Picks a backend. If db_url is set, uses SQL; otherwise falls back to
    JSON files so the service still runs with no database configured.

    Connection string examples:
      MySQL:      mysql+pymysql://user:password@localhost:3306/vapilu
      Postgres:   postgresql+psycopg://user:password@localhost:5432/vapilu
      SQLite:     sqlite:///tenants.db

    Switching between them is only ever this string - no code changes.
    """
    if db_url:
        return SqlTenantStore(db_url)
    return JsonTenantStore(data_dir)
