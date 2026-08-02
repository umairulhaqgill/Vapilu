"""
Tenant configuration schema.

This is the contract for what a business can customize about its bot
without anyone touching code. Everything here was previously a hardcoded
literal somewhere in the Orchestrator or NLU service.

Adding a new setting: add it here with a sensible default, and it becomes
optional for existing tenants automatically - their stored configs won't
have the field, and pydantic fills the default in.
"""

from pydantic import BaseModel, Field


class BusinessHours(BaseModel):
    """Simple open/close per weekday. 24h format, local to the business."""
    monday: str | None = "09:00-17:00"
    tuesday: str | None = "09:00-17:00"
    wednesday: str | None = "09:00-17:00"
    thursday: str | None = "09:00-17:00"
    friday: str | None = "09:00-17:00"
    saturday: str | None = None   # None = closed
    sunday: str | None = None

    # Timezone name (e.g. "Asia/Karachi", "America/New_York"). The bot needs
    # this to answer "are you open right now" correctly - server time is
    # meaningless to a caller.
    timezone: str = "UTC"


class TenantConfig(BaseModel):
    tenant_id: str
    business_name: str

    # --- Conversation ---
    greeting: str = "Hello! How can I help you today?"
    # Appended to the base voice-assistant instructions in the NLU service.
    # This is where a business describes itself, its services, its policies -
    # anything the bot should know but that isn't worth a live API call.
    system_prompt_extra: str = ""
    language: str = "en"

    # --- Voice ---
    # Which TTS voice to use. Meaning depends on the TTS provider - for Piper
    # it's a model filename; for a cloud provider it'd be a voice ID.
    voice: str | None = None

    # --- Behavior ---
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    # Phone number to transfer to when the caller asks for a human, or the
    # bot decides it can't help. None = no human handoff available.
    escalation_phone: str | None = None
    # Free-text list of things this bot should be able to handle. Fed to the
    # LLM so it knows its own scope rather than guessing.
    capabilities: list[str] = Field(default_factory=list)

    # --- Integrations (used later by the Connector Gateway) ---
    # Which connectors this tenant has enabled, e.g. ["booking", "orders"].
    # The Connector Gateway will use this to decide what tools to expose.
    enabled_connectors: list[str] = Field(default_factory=list)

    # --- Status ---
    active: bool = True
