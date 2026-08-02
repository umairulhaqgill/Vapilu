"""
Generic STT Service wrapper.

This is the "STT Service" microservice from the architecture doc, implemented
as a small Python class for now. Keep every Deepgram-specific detail inside
this file — the rest of your bot (orchestrator, tests, etc.) should only ever
call these methods, never import `deepgram` directly. That way, swapping to
ElevenLabs/AssemblyAI/Whisper later means rewriting this one file only.
"""

import os
from contextlib import asynccontextmanager
from deepgram import DeepgramClient, AsyncDeepgramClient


class SttClient:
    def __init__(self, api_key: str | None = None, model: str = "nova-3"):
        """
        api_key: falls back to the DEEPGRAM_API_KEY environment variable.
        model:   "nova-3" is Deepgram's current best-value general model.
        """
        key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not key:
            raise ValueError(
                "No Deepgram API key found. Set DEEPGRAM_API_KEY in your "
                "environment or .env file, or pass api_key= explicitly."
            )
        self._api_key = key
        self._client = DeepgramClient(api_key=key)
        self._model = model

    def transcribe_file(self, file_path: str, language: str = "en") -> str:
        """
        Transcribes a local audio file (wav, mp3, m4a, etc.) and returns the
        plain transcript text. This is the simplest possible test of the
        integration — no streaming, no telephony, just: audio in, text out.
        """
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        return self.transcribe_bytes(audio_bytes, language=language)

    def transcribe_bytes(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Same as transcribe_file, but takes raw audio bytes directly — this is
        what the network-facing /transcribe/file endpoint uses, since it
        receives an uploaded file's bytes rather than a local path.
        """
        response = self._client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model=self._model,
            language=language,
            smart_format=True,   # adds punctuation/casing
            punctuate=True,
        )
        return self._extract_transcript(response)

    @staticmethod
    def _extract_transcript(response) -> str:
        """Pulls the plain transcript text out of Deepgram's response object."""
        channel = response.results.channels[0]
        alternative = channel.alternatives[0]
        return alternative.transcript

    @asynccontextmanager
    async def live_connection(
        self,
        encoding: str = "linear16",
        sample_rate: int = 16000,
        language: str = "en",
    ):
        """
        Opens a live streaming connection to Deepgram. Use as:

            async with stt.live_connection() as dg_socket:
                await dg_socket.send_media(audio_chunk_bytes)
                result = await dg_socket.recv()

        `encoding`/`sample_rate` must match whatever audio format you're
        actually sending — 16kHz linear16 PCM is a safe, common default for
        mic/browser audio. Twilio phone audio is typically 8kHz mulaw, so
        you'll set different values when you wire up the telephony gateway.
        """
        async_client = AsyncDeepgramClient(api_key=self._api_key)
        async with async_client.listen.v1.connect(
            model=self._model,
            language=language,
            encoding=encoding,
            sample_rate=sample_rate,
            interim_results=True,   # get partial results as the caller talks
            smart_format=True,
            punctuate=True,
            vad_events=True,        # emit SpeechStarted events (needed for barge-in)
        ) as dg_socket:
            yield dg_socket
