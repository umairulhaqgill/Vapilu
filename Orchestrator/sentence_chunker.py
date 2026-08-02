"""
Splits streaming text into complete sentences as they become available.

Why this exists: TTS should synthesize whole sentences, not word fragments -
feeding it "Sure, we ha" then "ve openings" would sound broken. But the NLU
Service streams text as small token deltas, not whole sentences. This module
bridges the two: accumulate deltas into a buffer, and whenever a sentence
boundary appears, emit everything up to and including it, keeping the
(possibly incomplete) remainder buffered for next time.
"""

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class SentenceChunker:
    def __init__(self):
        self._buffer = ""

    def add(self, delta: str) -> list[str]:
        """
        Feed in a new text delta. Returns a list of any complete sentences
        that are now ready (usually 0 or 1, occasionally more if a delta
        happens to complete several short sentences at once).
        """
        self._buffer += delta
        parts = _SENTENCE_BOUNDARY.split(self._buffer)

        if len(parts) <= 1:
            return []  # no sentence boundary yet, keep buffering

        complete_sentences = parts[:-1]
        self._buffer = parts[-1]  # last part might still be incomplete
        return complete_sentences

    def flush(self) -> str | None:
        """
        Call once the NLU stream is done. Returns whatever text is left in
        the buffer (the final sentence almost never ends with trailing
        whitespace after its punctuation, so it wouldn't otherwise get
        emitted by add()) - or None if nothing's left.
        """
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining or None
