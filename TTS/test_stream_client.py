"""
Tests the TTS Service over its actual WebSocket, playing back the audio it
streams - the real end-to-end test, matching how the Orchestrator will use it.

Run the service first:
    uvicorn tts_service:app --reload --port 8003

Then:
    python test_stream_client.py
"""

import asyncio
import json
import os

import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TTS_SERVICE_TOKEN", "")
SERVICE_URL = f"ws://localhost:8003/ws/synthesize?token={TOKEN}"
TEXT = "Hello! This is a streaming test over the actual WebSocket service."


async def main():
    async with websockets.connect(SERVICE_URL) as ws:
        fmt_message = json.loads(await ws.recv())
        print("Format:", fmt_message)
        sample_rate = fmt_message["sample_rate"]

        await ws.send(TEXT)
        print(f"Sent: {TEXT!r}\n")

        all_audio = bytearray()
        async for message in ws:
            if isinstance(message, bytes):
                print(f"  received audio chunk: {len(message)} bytes")
                all_audio.extend(message)
            else:
                data = json.loads(message)
                print("Event:", data)
                if data.get("event") == "utterance_end":
                    break

        print(f"\nTotal audio: {len(all_audio)} bytes. Playing back...")
        audio_array = np.frombuffer(bytes(all_audio), dtype=np.int16)
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
