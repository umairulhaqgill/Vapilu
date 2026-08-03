"""
Flow execution.

Tracks which fields a flow still needs and turns that into instructions the
LLM can act on. Deliberately NOT a separate service: this is a state machine
over call state, and the Orchestrator already owns that state in
CallSession. Shipping it back and forth on every turn would put a network
hop in the latency-critical path for no benefit.

The division of labour that makes this reliable:
  - The ENGINE decides what's still missing. Deterministic, checkable.
  - The LLM decides how to ask for it. Natural, flexible.

The model is never asked "do you have enough to book this?" - that question
is answered by looking at which required fields are empty. That's the
difference between "always collects a phone number" being a guarantee
versus a tendency.
"""

import logging
import re
from enum import Enum

logger = logging.getLogger("orchestrator")


class FlowStage(str, Enum):
    COLLECTING = "collecting"    # still gathering required fields
    CONFIRMING = "confirming"    # read values back, waiting for yes/no
    READY = "ready"              # confirmed, action should run
    DONE = "done"                # action ran (or there was none)


def check_format(value: str, fmt: str | None) -> bool:
    """
    Validates a collected value. Unknown format names pass rather than fail -
    so adding a new format to the schema later can't retroactively break
    flows already stored in the database.
    """
    if not fmt or value is None:
        return True
    text = str(value).strip()

    if fmt == "phone":
        digits = re.sub(r"\D", "", text)
        return 7 <= len(digits) <= 15
    if fmt == "email":
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text) is not None
    if fmt == "number":
        try:
            float(text)
            return True
        except ValueError:
            return False
    if fmt == "date":
        # Deliberately permissive: the caller says "next Tuesday" and the
        # LLM normalizes it. Rejecting anything that isn't ISO would fight
        # the way people actually speak. Real date resolution belongs in
        # the connector, which knows the business's calendar.
        return len(text) >= 3

    return True


class FlowRun:
    """One flow, in progress, for one call."""

    def __init__(self, flow: dict):
        self.flow = flow
        self.flow_id = flow.get("flow_id", "unknown")
        self.values: dict[str, str] = {}
        self.stage = FlowStage.COLLECTING
        # Fields the caller gave in a form we couldn't accept. Kept so the
        # LLM can re-ask specifically ("that number seemed short") instead
        # of asking blankly again.
        self.rejected: dict[str, str] = {}

    # --- field state ---

    def fields(self) -> list[dict]:
        return self.flow.get("collect", []) or []

    def missing_required(self) -> list[dict]:
        return [
            f for f in self.fields()
            if f.get("required", True) and f["name"] not in self.values
        ]

    def apply_values(self, extracted: dict) -> dict:
        """
        Records values the LLM extracted from what the caller said.
        Returns the ones that were rejected, so the caller can be told.
        """
        rejected = {}
        known = {f["name"]: f for f in self.fields()}

        for name, value in (extracted or {}).items():
            field = known.get(name)
            if field is None or value in (None, ""):
                continue

            value = str(value).strip()

            if not check_format(value, field.get("format")):
                rejected[name] = value
                logger.info("[flow %s] rejected %s=%r (bad %s)",
                            self.flow_id, name, value, field.get("format"))
                continue

            options = field.get("options")
            if options and value.lower() not in [o.lower() for o in options]:
                rejected[name] = value
                logger.info("[flow %s] rejected %s=%r (not in options)",
                            self.flow_id, name, value)
                continue

            self.values[name] = value
            self.rejected.pop(name, None)

        self.rejected.update(rejected)
        return rejected

    # --- stage transitions ---

    def advance(self):
        """
        Recomputes the stage from current state. Called after every turn.
        Nothing here consults the LLM - that's the point.
        """
        if self.stage in (FlowStage.DONE, FlowStage.READY):
            return

        if self.missing_required():
            self.stage = FlowStage.COLLECTING
        elif self.flow.get("confirm") and self.stage == FlowStage.COLLECTING:
            self.stage = FlowStage.CONFIRMING
        elif not self.flow.get("confirm"):
            self.stage = FlowStage.READY

    def confirm(self, confirmed: bool):
        """Caller answered the confirmation question."""
        if confirmed:
            self.stage = FlowStage.READY
        else:
            # They said something was wrong. Drop back to collecting so the
            # LLM can find out what, and let them correct it.
            self.stage = FlowStage.COLLECTING

    def rendered_confirm(self) -> str | None:
        template = self.flow.get("confirm")
        if not template:
            return None
        text = template
        for name, value in self.values.items():
            text = text.replace("{" + name + "}", str(value))
        return text

    # --- prompt building ---

    def instructions(self) -> str:
        """
        What to tell the LLM about this turn. This is the steering: the
        model gets told exactly what's still needed, so it doesn't have to
        work it out (and doesn't get to skip it).
        """
        if self.stage == FlowStage.CONFIRMING:
            return (
                "You have everything you need. Read this back to the caller "
                f"to confirm, in your own words: \"{self.rendered_confirm()}\" "
                "If they confirm, say you're processing it. If they correct "
                "something, collect the correction."
            )

        if self.stage == FlowStage.READY:
            return "The caller confirmed. Tell them you're processing it now."

        lines = [f"You are helping the caller with: {self.flow.get('trigger', 'their request')}."]

        collected = {k: v for k, v in self.values.items()}
        if collected:
            summary = ", ".join(f"{k}: {v}" for k, v in collected.items())
            lines.append(f"Already collected - do NOT ask for these again: {summary}.")

        missing = self.missing_required()
        if missing:
            first = missing[0]
            lines.append(f"Still needed: {', '.join(f['prompt'] for f in missing)}.")
            lines.append(f"Ask for {first['prompt']} next, unless the caller raises something else.")
            options = first.get("options")
            if options:
                lines.append(f"Valid answers for that: {', '.join(options)}.")

        if self.rejected:
            problems = ", ".join(f"{k} (\"{v}\")" for k, v in self.rejected.items())
            lines.append(
                f"These were unclear or invalid and need re-asking: {problems}. "
                "Ask them to repeat it, mentioning what seemed wrong."
            )

        lines.append(
            "Ask for ONE thing at a time and stay conversational. If the caller "
            "volunteers several details at once, accept them all."
        )
        return " ".join(lines)

    def extraction_fields(self) -> list[dict]:
        """
        The field list the NLU service turns into a tool schema, so the LLM
        can report what it heard. Only fields still outstanding - no point
        asking it to re-extract what's already confirmed.
        """
        wanted = self.missing_required() or self.fields()
        return [
            {
                "name": f["name"],
                "prompt": f.get("prompt", f["name"]),
                "options": f.get("options"),
            }
            for f in wanted
        ]


def pick_flow(flows: list[dict], flow_id: str) -> dict | None:
    for f in flows:
        if f.get("flow_id") == flow_id:
            return f
    return None


def flow_menu(flows: list[dict]) -> str:
    """
    Describes the available flows so the LLM can recognize when a caller is
    asking for one. Kept as plain text rather than tool definitions because
    the model only needs to spot the intent - the engine handles the rest.
    """
    if not flows:
        return ""
    lines = ["Tasks you can carry out for this caller:"]
    for f in flows:
        lines.append(f"- {f.get('flow_id')}: {f.get('trigger', '')}")
    return "\n".join(lines)
