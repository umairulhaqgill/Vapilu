"""
Flow definition schema - directed graph.

A flow is a graph of nodes. Each node does one thing (collect fields, say
something, call a connector, branch), then names the next node. Edges can
be conditional, so a call takes different paths based on what the caller
said.

The division that keeps this from becoming an IVR: WITHIN a node the LLM is
free - it phrases questions naturally, accepts several answers at once,
handles digressions. BETWEEN nodes the graph is deterministic - the engine
picks the next node by evaluating conditions against collected values, and
the model gets no say. Predictable routing, natural dialogue.

Backwards compatible: a flow authored in the old flat style (a `collect`
list plus an `action`) is converted to an equivalent graph on load, so
flows already in the database keep working untouched.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class FlowField(BaseModel):
    name: str
    # Plain-language description of what to ask for - goes into the prompt,
    # so write it as you'd explain it to a new receptionist.
    prompt: str
    required: bool = True

    # Optional format check. Named "format" rather than "validate" because
    # "validate" collides with a pydantic BaseModel attribute. Unrecognized
    # values pass, so adding a new checker later can't break stored flows.
    #   "phone" | "email" | "number" | "date"
    format: str | None = None

    options: list[str] | None = None

    # When set, valid answers come from the tenant's entities of this type
    # (see TenantConfig.entities) instead of being authored here - e.g.
    # "branch" means "whichever branches this tenant currently has", kept
    # in sync automatically as the tenant adds or renames one. The
    # Orchestrator resolves this into `options` per call, before the flow
    # ever reaches this schema's engine - see
    # `orchestrator_service.inject_entity_options`.
    entity_type: str | None = None


class Condition(BaseModel):
    """
    One test against collected values.

    Deliberately a small data structure rather than an expression string:
    these are evaluated on every call, and evaluating arbitrary strings
    would mean writing a parser or using eval(). A builder UI can also
    render this directly as dropdowns.
    """
    field: str
    op: Literal["eq", "ne", "in", "not_in", "exists", "not_exists", "contains"] = "eq"
    value: Any = None

    def evaluate(self, values: dict) -> bool:
        actual = values.get(self.field)

        if self.op == "exists":
            return actual not in (None, "")
        if self.op == "not_exists":
            return actual in (None, "")

        if actual is None:
            return False

        actual_s = str(actual).strip().lower()

        if self.op == "eq":
            return actual_s == str(self.value).strip().lower()
        if self.op == "ne":
            return actual_s != str(self.value).strip().lower()
        if self.op == "in":
            return actual_s in [str(v).strip().lower() for v in (self.value or [])]
        if self.op == "not_in":
            return actual_s not in [str(v).strip().lower() for v in (self.value or [])]
        if self.op == "contains":
            return str(self.value).strip().lower() in actual_s
        return False


class Branch(BaseModel):
    """
    One arm of a branch node. `when` omitted means "always" - use that on
    the last arm to make it the fallback.
    """
    when: list[Condition] = Field(default_factory=list)
    match: Literal["all", "any"] = "all"
    goto: str

    def matches(self, values: dict) -> bool:
        if not self.when:
            return True
        results = [c.evaluate(values) for c in self.when]
        return all(results) if self.match == "all" else any(results)


class FlowNode(BaseModel):
    """
    One step. `type` decides which fields matter:

      collect  - gather `fields` from the caller, then go to `next`
      say      - speak `text` (supports {field} placeholders), then `next`
      action   - call `connector`.`operation`, then `next` (or `on_error`)
      branch   - evaluate `branches` in order, take the first that matches
      handoff  - transfer to a human, ends the flow
      end      - stop the flow
    """
    type: Literal["collect", "say", "action", "branch", "handoff", "end"]

    fields: list[FlowField] = Field(default_factory=list)
    # Read values back and require a yes before moving on. Cheapest defence
    # against a mistranscription becoming a real booking.
    confirm: str | None = None

    text: str | None = None

    connector: str | None = None
    operation: str | None = None
    # Where the connector's result lands in collected values, so later
    # nodes and conditions can use it.
    result_key: str | None = None
    on_error: str | None = None
    # Name of a `collect` field (elsewhere in this flow) whose entity_type
    # picked a specific resource - "branch" if this action should run
    # against whichever branch the caller chose. Lets the Connector Gateway
    # look up settings scoped to that one entity (its calendar id) rather
    # than one config per tenant. None means this action isn't scoped to
    # a particular entity.
    entity_field: str | None = None

    branches: list[Branch] = Field(default_factory=list)

    next: str | None = None

    # Canvas position for the flow builder UI, e.g. {"x": 120, "y": 40}.
    # Opaque to the engine - carried through save/load so the builder's
    # layout survives a round trip.
    ui: dict[str, Any] | None = None


class FlowConfig(BaseModel):
    flow_id: str
    tenant_id: str

    # Plain-language description of when this flow applies - phrase it as an
    # intent: "caller wants to book a repair appointment".
    trigger: str

    start: str | None = None
    nodes: dict[str, FlowNode] = Field(default_factory=dict)

    # Legacy flat form, converted to a graph on load.
    collect: list[FlowField] = Field(default_factory=list)
    confirm: str | None = None
    action: dict | None = None
    on_success: str | None = None
    on_failure: str | None = None

    active: bool = True

    @model_validator(mode="after")
    def _ensure_graph(self):
        if self.nodes or not self.collect:
            return self
        self.nodes, self.start = _flat_to_graph(self)
        return self

    def validate_graph(self) -> list[str]:
        """
        Problems with the graph, empty list if sound. Worth calling before
        saving - a dangling goto otherwise only surfaces mid-call, which is
        the worst time to discover it.
        """
        problems = []
        if not self.nodes:
            return ["flow has no nodes"]
        if not self.start:
            problems.append("flow has no start node")
        elif self.start not in self.nodes:
            problems.append(f"start node {self.start!r} does not exist")

        for name, node in self.nodes.items():
            targets = []
            if node.next:
                targets.append(node.next)
            if node.on_error:
                targets.append(node.on_error)
            targets += [b.goto for b in node.branches]

            for target in targets:
                if target not in self.nodes:
                    problems.append(f"node {name!r} points to missing node {target!r}")

            if node.type == "branch" and not node.branches:
                problems.append(f"branch node {name!r} has no branches")
            if node.type in ("collect", "say") and not node.next:
                problems.append(f"node {name!r} has no next node")
            if node.type == "action" and (not node.connector or not node.operation):
                problems.append(f"action node {name!r} needs connector and operation")

        reachable = self._reachable()
        for name in self.nodes:
            if name not in reachable:
                problems.append(f"node {name!r} is unreachable")

        return problems

    def _reachable(self) -> set[str]:
        if not self.start or self.start not in self.nodes:
            return set()
        seen, stack = set(), [self.start]
        while stack:
            name = stack.pop()
            if name in seen or name not in self.nodes:
                continue
            seen.add(name)
            node = self.nodes[name]
            for target in [node.next, node.on_error] + [b.goto for b in node.branches]:
                if target:
                    stack.append(target)
        return seen


def _flat_to_graph(flow: "FlowConfig") -> tuple[dict[str, FlowNode], str]:
    """Legacy flat flow -> equivalent graph."""
    nodes: dict[str, FlowNode] = {}
    tail = "finish"

    if flow.action:
        nodes["do_action"] = FlowNode(
            type="action",
            connector=flow.action.get("connector"),
            operation=flow.action.get("operation"),
            next="success" if flow.on_success else tail,
            on_error="failure" if flow.on_failure else tail,
        )
        if flow.on_success:
            nodes["success"] = FlowNode(type="say", text=flow.on_success, next=tail)
        if flow.on_failure:
            nodes["failure"] = FlowNode(type="say", text=flow.on_failure, next=tail)

    nodes["collect"] = FlowNode(
        type="collect",
        fields=flow.collect,
        confirm=flow.confirm,
        next="do_action" if flow.action else tail,
    )
    nodes[tail] = FlowNode(type="end")
    return nodes, "collect"
