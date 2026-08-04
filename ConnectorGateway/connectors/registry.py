"""
Explicit registry, not filesystem auto-discovery - adding a connector means
adding one line here, and it's obvious from reading this file what's
available. Auto-scanning connectors/*.py would "just work" too, but also
silently registers anything dropped in the folder, including a
work-in-progress file someone forgot isn't ready.
"""

from . import mock_booking
from .base import Operation

_MODULES = [mock_booking]

REGISTRY: dict[str, dict[str, Operation]] = {m.CONNECTOR_ID: m.OPERATIONS for m in _MODULES}


def get_operation(connector: str, operation: str) -> Operation | None:
    return REGISTRY.get(connector, {}).get(operation)


def list_connectors() -> dict[str, list[str]]:
    return {connector_id: sorted(ops.keys()) for connector_id, ops in REGISTRY.items()}
