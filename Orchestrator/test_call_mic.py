"""
Streams your mic into the Orchestrator (not directly into the STT Service)
so you can test the full chain: mic -> Orchestrator -> STT Service ->
Deepgram -> transcript -> Orchestrator's state machine -> placeholder reply.

Requires both services already running:
    Terminal 1 (in stt-service/):    uvicorn stt_service:app --reload --port 8000
    Terminal 2 (in orchestrator/):   uvicorn orchestrator_service:app --reload --port 8001

Then, in a third terminal (in orchestrator/):
    python test_call_mic.py

Speak into your mic. You'll see:
  - the bot's greeting immediately
  - "(caller speaking...)" the instant you start talking
  - the bot's (placeholder) reply after you pause

Press Ctrl+C to stop.
"""

import asyncio
import json
import os
import sys

import sounddevice as sd
import websockets
from dotenv import load_dotenv

load_dotenv()

ORCHESTRATOR_TOKEN = os.environ.get("ORCHESTRATOR_TOKEN", "")
SERVICE_URL = f"ws://localhost:8001/ws/call?token={ORCHESTRATOR_TOKEN}"
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_MS = 100


async def call():
    loop = asyncio.get_event_loop()
    audio_queue: asyncio.Queue = asyncio.Queue()

    def on_audio_block(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    blocksize = int(SAMPLE_RATE * BLOCK_MS / 1000)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=blocksize,
        callback=on_audio_block,
    ):
        async with websockets.connect(SERVICE_URL) as ws:

            async def sender():
                while True:
                    chunk = await audio_queue.get()
                    await ws.send(chunk)

            async def receiver():
                async for message in ws:
                    data = json.loads(message)
                    if data.get("event") == "caller_speaking":
                        print("(caller speaking...)")
                    elif data.get("event") == "bot_speech":
                        print(f"Bot: {data['text']}")
                    elif "error" in data:
                        print(f"[error] {data['error']}: {data.get('detail')}")

            print("Call connected. Speak into your mic. Ctrl+C to stop.\n")
            await asyncio.gather(sender(), receiver())


if __name__ == "__main__":
    try:
        asyncio.run(call())
    except KeyboardInterrupt:
        print("\nCall ended.")
