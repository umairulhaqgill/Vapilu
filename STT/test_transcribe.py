"""
First STT test.

Run this after:
  1. pip install -r requirements.txt
  2. Copy .env.example to .env and add your real Deepgram API key
  3. Put a short audio file (wav/mp3, a few seconds of speech) at
     ./sample_audio/test.wav  — e.g. record yourself saying a sentence
     on your phone and airdrop/transfer it over, or use any sample
     voice clip you have.

Then run:
  python test_transcribe.py
"""

from dotenv import load_dotenv
from stt_client import SttClient

load_dotenv()  # reads .env into environment variables

AUDIO_FILE = "sample_audio/test.wav"

if __name__ == "__main__":
    stt = SttClient()  # picks up DEEPGRAM_API_KEY from environment

    print(f"Transcribing: {AUDIO_FILE}")
    transcript = stt.transcribe_file(AUDIO_FILE)

    print("\n--- Transcript ---")
    print(transcript)
    print("------------------")
