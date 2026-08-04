"""
Flow execution - graph walker.

Tracks where a call is in a tenant's flow graph, which fields are still
needed at the current node, and where to go next once they're collected.

Deliberately NOT a separate service: this is a state machine over call
state, and the Orchestrator already owns that state in CallSession.
Shipping it back and forth every turn would put a network hop in the
latency-critical path for no benefit.

The division of labour that makes this reliable:
  - The ENGINE decides what's missing and where to go next. Deterministic.
  - The LLM decides how to ask. Natural.

The model is never asked "do you have enough to book this?" - that's
answered by checking which required fields are empty. That's the difference
between "always collects a phone number" being a guarantee rather than a
tendency.
"""

import logging
import re
from enum import Enum

logger = logging.getLogger("orchestrator")

# A run that visits this many nodes without pausing for the caller is
# almost certainly looping through say/branch nodes with no exit. Better to
# stop and hand off than to spin.
MAX_NODE_HOPS = 25


class RunStatus(str, Enum):
    COLLECTING = "collecting"   # waiting on the caller for fields
    CONFIRMING = "confirming"   # read values back, waiting for yes/no
    SPEAKING = "speaking"       # has text to say, then continues
    ACTING = "acting"           # needs a connector call
    HANDOFF = "handoff"         # transfer to a human
    DONE = "done"


def check_format(value: str, fmt: str | None) -> bool:
    """
    Unknown format names pass rather than fail, so adding a new checker to
    the schema later can't retroactively break flows already stored.
    """
    if not fmt or value is None:
        return True
    text = str(value).strip()

    if fmt == "phone":
        return 7 <= len(re.sub(r"\D", "", text)) <= 15
    if fmt == "email":
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text) is not None
    if fmt == "number":
        try:
            float(text)
            return True
        except ValueError:
            return False
    if fmt == "date":
        # Permissive on purpose: the caller says "next Tuesday" and the LLM
        # normalizes it. Rejecting non-ISO would fight how people speak.
        # Real date resolution belongs in the connector, which knows the
        # business's calendar.
        return len(text) >= 3

    return True


def render(template: str | None, values: dict) -> str:
    if not template:
        return ""
    text = template
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


