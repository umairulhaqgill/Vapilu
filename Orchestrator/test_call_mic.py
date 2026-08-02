"""
Streams your mic into the Orchestrator (not directly into the STT Service)
so you can test the full chain: mic -> Orchestrator -> STT Service ->
Deepgram -> transcript -> NLU Service -> TTS Service -> spoken audio back
to you, through your speakers.

Requires all three backing services already running (see run_all.ps1),
plus the Orchestrator itself:
    uvicorn orchestrator_service:app --reload --port 8001

Then:
    python test_call_mic.py

Speak into your mic. You'll hear:
  - the bot's spoken greeting immediately
  - "(caller speaking...)" printed the instant you start talking
  - the bot's actual spoken reply after you pause

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
    output_stream = None  # created once we learn the audio format from the server

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
                nonlocal output_stream
                bot_is_speaking = False
                async for message in ws:
                    if isinstance(message, bytes):
                        # Raw PCM audio from the bot's TTS - play it as it arrives.
                        # A plain blocking write is fine for a manual test script
                        # like this; a production client would want a proper
                        # non-blocking playback queue instead.
                        if output_stream is not None:
                            output_stream.write(message)
                        continue

                    data = json.loads(message)
                    if data.get("event") == "audio_format":
                        output_stream = sd.RawOutputStream(
                            samplerate=data["sample_rate"],
                            channels=data["channels"],
                            dtype="int16",
                        )
                        output_stream.start()
                    elif data.get("event") == "caller_speaking":
                        print("(caller speaking...)")
                    elif data.get("event") == "bot_speech":
                        print(f"Bot: {data['text']}")
                    elif data.get("event") == "bot_speech_chunk":
                        if not bot_is_speaking:
                            print("Bot: ", end="", flush=True)
                            bot_is_speaking = True
                        print(data["text"], end="", flush=True)
                    elif data.get("event") == "bot_speech_end":
                        print()  # newline after the streamed reply finishes
                        bot_is_speaking = False
                    elif "error" in data:
                        print(f"[error] {data['error']}: {data.get('detail')}")

            print("Call connected. Speak into your mic. Ctrl+C to stop.\n")
            try:
                await asyncio.gather(sender(), receiver())
            finally:
                if output_stream is not None:
                    output_stream.stop()
                    output_stream.close()


if __name__ == "__main__":
    try:
        asyncio.run(call())
    except KeyboardInterrupt:
        print("\nCall ended.")  