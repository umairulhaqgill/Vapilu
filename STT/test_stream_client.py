"""
Test client for the streaming STT service.

Simulates a "live caller" by reading a wav file and sending it to the
service in small chunks, waiting briefly between chunks like real-time
audio would arrive — then prints every transcript event as it streams back.

IMPORTANT: your test wav file must actually be 16kHz, 16-bit, mono PCM
(linear16) to match the settings in stt_client.py's live_connection().
If your file is a different format, either convert it first (e.g. with
ffmpeg: `ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 test16k.wav`)
or adjust sample_rate/encoding in stt_client.py to match your file.

Run the service first in one terminal:
    uvicorn stt_service:app --reload --port 8000

Then in another terminal:
    python test_stream_client.py
"""

import asyncio
import os
import wave

import websockets
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("STT_SERVICE_TOKEN", "")
AUDIO_FILE = "sample_audio/test16k.wav"
SERVICE_URL = f"ws://localhost:8000/ws/transcribe?token={TOKEN}"
CHUNK_MS = 100  # send 100ms of audio at a time, like a real mic stream would


async def stream_audio():
    wf = wave.open(AUDIO_FILE, "rb")
    frame_rate = wf.getframerate()
    chunk_size = int(frame_rate * (CHUNK_MS / 1000)) * wf.getsampwidth()

    async with websockets.connect(SERVICE_URL) as ws:

        async def sender():
            while True:
                chunk = wf.readframes(chunk_size // wf.getsampwidth())
                if not chunk:
                    break
                await ws.send(chunk)
                await asyncio.sleep(CHUNK_MS / 1000)  # pace it like real audio
            print("Finished sending audio.")

        async def receiver():
            async for message in ws:
                print("Transcript event:", message)

        await asyncio.gather(sender(), receiver())


if __name__ == "__main__":
    asyncio.run(stream_audio())
