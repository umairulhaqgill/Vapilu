"""
Local test: synthesizes a sentence and plays it through your speakers - no
network services involved, just Piper directly. Good first test before
running the full WebSocket service.

Run the service first? No - this script doesn't need tts_service.py running
at all, it uses tts_client.py directly.

Usage:
    python test_local_playback.py
"""

import asyncio
import os

import sounddevice as sd
import numpy as np
from dotenv import load_dotenv

from tts_client import TtsClient

load_dotenv()

MODEL_PATH = os.environ.get("PIPER_MODEL_PATH", "voices/en_US-amy-medium.onnx")
TEXT = "Hello! This is a test of the local text to speech service."


async def main():
    print(f"Loading voice model from {MODEL_PATH} ...")
    tts = TtsClient(model_path=MODEL_PATH)
    print(f"Loaded. Sample rate: {tts.sample_rate} Hz\n")

    print(f"Synthesizing: {TEXT!r}")
    all_audio = bytearray()
    async for chunk in tts.synthesize_stream(TEXT):
        print(f"  received chunk: {len(chunk)} bytes")
        all_audio.extend(chunk)

    print(f"\nTotal audio: {len(all_audio)} bytes. Playing back...")
    audio_array = np.frombuffer(bytes(all_audio), dtype=np.int16)
    sd.play(audio_array, samplerate=tts.sample_rate)
    sd.wait()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
