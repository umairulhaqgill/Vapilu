"""
In-memory booking connector - no real calendar behind it. This exists to
prove the Gateway's plumbing end-to-end (flow collects values -> action
node -> this connector -> result lands in result_key -> flow continues)
without needing real credentials for anything yet.

Deliberately still does real conflict-checking (a day fills up after
enough bookings) rather than always succeeding - "prove it end-to-end"
means proving the failure path (on_error) too, not just the happy path.

Swap-out story: a real calendar connector (Google Calendar, Cal.com,
whatever) is a separate module with the same CONNECTOR_ID and OPERATIONS
shape - registered instead of this one in registry.py, no changes needed
anywhere else (not the flow model, not the Orchestrator, not other
connectors).

Known limitation: `preferred_day` is caller-spoken free text ("next
Tuesday", "August 5th") captured via LLM extraction, not a normalized
date. This mock treats the raw string as the slot key, so "Tuesday" and
"next Tuesday" are different slots even if they mean the same day - fine
for proving the plumbing, not fine for a real connector, which would need
real date parsing (and almost certainly a timezone, from the tenant's
business_hours).

Reads `values["_config"]["max_per_slot"]` (per-tenant, set via the
Connector Gateway's config endpoints / the Flow Builder's Connectors tab)
- not because a mock needs configurability, but to prove that a tenant's
stored connector config genuinely reaches the connector on every call,
not just that the plumbing exists unused.
"""

import uuid

from .base import ConnectorError

CONNECTOR_ID = "booking"

DEFAULT_MAX_PER_SLOT = 3

# tenant_id -> slot_key -> list of {"ref": str, "values": dict}
# Keyed by tenant too - two different businesses' calendars must never
# collide just because both happened to get "Tuesday" as a slot key.
_bookings: dict[str, dict[str, list[dict]]] = {}


def _slot_key(values: dict) -> str | None:
    day = values.get("preferred_day") or values.get("date")
    if not day:
        return None
    return str(day).strip().lower()


def _max_per_slot(values: dict) -> int:
    config = values.get("_config") or {}
    try:
        return int(config.get("max_per_slot", DEFAULT_MAX_PER_SLOT))
    except (TypeError, ValueError):
        return DEFAULT_MAX_PER_SLOT


async def create_booking(values: dict) -> dict:
    tenant_id = values.get("_tenant_id", "")
    slot = _slot_key(values)
    if not slot:
        raise ConnectorError("no preferred day given - can't book without one")

    tenant_bookings = _bookings.setdefault(tenant_id, {})
    existing = tenant_bookings.setdefault(slot, [])
    if len(existing) >= _max_per_slot(values):
        raise ConnectorError(f"{slot} is fully booked - ask the caller for a different day")

    ref = f"BK-{uuid.uuid4().hex[:6].upper()}"
    existing.append({"ref": ref, "values": values})
    return {"booking_ref": ref, "status": "confirmed", "scheduled_for": values.get("preferred_day", slot)}


async def check_availability(values: dict) -> dict:
    tenant_id = values.get("_tenant_id", "")
    slot = _slot_key(values)
    if not slot:
        raise ConnectorError("no day given to check availability for")

    count = len(_bookings.get(tenant_id, {}).get(slot, []))
    remaining = max(0, _max_per_slot(values) - count)
    return {"available": remaining > 0, "slots_remaining": remaining, "day": values.get("preferred_day", slot)}


async def cancel_booking(values: dict) -> dict:
    tenant_id = values.get("_tenant_id", "")
    ref = values.get("booking_ref")
    if not ref:
        raise ConnectorError("no booking_ref given to cancel")

    for slot_bookings in _bookings.get(tenant_id, {}).values():
        for entry in slot_bookings:
            if entry["ref"] == ref:
                slot_bookings.remove(entry)
                return {"status": "cancelled", "booking_ref": ref}
    raise ConnectorError(f"no booking found with ref {ref}")


OPERATIONS = {
    "create_booking": create_booking,
    "check_availability": check_availability,
    "cancel_booking": cancel_booking,
}
