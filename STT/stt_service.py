"""
STT Service — WebSocket streaming version.

This turns the STT wrapper into a real network service:

  Client (browser/orchestrator)  <---WebSocket--->  This service  <---WebSocket--->  Deepgram

- Client connects to  ws://<host>:8000/ws/transcribe?token=...
- Client sends raw audio bytes (binary WebSocket frames) as it records
- This service forwards each chunk to Deepgram in real time
- As Deepgram returns interim/final transcripts, this service immediately
  streams them back to the client as JSON messages

Run with:
    uvicorn stt_service:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from websockets.exceptions import ConnectionClosed

from stt_client import SttClient

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("stt-service")

app = FastAPI(title="STT Service")

stt = SttClient()  # reads DEEPGRAM_API_KEY from environment

# If STT_SERVICE_TOKEN is unset, auth is skipped — convenient for local dev,
# but set it before this ever runs anywhere reachable by anyone but you.
REQUIRED_TOKEN = os.environ.get("STT_SERVICE_TOKEN")
if not REQUIRED_TOKEN:
    logger.warning(
        "STT_SERVICE_TOKEN is not set — the /ws/transcribe endpoint is "
        "UNAUTHENTICATED. Fine for local testing, not for anything public."
    )


@app.get("/health")
async def health():
    """Simple liveness check — useful once this runs behind a load balancer."""
    return {"status": "ok"}


@app.post("/transcribe/file")
async def transcribe_file_endpoint(
    file: UploadFile = File(...),
    token: str | None = None,
    language: str = "en",
):
    """
    For pre-recorded audio (voicemails, saved call recordings for QA/analytics)
    — not for live calls, use /ws/transcribe for those. This is a normal
    request/response call: send the whole file, wait, get the whole transcript
    back. Deepgram's prerecorded API doesn't support partial/progressive
    results for a batch file, so unlike /ws/transcribe there's nothing to
    stream here — the honest fix for "files weren't part of the service" is
    exposing this endpoint, not faking a stream that doesn't exist.
    """
    if REQUIRED_TOKEN and token != REQUIRED_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid token")

    audio_bytes = await file.read()
    try:
        transcript = stt.transcribe_bytes(audio_bytes, language=language)
    except Exception as e:
        logger.exception("File transcription failed: %s", e)
        raise HTTPException(status_code=502, detail=f"transcription failed: {e}")

    return {"transcript": transcript}


@app.websocket("/ws/transcribe")
async def transcribe_stream(
    client_ws: WebSocket,
    token: str | None = None,
    encoding: str = "linear16",
    sample_rate: int = 16000,
    language: str = "en",
):
    """
    Query params let each caller describe its own audio format instead of it
    being hardcoded — e.g. Twilio will connect with
    ?encoding=mulaw&sample_rate=8000, while a browser mic client uses the
    linear16/16000 defaults.
    """
    conn_id = uuid.uuid4().hex[:8]

    # --- Auth gate: reject before accepting the handshake if token is wrong ---
    if REQUIRED_TOKEN and token != REQUIRED_TOKEN:
        logger.warning("[%s] rejected: missing or invalid token", conn_id)
        await client_ws.close(code=4401)  # 4401 = custom "unauthorized"
        return

    await client_ws.accept()
    logger.info(
        "[%s] client connected (encoding=%s sample_rate=%s language=%s)",
        conn_id, encoding, sample_rate, language,
    )

    try:
        async with stt.live_connection(
            encoding=encoding, sample_rate=sample_rate, language=language
        ) as dg_socket:

            async def pump_audio_client_to_deepgram():
                """Reads audio chunks from the client and forwards them to Deepgram."""
                try:
                    while True:
                        chunk = await client_ws.receive_bytes()
                        await dg_socket.send_media(chunk)
                except WebSocketDisconnect:
                    logger.info("[%s] client disconnected, closing Deepgram stream", conn_id)
                    await dg_socket.send_close_stream()

            async def pump_transcripts_deepgram_to_client():
                """Reads transcript events from Deepgram and forwards them to the client."""
                try:
                    while True:
                        result = await dg_socket.recv()
                        result_type = getattr(result, "type", None)

                        if result_type == "SpeechStarted":
                            # The caller just started talking. This is the signal
                            # your Orchestrator needs for barge-in — stop playing
                            # TTS audio immediately when the caller talks over it.
                            await client_ws.send_text(json.dumps({"event": "speech_started"}))
                            continue

                        if result_type != "Results":
                            # Other event types (Metadata, UtteranceEnd) skipped for now.
                            continue

                        channel = result.channel
                        alternative = channel.alternatives[0]
                        if not alternative.transcript:
                            continue  # empty interim result, nothing worth sending

                        payload = {
                            "transcript": alternative.transcript,
                            "confidence": alternative.confidence,
                            "is_final": bool(result.is_final),
                            "speech_final": bool(result.speech_final),
                        }
                        await client_ws.send_text(json.dumps(payload))
                except ConnectionClosed:
                    # Expected once the client disconnects and we close the
                    # Deepgram stream in response (see pump_audio above) —
                    # not a real error, just the natural end of this call.
                    logger.info("[%s] Deepgram stream closed", conn_id)

            # Run both directions concurrently until either the client
            # disconnects or the Deepgram stream ends.
            await asyncio.gather(
                pump_audio_client_to_deepgram(),
                pump_transcripts_deepgram_to_client(),
            )

    except WebSocketDisconnect:
        logger.info("[%s] client disconnected", conn_id)
    except Exception as e:
        logger.exception("[%s] error in transcription stream: %s", conn_id, e)
        # Tell the client *why* it's about to be disconnected, instead of
        # just dropping the connection with no explanation.
        try:
            await client_ws.send_text(json.dumps({"error": "stt_stream_failed", "detail": str(e)}))
        except Exception:
            pass  # client socket may already be gone; nothing more we can do
        await client_ws.close(code=1011)    