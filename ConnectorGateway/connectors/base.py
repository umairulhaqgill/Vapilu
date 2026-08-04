"""
The contract every connector implements. This is the whole point of the
Gateway: it stays generic (a connector name and operation name, dispatched
against a registry) while every business-specific or vendor-specific thing
lives inside one connector module - same "one file, one vendor" shape as
stt_client.py, nlu_client.py, tts_client.py, tenant_store.py.

A connector module exposes:
    CONNECTOR_ID: str                          - the name flows reference
    OPERATIONS: dict[str, Operation]            - operation name -> handler

An Operation is `async def handler(values: dict) -> dict`, where `values`
is the flow's full collected-values dict (not just fields this operation
cares about - the connector picks out what it needs by name) and the
return value is whatever should land in the flow's result_key.

Raise ConnectorError for an expected, meaningful failure (a slot's taken,
a required field is missing) - the caller sees `ok: false` and the flow's
on_error path, not a 500. Any other exception is treated as unexpected and
logged, but still degrades to on_error rather than killing the call - same
"downstream failures degrade" convention as every other service here.
"""

from typing import Awaitable, Callable

Operation = Callable[[dict], Awaitable[dict]]


class ConnectorError(Exception):
    """An expected failure a connector wants reported back to the flow (as
    ok=false), not raised as a server error."""
