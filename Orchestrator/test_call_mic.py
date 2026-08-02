"""
Voice client with LOCAL barge-in handling.

The key design change from the earlier version: this client no longer waits
for the server to tell it to stop playing audio. It runs its own voice
activity detection on the mic feed, and the moment it hears you start
talking it flushes its own playback buffer immediately - microseconds, not
a network round trip.

The server is still told (so it can cancel generation and reconnect TTS),
but that happens in parallel rather than as a prerequisite. The server's
own bot_interrupted event is still honored as a backstop, in case its STT
detects speech that local VAD missed.

Audio playback also runs through an explicit queue rather than blocking
writes, so "flush everything now" is a real operation - you can't unsend
audio you've already handed to a blocking write.

Requires all four services running (see run_all.ps1), then:
    python test_call_mic.py

Speak into your mic. Ctrl+C to stop.

NOTE ON HEADPHONES: local VAD listens to your mic while the bot's audio
plays. On speakers, it will hear the bot and treat that as you talking
(there's no acoustic echo cancellation here - that's genuinely hard).
Use headphones.
"""

import asyncio
import json
import os
import sys

import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv

from local_vad import LocalVAD

load_dotenv()

ORCHESTRATOR_TOKEN = os.environ.get("ORCHESTRATOR_TOKEN", "")
SERVICE_URL = f"ws://localhost:8001/ws/call?token={ORCHESTRATOR_TOKEN}"
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 20  # smaller frames than before: less buffered audio to be wrong about

# Tune this if barge-in misfires. Run calibrate_vad.py to measure the right
# value for your actual microphone instead of guessing.
VAD_THRESHOLD = float(os.environ.get("VAD_THRESHOLD", "1200"))


class AudioPlayer:
    """
    Queue-based playback so that flushing is actually possible.

    The previous version wrote audio straight to the output stream as it
    arrived, which meant that by the time we wanted to stop, the data was
    already inside PortAudio's own buffer and out of our control. Here,
    incoming audio sits in our queue until a background writer feeds it to
    the device in small pieces - so flush() can genuinely discard what
    hasn't played yet.
    """

    def __init__(self, sample_rate: int, channels: int):
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: asyncio.Queue = asyncio.Queue()
        self._stream = sd.RawOutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            blocksize=int(sample_rate * FRAME_MS / 1000),
        )
        self._stream.start()
        self._writer_task = asyncio.create_task(self._writer())
        self._playing = False

    async def _writer(self):
        while True:
            chunk = await self._queue.get()
            try:
                # write() blocks until the device accepts the data, so hand
                # it small pieces and yield between them - that keeps the
                # event loop responsive AND limits how much is committed to
                # the device at once (i.e. how much we can't take back).
                piece_size = int(self.sample_rate * self.channels * 2 * 0.02)  # ~20ms
                for i in range(0, len(chunk), piece_size):
                    self._stream.write(chunk[i:i + piece_size])
                    await asyncio.sleep(0)
            except Exception as e:
                print(f"[playback error] {e}", file=sys.stderr)
            finally:
                self._playing = not self._queue.empty()

    def play(self, audio_bytes: bytes):
        self._playing = True
        self._queue.put_nowait(audio_bytes)

    def flush(self):
        """Discard everything queued and stop the device immediately."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            self._stream.abort()   # abort(), not stop(): don't drain buffers
            self._stream.start()   # ready again straight away
        except Exception as e:
            print(f"[flush error] {e}", file=sys.stderr)
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing or not self._queue.empty()

    def close(self):
        self._writer_task.cancel()
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass


async def call():
    loop = asyncio.get_event_loop()
    mic_queue: asyncio.Queue = asyncio.Queue()
    player: AudioPlayer | None = None
    vad = LocalVAD(threshold=VAD_THRESHOLD)

    def on_audio_block(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        loop.call_soon_threadsafe(mic_queue.put_nowait, bytes(indata))

    blocksize = int(SAMPLE_RATE * FRAME_MS / 1000)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=blocksize,
        callback=on_audio_block,
    ):
        async with websockets.connect(SERVICE_URL) as ws:

            async def sender():
                """
                Forwards mic audio to the server AND runs local VAD on it.
                On local speech onset, flushes playback immediately - this
                is the whole point of the redesign, and it happens without
                waiting for any server response.
                """
                nonlocal player
                while True:
                    chunk = await mic_queue.get()
                    await ws.send(chunk)

                    event = vad.process(chunk)
                    if event == "speech_start":
                        if player is not None and player.is_playing:
                            player.flush()
                            print(" [barge-in: audio stopped locally]")
                        # Tell the server too, so it can cancel generation
                        # and reset TTS - but we've ALREADY stopped playing,
                        # so this isn't on the critical path for how fast
                        # the interruption feels.
                        await ws.send(json.dumps({"event": "client_speech_start"}))

            async def receiver():
                nonlocal player
                bot_is_speaking = False
                async for message in ws:
                    if isinstance(message, bytes):
                        if player is not None:
                            player.play(message)
                        continue

                    data = json.loads(message)
                    event = data.get("event")

                    if event == "audio_format":
                        player = AudioPlayer(data["sample_rate"], data["channels"])
                    elif event == "caller_speaking":
                        pass  # already handled locally, far earlier
                    elif event == "bot_interrupted":
                        # Backstop: the server's STT caught speech our local
                        # VAD missed. Usually redundant - we've normally
                        # already flushed - but harmless and worth keeping.
                        if player is not None:
                            player.flush()
                        if bot_is_speaking:
                            print()
                        bot_is_speaking = False
                    elif event == "bot_speech":
                        print(f"Bot: {data['text']}")
                    elif event == "bot_speech_chunk":
                        if not bot_is_speaking:
                            print("Bot: ", end="", flush=True)
                            bot_is_speaking = True
                        print(data["text"], end="", flush=True)
                    elif event == "bot_speech_end":
                        print()
                        bot_is_speaking = False
                    elif "error" in data:
                        print(f"[error] {data['error']}: {data.get('detail')}")

            print("Call connected. Speak into your mic. Ctrl+C to stop.")
            print("(Use headphones - local VAD has no echo cancellation.)\n")
            try:
                await asyncio.gather(sender(), receiver())
            finally:
                if player is not None:
                    player.close()


if __name__ == "__main__":
    try:
        asyncio.run(call())
    except KeyboardInterrupt:
        print("\nCall ended.")
