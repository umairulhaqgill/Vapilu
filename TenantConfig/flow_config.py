"""
Flow definition schema.

A flow is a tenant-authored task the bot can complete: collect some fields,
confirm them, then perform an action. The tenant defines WHAT must be
collected; the LLM decides HOW to ask for it conversationally.

The important property: the model never decides whether it has enough
information. The flow engine checks which required fields are still empty,
deterministically, and steers the model toward the gaps. That's what makes
"always get a phone number before booking" a guarantee rather than a
tendency.
"""

from pydantic import BaseModel, Field


class FlowField(BaseModel):
    name: str
    # Plain-language description of what to ask for. Goes into the prompt,
    # so write it the way you'd explain it to a new receptionist:
    # "a callback number" reads better than "phone_number".
    prompt: str
    required: bool = True

    # Optional format check. Named "format" rather than "validate" because
    # "validate" collides with a pydantic BaseModel attribute. Unrecognized
    # values are ignored rather than erroring, so adding a new checker later
    # can't break flows already stored.
    #   "phone"  - digits, reasonable length
    #   "date"   - anything dateutil can parse
    #   "email"  - has an @ and a dot after it
    #   "number" - numeric
    format: str | None = None

    # If set, the value must be one of these. Useful for constraining the
    # LLM to values a downstream API will actually accept.
    options: list[str] | None = None


class FlowAction(BaseModel):
    """What to do once every required field is collected and confirmed."""
    connector: str          # which connector to call, e.g. "booking"
    operation: str          # which operation on it, e.g. "create_booking"


class FlowConfig(BaseModel):
    flow_id: str
    tenant_id: str

    # Plain-language description of when this flow applies. The LLM uses
    # this to decide whether the caller is asking for this task, so write
    # it as an intent: "caller wants to book a repair appointment".
    trigger: str

    collect: list[FlowField] = Field(default_factory=list)

    # Read the collected values back before acting. Use {field_name}
    # placeholders. Strongly recommended for anything that writes to a real
    # system - STT mistranscriptions are common, and this is the cheapest
    # place to catch them.
    confirm: str | None = None

    action: FlowAction | None = None
    on_success: str | None = None
    on_failure: str | None = None

    active: bool = True
