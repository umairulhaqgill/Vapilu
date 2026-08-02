"""
Pure-Python voice activity detection for the client side.

Why pure Python instead of webrtcvad: webrtcvad (and webrtcvad-wheels) are
native C extensions. On Windows machines with Application Control policies
enabled, unsigned native extensions get blocked from loading - exactly what
happened with Piper's espeakbridge.dll in this project. Energy-based
detection in numpy is less sophisticated than WebRTC's algorithm, but it's
adequate for "did the caller start talking", has zero install risk, and is
easy to tune by hand.

The point of doing this client-side at all: detecting speech locally takes
microseconds, versus waiting for audio to travel to the STT service, get
processed, and have speech_started travel back. That round trip is the
single biggest source of the "it doesn't stop fast enough" feeling.

Honest limitation - echo: if the caller is on speakers rather than
headphones, this WILL hear the bot's own voice and treat it as the caller
talking. Real products solve this with acoustic echo cancellation, which is
genuinely hard and not attempted here. The mitigation used instead is
gating (see is_speech's `muted` parameter) plus a threshold high enough
that quiet bleed-through doesn't trigger it. Headphones avoid the problem
entirely.
"""

import numpy as np


class LocalVAD:
    def __init__(
        self,
        threshold: float = 1200.0,
        speech_frames_required: int = 5,
        silence_frames_required: int = 25,
    ):
        """
        threshold: RMS amplitude (16-bit scale, so 0-32767) above which a
                   frame counts as "loud". The default is a guess - mic
                   sensitivity varies enormously between devices, so run
                   calibrate_vad.py to measure a real value for YOUR setup
                   rather than trusting this number.
        speech_frames_required: consecutive loud frames before declaring
                   speech started. At 20ms frames, 5 = 100ms of continuous
                   sound. This is the main defence against brief noises
                   (keyboard clicks, door bumps, coughs) triggering
                   barge-in: a click is loud but doesn't sustain.
        silence_frames_required: consecutive quiet frames before declaring
                   speech ended. At 20ms frames, 25 = 500ms, long enough to
                   not cut off mid-sentence during natural pauses.
        """
        self.threshold = threshold
        self.speech_frames_required = speech_frames_required
        self.silence_frames_required = silence_frames_required

        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_active = False

    @staticmethod
    def _rms(frame_bytes: bytes) -> float:
        """Root-mean-square amplitude of a 16-bit PCM frame."""
        if not frame_bytes:
            return 0.0
        samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples ** 2)))

    def process(self, frame_bytes: bytes, muted: bool = False) -> str | None:
        """
        Feed one audio frame. Returns:
          "speech_start" - the caller just started talking
          "speech_end"   - the caller just stopped talking
          None           - no state change

        muted: when True, audio is still analyzed for level but can never
        trigger speech_start. Used to gate out known-bad windows (e.g. the
        moment right after we start playing bot audio, when echo is most
        likely on a speaker setup).
        """
        level = self._rms(frame_bytes)
        is_loud = level > self.threshold

        if is_loud and not muted:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
        else:
            self._consecutive_silence += 1
            self._consecutive_speech = 0

        if not self._speech_active and self._consecutive_speech >= self.speech_frames_required:
            self._speech_active = True
            return "speech_start"

        if self._speech_active and self._consecutive_silence >= self.silence_frames_required:
            self._speech_active = False
            return "speech_end"

        return None

    @property
    def speech_active(self) -> bool:
        return self._speech_active

    def reset(self):
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_active = False
