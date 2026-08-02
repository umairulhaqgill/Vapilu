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

import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from nlu_client import NluClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nlu-service")

app = FastAPI(title="NLU/LLM Service")

nlu = NluClient(
    model=os.environ.get("NLU_MODEL", "anthropic/claude-sonnet-4.6"),
    max_tokens=int(os.environ.get("NLU_MAX_TOKENS", "150")),
)

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


@app.post("/reply/stream")
async def reply_stream(request: ReplyRequest):
    """
    Same as /reply, but streams the response as newline-delimited JSON
    instead of waiting for the whole reply. Each line is one of:
      {"delta": "..."}          - a small chunk of new text
      {"done": true}            - the reply is complete
      {"error": "..."}          - something went wrong mid-stream

    This is what actually makes the bot feel fast: the Orchestrator can
    start acting on the first few words immediately instead of waiting for
    the whole sentence (or paragraph) to finish generating.
    """
    if NLU_SERVICE_TOKEN and request.token != NLU_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid token")

    history = [{"role": t.role, "content": t.content} for t in request.conversation_history]

    async def generate():
        try:
            async for delta in nlu.get_reply_stream(history):
                yield json.dumps({"delta": delta}) + "\n"
            yield json.dumps({"done": True}) + "\n"
        except Exception as e:
            logger.exception("NLU streaming reply failed: %s", e)
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")