class FlowRun:
    """One flow graph, in progress, for one call."""

    def __init__(self, flow: dict):
        self.flow = flow
        self.flow_id = flow.get("flow_id", "unknown")
        self.nodes: dict = flow.get("nodes", {}) or {}
        self.current: str | None = flow.get("start")
        self.values: dict[str, str] = {}
        self.status = RunStatus.COLLECTING
        # Values the caller gave in a form we couldn't accept, kept so the
        # LLM can re-ask specifically rather than blankly repeating itself.
        self.rejected: dict[str, str] = {}
        # Set when a node produces something to say or do; the Orchestrator
        # drains these.
        self.pending_say: str | None = None
        self.pending_action: dict | None = None
        self._awaiting_confirm = False
        self.visited_path: list[str] = []

    # --- node access ---

    @property
    def node(self) -> dict | None:
        if self.current is None:
            return None
        return self.nodes.get(self.current)

    def _node_fields(self) -> list[dict]:
        node = self.node
        if not node or node.get("type") != "collect":
            return []
        return node.get("fields", []) or []

    def missing_required(self) -> list[dict]:
        return [
            f for f in self._node_fields()
            if f.get("required", True) and f["name"] not in self.values
        ]

    # --- collecting values ---

    def apply_values(self, extracted: dict) -> dict:
        """
        Records values the LLM extracted. Returns the ones rejected, so the
        caller can be told what went wrong.

        Accepts values for fields at ANY node, not just the current one - if
        a caller volunteers their phone number three questions early, we
        keep it rather than asking again later.
        """
        rejected = {}
        known = {}
        for node in self.nodes.values():
            for f in (node.get("fields") or []):
                known[f["name"]] = f

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
            if options and value.lower() not in [str(o).lower() for o in options]:
                rejected[name] = value
                logger.info("[flow %s] rejected %s=%r (not in options)",
                            self.flow_id, name, value)
                continue

            self.values[name] = value
            self.rejected.pop(name, None)

        self.rejected.update(rejected)
        return rejected

    def confirm(self, confirmed: bool):
        """Caller answered a confirmation question."""
        if not self._awaiting_confirm:
            return
        self._awaiting_confirm = False
        if confirmed:
            self._goto(self.node.get("next") if self.node else None)
        else:
            # Something was wrong. Clear this node's values so the LLM can
            # find out what and re-collect, rather than looping on a
            # confirmation the caller keeps rejecting.
            for f in self._node_fields():
                self.values.pop(f["name"], None)
            self.status = RunStatus.COLLECTING

    # --- graph walking ---

    def _goto(self, node_name: str | None):
        self.current = node_name
        self.advance()

    def advance(self):
        """
        Walks forward from the current node as far as it can without needing
        the caller. Stops at a collect node with unmet fields, a confirm
        that hasn't been answered, an action, or a handoff/end.

        Called after every turn. Nothing here consults the LLM.
        """
        hops = 0
        while True:
            hops += 1
            if hops > MAX_NODE_HOPS:
                logger.error("[flow %s] exceeded %d node hops - stopping. Path: %s",
                             self.flow_id, MAX_NODE_HOPS, " -> ".join(self.visited_path[-12:]))
                self.pending_say = None
                self.status = RunStatus.HANDOFF
                return

            node = self.node
            if node is None:
                self.status = RunStatus.DONE
                return

            if not self.visited_path or self.visited_path[-1] != self.current:
                self.visited_path.append(self.current)

            kind = node.get("type")

            if kind == "collect":
                if self.missing_required():
                    self.status = RunStatus.COLLECTING
                    return
                if node.get("confirm") and not self._awaiting_confirm:
                    self._awaiting_confirm = True
                    self.status = RunStatus.CONFIRMING
                    return
                if self._awaiting_confirm:
                    self.status = RunStatus.CONFIRMING
                    return
                self.current = node.get("next")
                continue

            if kind == "branch":
                target = None
                for branch in node.get("branches", []) or []:
                    if _branch_matches(branch, self.values):
                        target = branch.get("goto")
                        break
                if target is None:
                    # No arm matched and no fallback was authored. Ending is
                    # safer than picking one arbitrarily.
                    logger.warning("[flow %s] no branch matched at %r - ending flow",
                                   self.flow_id, self.current)
                    self.status = RunStatus.DONE
                    return
                self.current = target
                continue

            if kind == "say":
                self.pending_say = render(node.get("text"), self.values)
                self.current = node.get("next")
                self.status = RunStatus.SPEAKING
                return

            if kind == "action":
                self.pending_action = {
                    "connector": node.get("connector"),
                    "operation": node.get("operation"),
                    "result_key": node.get("result_key"),
                    "values": dict(self.values),
                }
                self.status = RunStatus.ACTING
                return

            if kind == "handoff":
                self.pending_say = render(node.get("text"), self.values)
                self.status = RunStatus.HANDOFF
                return

            # "end" or anything unrecognized
            self.status = RunStatus.DONE
            return

    def action_completed(self, result: dict | None, ok: bool = True):
        """Called once a connector has run, to continue from the action node."""
        node = self.node or {}
        self.pending_action = None

        if ok and result and node.get("result_key"):
            self.values[node["result_key"]] = result

        self._goto(node.get("next") if ok else (node.get("on_error") or node.get("next")))

    def take_pending_say(self) -> str | None:
        text, self.pending_say = self.pending_say, None
        return text

    def continue_after_say(self):
        """Called once a `say` node's text has been spoken."""
        if self.status == RunStatus.SPEAKING:
            self.advance()

    # --- prompt building ---

    def rendered_confirm(self) -> str | None:
        node = self.node
        return render(node.get("confirm"), self.values) if node else None

    def instructions(self) -> str:
        """
        What to tell the LLM this turn. This is the steering: the model is
        told exactly what's still needed, so it doesn't have to work it out
        - and doesn't get to skip it.
        """
        if self.status == RunStatus.CONFIRMING:
            return (
                "You have everything for this step. Read this back to confirm, "
                f"in your own words: \"{self.rendered_confirm()}\" "
                "If they confirm, say you're continuing. If they correct "
                "something, collect the correction."
            )

        lines = [f"You are helping the caller with: {self.flow.get('trigger', 'their request')}."]

        if self.values:
            # Underscore-prefixed keys (e.g. _branch_id, stamped by
            # stamp_entity_ids in the Orchestrator) are resolved ids for
            # connectors, not something the caller said or should hear
            # echoed back - exclude them from what the model sees as
            # "collected".
            summary = ", ".join(f"{k}: {v}" for k, v in self.values.items()
                                if not isinstance(v, dict) and not k.startswith("_"))
            if summary:
                lines.append(f"Already collected - do NOT ask again: {summary}.")

        missing = self.missing_required()
        if missing:
            first = missing[0]
            lines.append(f"Still needed: {', '.join(f['prompt'] for f in missing)}.")
            lines.append(f"Ask for {first['prompt']} next, unless the caller raises something else.")
            if first.get("options"):
                lines.append(f"Valid answers for that: {', '.join(first['options'])}.")

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
        Fields the NLU service turns into a tool schema. Current node's
        outstanding fields first, plus fields from later nodes so a caller
        who volunteers something early isn't asked for it again.
        """
        seen, out = set(), []
        for f in self.missing_required():
            seen.add(f["name"])
            out.append({"name": f["name"], "prompt": f.get("prompt", f["name"]),
                        "options": f.get("options")})

        for node in self.nodes.values():
            if node.get("type") != "collect":
                continue
            for f in (node.get("fields") or []):
                if f["name"] in seen or f["name"] in self.values:
                    continue
                seen.add(f["name"])
                out.append({"name": f["name"], "prompt": f.get("prompt", f["name"]),
                            "options": f.get("options")})
        return out


def _branch_matches(branch: dict, values: dict) -> bool:
    conditions = branch.get("when") or []
    if not conditions:
        return True
    results = [_condition_matches(c, values) for c in conditions]
    return any(results) if branch.get("match") == "any" else all(results)


def _condition_matches(cond: dict, values: dict) -> bool:
    field, op = cond.get("field"), cond.get("op", "eq")
    expected, actual = cond.get("value"), values.get(field)

    if op == "exists":
        return actual not in (None, "")
    if op == "not_exists":
        return actual in (None, "")
    if actual is None:
        return False

    actual_s = str(actual).strip().lower()
    if op == "eq":
        return actual_s == str(expected).strip().lower()
    if op == "ne":
        return actual_s != str(expected).strip().lower()
    if op == "in":
        return actual_s in [str(v).strip().lower() for v in (expected or [])]
    if op == "not_in":
        return actual_s not in [str(v).strip().lower() for v in (expected or [])]
    if op == "contains":
        return str(expected).strip().lower() in actual_s
    return False


def pick_flow(flows: list[dict], flow_id: str) -> dict | None:
    for f in flows:
        if f.get("flow_id") == flow_id:
            return f
    return None


def flow_menu(flows: list[dict]) -> str:
    if not flows:
        return ""
    lines = ["Tasks you can carry out for this caller:"]
    for f in flows:
        lines.append(f"- {f.get('flow_id')}: {f.get('trigger', '')}")
    return "\n".join(lines)
