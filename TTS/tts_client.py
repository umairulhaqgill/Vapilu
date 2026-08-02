"""
Generic TTS Service wrapper around Piper (local, free, offline neural TTS).

Same philosophy as stt_client.py and nlu_client.py: this is the only file
that knows Piper is involved. Everything else calls TtsClient.synthesize_stream()
and would never need to change if you swap to a cloud provider later.

Important implementation detail: Piper's synthesize() is a SYNCHRONOUS,
CPU-bound generator - it does real computation to produce audio, and it
does not know about asyncio at all. Calling it directly inside an async
function would block the entire event loop for as long as synthesis takes,
freezing every other concurrent call this service is handling. To avoid
that, synthesize_stream() runs the actual Piper call on a background
thread and feeds chunks back to the async caller through a queue.
"""

import asyncio
import threading
from pathlib import Path
from typing import AsyncIterator

from piper import PiperVoice


class TtsClient:
    def __init__(self, model_path: str, config_path: str | None = None):
        """
        model_path: path to the .onnx voice model file.
        config_path: path to the matching .onnx.json config file. If None,
                     Piper looks for "<model_path>.json" automatically.
        """
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Piper voice model not found at {model_path}. "
                f"Download one with: python -m piper.download_voices <voice_name> "
                f"(see README for details and voice name options)."
            )
        self._voice = PiperVoice.load(model_path, config_path=config_path)
        self.sample_rate = self._voice.config.sample_rate
        self.sample_width = 2   # Piper outputs 16-bit PCM
        self.channels = 1       # mono

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Yields raw 16-bit PCM audio chunks as they're generated, without
        blocking the event loop. Pass one complete sentence/utterance at a
        time for best results - Piper synthesizes what you give it as one
        unit, so partial words or sentence fragments won't sound right.
        """
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        DONE = object()

        def run_synthesis():
            try:
                for chunk in self._voice.synthesize(text):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk.audio_int16_bytes)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, DONE)

        thread = threading.Thread(target=run_synthesis, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item is DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item
