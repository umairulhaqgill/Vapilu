"""
Orchestrator — the conversation state machine.

  Caller  <---WebSocket--->  Orchestrator  <---WebSocket--->  STT Service

- Caller connects to  ws://<host>:8001/ws/call?token=...
- Caller sends raw audio bytes (same format the STT Service expects)
- Orchestrator forwards that audio to the STT Service (as a client of it —
  same role your test_mic_stream.py script has been playing)
- On each transcript event, the Orchestrator advances its call state machine
  and calls the NLU/LLM Service for a real reply, using session.conversation_history
  to keep memory of everything said so far in this call. TTS Service doesn't
  exist yet, so replies are still sent as text, clearly marked below.

Run with:
    uvicorn orchestrator_service:app --reload --port 8001

Needs the STT Service already running (port 8000 by default).
"""

import asyncio
import json
import logging
import os
import uuid

import httpx
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from call_state import CallSession, CallState

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("orchestrator")

app = FastAPI(title="Orchestrator")

STT_SERVICE_URL = os.environ.get("STT_SERVICE_URL", "ws://localhost:8000/ws/transcribe")
STT_SERVICE_TOKEN = os.environ.get("STT_SERVICE_TOKEN", "")

NLU_SERVICE_URL = os.environ.get("NLU_SERVICE_URL", "http://localhost:8002/reply")
NLU_SERVICE_TOKEN = os.environ.get("NLU_SERVICE_TOKEN", "")

ORCHESTRATOR_TOKEN = os.environ.get("ORCHESTRATOR_TOKEN")
if not ORCHESTRATOR_TOKEN:
    logger.warning(
        "ORCHESTRATOR_TOKEN is not set — /ws/call is UNAUTHENTICATED. "
        "Fine for local testing, not for anything public."
    )


async def get_nlu_reply(conversation_history: list[dict]) -> str:
    """
    Calls the NLU/LLM Service with the full conversation so far and returns
    its reply. Falls back to a safe, spoken-friendly message if the service
    is unreachable or errors — a call in progress shouldn't die just because
    one downstream service hiccuped.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(
                NLU_SERVICE_URL,
                json={"token": NLU_SERVICE_TOKEN, "conversation_history": conversation_history},
            )
            response.raise_for_status()
            return response.json()["reply"]
    except Exception as e:
        logger.exception("NLU Service call failed: %s", e)
        return "Sorry, I'm having trouble understanding right now. Could you say that again?"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/call")
async def handle_call(
    client_ws: WebSocket,
    token: str | None = None,
    encoding: str = "linear16",
    sample_rate: int = 16000,
):
    conn_id = uuid.uuid4().hex[:8]

    if ORCHESTRATOR_TOKEN and token != ORCHESTRATOR_TOKEN:
        logger.warning("[%s] rejected: missing or invalid token", conn_id)
        await client_ws.close(code=4401)
        return

    await client_ws.accept()
    session = CallSession(conn_id)
    logger.info("[%s] call started", conn_id)

    # --- Greeting ---
    await session.transition(CallState.GREETING)
    await client_ws.send_text(json.dumps({
        "event": "bot_speech",
        "text": "Hello! How can I help you today?",
        # TTS Service doesn't exist yet — sending text instead of audio.
        # Once it does, this becomes: audio = tts.synthesize(text); send audio.
    }))

    await session.transition(CallState.LISTENING)

    stt_url = f"{STT_SERVICE_URL}?token={STT_SERVICE_TOKEN}&encoding={encoding}&sample_rate={sample_rate}"

    try:
        async with websockets.connect(stt_url) as stt_ws:

            async def pump_audio_caller_to_stt():
                """Forwards the caller's audio to the STT Service."""
                try:
                    while True:
                        chunk = await client_ws.receive_bytes()
                        await stt_ws.send(chunk)
                except WebSocketDisconnect:
                    await stt_ws.close()

            async def pump_stt_events_to_orchestrator():
                """Reads transcript events from the STT Service and drives the state machine."""
                try:
                    async for message in stt_ws:
                        data = json.loads(message)

                        if data.get("event") == "speech_started":
                            # Caller started talking — this is the barge-in signal.
                            # Once TTS exists: if session.state == RESPONDING, stop
                            # playback here. For now, just forward it along.
                            await client_ws.send_text(json.dumps({"event": "caller_speaking"}))
                            continue

                        transcript = data.get("transcript")
                        if not transcript or not data.get("speech_final"):
                            continue  # only act once the caller has finished a full thought

                        await session.transition(CallState.THINKING)
                        logger.info("[%s] caller said: %s", conn_id, transcript)

                        session.conversation_history.append({"role": "user", "content": transcript})
                        reply_text = await get_nlu_reply(session.conversation_history)
                        session.conversation_history.append({"role": "assistant", "content": reply_text})

                        await session.transition(CallState.RESPONDING)
                        await client_ws.send_text(json.dumps({
                            "event": "bot_speech",
                            "text": reply_text,
                            # TTS Service doesn't exist yet — sending text instead of audio.
                        }))

                        await session.transition(CallState.LISTENING)
                except ConnectionClosed:
                    # Expected once the caller disconnects and we close the
                    # STT Service connection in response — not a real error,
                    # just the natural end of this call.
                    logger.info("[%s] STT Service connection closed", conn_id)

            await asyncio.gather(
                pump_audio_caller_to_stt(),
                pump_stt_events_to_orchestrator(),
            )

    except WebSocketDisconnect:
        logger.info("[%s] caller disconnected", conn_id)
    except Exception as e:
        logger.exception("[%s] error: %s", conn_id, e)
        try:
            await client_ws.send_text(json.dumps({"error": "orchestrator_failed", "detail": str(e)}))
        except Exception:
            pass
        await client_ws.close(code=1011)
    finally:
        await session.transition(CallState.CLOSED)
        logger.info("[%s] call ended", conn_id)
