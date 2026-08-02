"""
NLU/LLM Service - turns conversation history into the bot's next reply.

  Orchestrator  --HTTP POST-->  This service  --API call-->  Claude

Stateless by design: every request must include the full conversation
history so far. The Orchestrator owns and grows that history per call
(in CallSession) - this service just answers "given this history, what
should the bot say next."

Run with:
    uvicorn nlu_service:app --reload --port 8002
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from nlu_client import NluClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nlu-service")

app = FastAPI(title="NLU/LLM Service")

nlu = NluClient()  # reads ANTHROPIC_API_KEY from environment

NLU_SERVICE_TOKEN = os.environ.get("NLU_SERVICE_TOKEN")
if not NLU_SERVICE_TOKEN:
    logger.warning(
        "NLU_SERVICE_TOKEN is not set - /reply is UNAUTHENTICATED. "
        "Fine for local testing, not for anything public."
    )


class Turn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ReplyRequest(BaseModel):
    conversation_history: list[Turn]
    token: str | None = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reply")
async def reply(request: ReplyRequest):
    if NLU_SERVICE_TOKEN and request.token != NLU_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid token")

    history = [turn.model_dump(exclude={}) for turn in request.conversation_history]
    # Only role/content are meaningful to the Anthropic API - strip anything else.
    history = [{"role": t["role"], "content": t["content"]} for t in history]

    try:
        reply_text = nlu.get_reply(history)
    except Exception as e:
        logger.exception("NLU reply failed: %s", e)
        raise HTTPException(status_code=502, detail=f"reply generation failed: {e}")

    return {"reply": reply_text}
