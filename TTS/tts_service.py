"""
TTS Service - turns text into streamed audio, using Piper (local, free).

  Orchestrator  <---WebSocket--->  This service  --(local CPU)-->  Piper

- Orchestrator connects to  ws://<host>:8003/ws/synthesize?token=...
- Orchestrator sends one text message per utterance (e.g. one sentence)
- This service streams back raw 16-bit PCM audio chunks as they're
  generated, followed by an "end" marker - so playback can start on the
  first chunk instead of waiting for the whole utterance to finish.

Run with:
    uvicorn tts_service:app --reload --port 8003
"""

import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from tts_client import TtsClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tts-service")

app = FastAPI(title="TTS Service")

MODEL_PATH = os.environ.get("PIPER_MODEL_PATH", "voices/en_US-amy-medium.onnx")
tts = TtsClient(model_path=MODEL_PATH)

TTS_SERVICE_TOKEN = os.environ.get("TTS_SERVICE_TOKEN")
if not TTS_SERVICE_TOKEN:
    logger.warning(
        "TTS_SERVICE_TOKEN is not set - /ws/synthesize is UNAUTHENTICATED. "
        "Fine for local testing, not for anything public."
    )


@app.get("/health")
async def health():
    return {"status": "ok", "sample_rate": tts.sample_rate}


@app.websocket("/ws/synthesize")
async def synthesize_stream(client_ws: WebSocket, token: str | None = None):
    if TTS_SERVICE_TOKEN and token != TTS_SERVICE_TOKEN:
        logger.warning("rejected: missing or invalid token")
        await client_ws.close(code=4401)
        return

    await client_ws.accept()

    # Tell the client the audio format up front, once, so it knows how to
    # play back the raw PCM bytes that follow.
    await client_ws.send_text(json.dumps({
        "event": "format",
        "sample_rate": tts.sample_rate,
        "sample_width": tts.sample_width,
        "channels": tts.channels,
    }))

    try:
        while True:
            text = await client_ws.receive_text()
            if not text.strip():
                continue

            try:
                async for audio_chunk in tts.synthesize_stream(text):
                    await client_ws.send_bytes(audio_chunk)
                await client_ws.send_text(json.dumps({"event": "utterance_end"}))
            except Exception as e:
                logger.exception("Synthesis failed: %s", e)
                await client_ws.send_text(json.dumps({"error": "synthesis_failed", "detail": str(e)}))

    except WebSocketDisconnect:
        logger.info("client disconnected")
