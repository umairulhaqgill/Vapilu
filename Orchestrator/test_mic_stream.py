"""
Streams your laptop mic straight into the STT service and prints transcripts
live as you speak. This is the real end-to-end test: mic -> your service ->
Deepgram -> transcript back to you, all in near real time.

Requires: sounddevice (already in requirements.txt)
  - Windows: works out of the box, no extra installs needed.
  - Mac: if import fails, `brew install portaudio` first.
  - Linux: if import fails, `sudo apt install libportaudio2` first.

Run the service first, in one terminal:
    uvicorn stt_service:app --reload --port 8000

Then, in another terminal:
    python test_mic_stream.py

Speak into your mic, watch transcripts appear. Press Ctrl+C to stop.
"""

import asyncio
import os
import sys

import sounddevice as sd
import websockets
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("STT_SERVICE_TOKEN", "")
SERVICE_URL = f"ws://localhost:8000/ws/transcribe?token={TOKEN}"
SAMPLE_RATE = 16000  # must match stt_client.py's live_connection() settings
CHANNELS = 1
BLOCK_MS = 100  # send ~100ms chunks at a time, like a real phone call would


async def mic_stream():
    loop = asyncio.get_event_loop()
    audio_queue: asyncio.Queue = asyncio.Queue()

    def on_audio_block(indata, frames, time_info, status):
        """Called by sounddevice on a background thread for every audio block."""
        if status:
            print(status, file=sys.stderr)
        # Hand the raw bytes off to the asyncio side safely (different thread).
        loop.call_soon_threadsafe(audio_queue.put_nowait, bytes(indata))

    blocksize = int(SAMPLE_RATE * BLOCK_MS / 1000)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=blocksize,
        callback=on_audio_block,
    ):
        print("Listening on your default mic — speak now. Ctrl+C to stop.\n")

        async with websockets.connect(SERVICE_URL) as ws:

            async def sender():
                while True:
                    chunk = await audio_queue.get()
                    await ws.send(chunk)

            async def receiver():
                async for message in ws:
                    print(message)

            await asyncio.gather(sender(), receiver())


if __name__ == "__main__":
    try:
        asyncio.run(mic_stream())
    except KeyboardInterrupt:
        print("\nStopped.")
