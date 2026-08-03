"""
Call state tracking — the Orchestrator's core job.

Kept intentionally simple and in-memory for v1: one CallSession instance per
active WebSocket connection, alive only as long as the process is running.
Once you need state to survive a restart, or be visible to more than one
Orchestrator process, this is exactly what moves into the Session Store
(Redis) service from the architecture doc — the state machine logic here
wouldn't need to change, just where `self.state` actually lives.
"""

import logging
from enum import Enum

logger = logging.getLogger("orchestrator")


class CallState(str, Enum):
    GREETING = "greeting"      # bot is delivering its opening line
    LISTENING = "listening"    # waiting for the caller to speak
    THINKING = "thinking"      # caller finished speaking, deciding a reply
    RESPONDING = "responding"  # bot is delivering its reply
    CLOSED = "closed"          # call has ended


class CallSession:
    def __init__(self, conn_id: str):
        self.conn_id = conn_id
        self.state: CallState | None = None
        # Full conversation so far, as {"role": "user"/"assistant", "content": "..."}
        # turns — the exact shape the NLU/LLM Service expects. This is the one
        # thing that makes the bot "remember" earlier parts of the same call;
        # the NLU Service itself is stateless and relies entirely on this.
        self.conversation_history: list[dict] = []
        # If a response gets interrupted and the caller doesn't follow up
        # with anything new within a short grace period, this holds
        # whatever partial reply text had already been generated before
        # the interruption - so it can be resumed instead of just dropped.
        # None means there's nothing pending to resume.
        self.pending_resume_text: str | None = None
        # This call's tenant configuration (greeting, system prompt, hours,
        # etc). Loaded once at call start from the Tenant Config Service.
        # None means no tenant was specified or lookup failed - the
        # Orchestrator falls back to generic defaults in that case.
        self.tenant: dict | None = None
        # Flows this tenant has defined, loaded once at call start.
        self.flows: list[dict] = []
        # The flow currently in progress, if any. A FlowRun instance -
        # typed loosely here to keep call_state free of engine imports.
        self.active_flow = None

    async def transition(self, new_state: CallState):
        logger.info("[%s] state: %s -> %s", self.conn_id, self.state, new_state)
        self.state = new_state
