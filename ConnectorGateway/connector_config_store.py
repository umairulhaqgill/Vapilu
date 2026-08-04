"""
Per-tenant, per-connector settings storage - an OAuth token, a calendar
ID, a CRM API key, whatever a given connector needs to actually call its
real backend. Deliberately owned here, not in the Tenant Config Service:
these are connector-shaped (wildly different fields per connector) and
credential-shaped (more sensitive than business_name/greeting), not
business config - see ConnectorGateway/README.md.

Same two-backend shape as TenantConfig/tenant_store.py, for the same
reasons: SQL now (MySQL, same "vapilu" database, a new table), JSON files
as a zero-setup fallback, switching is a connection-string change. Which
one you get is decided by CONNECTOR_DB_URL (see create_store below).

Schema note: config is one JSON column per (tenant_id, connector_id) pair
rather than a column per setting - same reasoning as tenant_store.py: a
connector's settings shape can change (or a new connector with a totally
different shape can be added) with no migration.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy import JSON, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class ConnectorConfigStore(ABC):
    """The interface every backend implements."""

    @abstractmethod
    def get(self, tenant_id: str, connector_id: str) -> dict:
        """Always returns a dict - {} if nothing's been configured yet,
        never None. A connector operation can merge this straight into
        its call without a null check."""

    @abstractmethod
    def save(self, tenant_id: str, connector_id: str, config: dict) -> dict: ...

    @abstractmethod
    def delete(self, tenant_id: str, connector_id: str) -> bool: ...

    @staticmethod
    def _validate_id(value: str, label: str):
        """Same guard as TenantStore._validate_id - matters most for the
        JSON backend, where these become part of a file path, but applied
        to both backends so they behave identically."""
        if not value or not value.strip():
            raise ValueError(f"{label} cannot be empty")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"Invalid {label}: {value!r}")
        if len(value) > 64:
            raise ValueError(f"{label} cannot be longer than 64 characters")


# --------------------------------------------------------------------------
# SQL backend
# --------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class ConnectorConfigRow(Base):
    __tablename__ = "connector_configs"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    connector_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)


class SqlConnectorConfigStore(ConnectorConfigStore):
    def __init__(self, db_url: str, echo: bool = False):
        self._engine = create_engine(db_url, echo=echo, pool_pre_ping=True)
        self._Session = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    def get(self, tenant_id: str, connector_id: str) -> dict:
        self._validate_id(tenant_id, "tenant_id")
        self._validate_id(connector_id, "connector_id")
        with self._Session() as session:
            row = session.get(ConnectorConfigRow, (tenant_id, connector_id))
            return dict(row.config) if row else {}

    def save(self, tenant_id: str, connector_id: str, config: dict) -> dict:
        self._validate_id(tenant_id, "tenant_id")
        self._validate_id(connector_id, "connector_id")
        with self._Session() as session:
            row = session.get(ConnectorConfigRow, (tenant_id, connector_id))
            if row is None:
                row = ConnectorConfigRow(tenant_id=tenant_id, connector_id=connector_id, config=config)
                session.add(row)
            else:
                row.config = config
            session.commit()
        return config

    def delete(self, tenant_id: str, connector_id: str) -> bool:
        self._validate_id(tenant_id, "tenant_id")
        self._validate_id(connector_id, "connector_id")
        with self._Session() as session:
            row = session.get(ConnectorConfigRow, (tenant_id, connector_id))
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True


# --------------------------------------------------------------------------
# JSON file backend
# --------------------------------------------------------------------------

class JsonConnectorConfigStore(ConnectorConfigStore):
    def __init__(self, data_dir: str = "connector_configs"):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, tenant_id: str, connector_id: str) -> Path:
        self._validate_id(tenant_id, "tenant_id")
        self._validate_id(connector_id, "connector_id")
        return self._dir / f"{tenant_id}__{connector_id}.json"

    def get(self, tenant_id: str, connector_id: str) -> dict:
        path = self._path(tenant_id, connector_id)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, tenant_id: str, connector_id: str, config: dict) -> dict:
        with open(self._path(tenant_id, connector_id), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return config

    def delete(self, tenant_id: str, connector_id: str) -> bool:
        path = self._path(tenant_id, connector_id)
        if not path.exists():
            return False
        path.unlink()
        return True


def create_store(db_url: str | None, data_dir: str = "connector_configs") -> ConnectorConfigStore:
    """
    Picks a backend. If db_url is set, uses SQL; otherwise falls back to
    JSON files so the service still runs with no database configured.
    Switching between them is only ever this string - no code changes.
    """
    if db_url:
        return SqlConnectorConfigStore(db_url)
    return JsonConnectorConfigStore(data_dir)
