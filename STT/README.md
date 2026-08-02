# STT Service — first test

A minimal, swappable Speech-to-Text service wrapper, using Deepgram as the
first provider. This is step 1 of Phase 2 in the roadmap ("Add STT").

## Why it's structured this way
`stt_client.py` is the only file that knows about Deepgram. Everything else
(`test_transcribe.py`, and later your orchestrator) calls `SttClient`, not
`deepgram` directly. When you eventually benchmark ElevenLabs Scribe or
another provider, you only rewrite this one file.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Get a Deepgram API key (free trial credit included):
   https://console.deepgram.com/signup

3. Copy `.env.example` to `.env` and paste your key in:
   ```
   cp .env.example .env
   ```

4. Add a short test audio file:
   - Create a `sample_audio/` folder
   - Drop in a few seconds of speech as `sample_audio/test.wav`
     (record a voice memo on your phone and transfer it, or use any
     short spoken clip you already have — wav or mp3 both work)

## Run the test

```
python test_transcribe.py
```

Expected output:
```
Transcribing: sample_audio/test.wav

--- Transcript ---
<your spoken words as text>
------------------
```

## What's next (once this works)

- Try `smart_format=False` vs `True` in `stt_client.py` to see the difference
  (adds punctuation, capitalization, formats numbers).
- Swap `model="nova-3"` for other Deepgram models to compare accuracy/cost.

## Streaming version (the real STT Service)

`stt_service.py` turns this into an actual network service: a WebSocket
endpoint that accepts a live audio stream and streams transcripts back in
real time — no waiting for the whole file. This is the version your
Channel Gateway / Orchestrator will actually call once you wire up real calls.

```
Client (browser / orchestrator)  <---WebSocket--->  stt_service.py  <---WebSocket--->  Deepgram
```

### Run the service

```
uvicorn stt_service:app --reload --port 8000
```

Check it's alive: open http://localhost:8000/health — should return `{"status": "ok"}`.

### Test it with a simulated live caller

The test client streams a wav file in small chunks (like a real mic feed)
and prints every transcript event as it arrives.

1. Your test file needs to be **16kHz, 16-bit, mono PCM** to match the
   settings in `stt_client.py`. Convert any file with ffmpeg:
   ```
   ffmpeg -i sample_audio/test.wav -ar 16000 -ac 1 -sample_fmt s16 sample_audio/test16k.wav
   ```
2. With the service running in one terminal, run in another:
   ```
   python test_stream_client.py
   ```
3. You'll see a stream of JSON events like:
   ```
   Transcript event: {"transcript": "hello", "is_final": false, "speech_final": false}
   Transcript event: {"transcript": "hello there", "is_final": true, "speech_final": true}
   ```
   `is_final: false` = interim guess, still refining. `is_final: true` =
   Deepgram has locked in that chunk of speech. `speech_final: true` means
   it also detected a pause — a natural point to treat as "the caller
   finished a sentence" in your orchestrator.

### Notes for when you connect this to a real telephony gateway

- Twilio Media Streams sends **8kHz mulaw** audio, not 16kHz linear16 — you'll
  need a second `live_connection()` config (or a parameter) for that format.
  Update `encoding`/`sample_rate` in `stt_client.py` accordingly, or extend
  `live_connection()` to accept them as arguments instead of hardcoding.
- Right now the service holds one Deepgram connection per client connection —
  fine for testing, and actually the right model for calls too (one call =
  one stream), but keep an eye on concurrency/connection limits on your
  Deepgram plan as you scale to many simultaneous calls.
- `is_final`/`speech_final` events are what your Orchestrator will use to
  decide "the caller stopped talking, time to send this to the LLM."

## Live mic test (the real real-time test)

`test_mic_stream.py` streams your laptop mic straight into the service —
speak and watch transcripts appear as you talk.

1. Make sure `sounddevice` installed cleanly:
   ```
   python -m pip install -r requirements.txt
   ```
   On Windows this just works (PortAudio ships inside the wheel). On Mac/Linux,
   if the import fails, install PortAudio first (`brew install portaudio` or
   `sudo apt install libportaudio2`), then reinstall.

2. With the service running in one terminal:
   ```
   uvicorn stt_service:app --reload --port 8000
   ```

3. In another terminal:
   ```
   python test_mic_stream.py
   ```

4. Speak into your mic. You should see JSON transcript events streaming in
   live, with `is_final` flipping to `true` each time you pause. Ctrl+C to stop.

If nothing shows up: check your OS mic permissions for the terminal/Python,
and confirm your default input device is actually your laptop mic (not a
disabled or virtual device) — `python -c "import sounddevice as sd; print(sd.query_devices())"`
lists everything available if you need to pick a specific one.

## Making this a real service (before wiring up the Orchestrator)

Four things changed to turn this from "a script that works" into something
safe to leave running and call from other services:

1. **Auth token required.** Set `STT_SERVICE_TOKEN` in `.env` to any random
   string. The WebSocket now rejects connections that don't pass
   `?token=<the same string>` — before this, anyone who found your port could
   use your Deepgram credits. Both test clients already read the token from
   `.env` automatically. If `STT_SERVICE_TOKEN` is left unset, the service
   still runs (handy for quick local testing) but logs a loud warning that
   it's unauthenticated — don't leave it that way anywhere reachable by
   anyone but you.

2. **Audio format is now a parameter, not hardcoded.** The endpoint accepts
   `?encoding=...&sample_rate=...&language=...` query params (defaulting to
   `linear16` / `16000` / `en` for your mic tests). When you wire up Twilio
   later, it'll connect with `?encoding=mulaw&sample_rate=8000` instead —
   no code changes needed in this service.

3. **Errors are reported to the client, not just logged.** If Deepgram drops
   or errors mid-call, the client now gets a JSON `{"error": ...}` message
   before the socket closes, instead of silently disconnecting — this will
   save you real debugging time once this is buried inside a bigger system.

4. **Every connection gets a short ID in its log lines** (e.g. `[a0551e58]`),
   so once you have multiple simultaneous calls, you can actually tell their
   logs apart.

### Updated run command

Nothing changes about how you start it — just make sure `.env` has both
`DEEPGRAM_API_KEY` and `STT_SERVICE_TOKEN` set before running:

```
uvicorn stt_service:app --reload --port 8000
```

### Still fine to leave for later (not blocking the next service)

- Dockerizing this — worth doing once you have 2-3 services to run together.
- Full metrics/observability (latency percentiles, error rates) — add once
  you have real traffic to monitor.
- Per-tenant model/config selection — ties into the Tenant Config service
  from the architecture doc, build that when you actually onboard a second
  business.
