# Orchestrator — first version

The conversation state machine. Owns the call lifecycle
(greeting → listening → thinking → responding) and calls the STT Service
as a client of it — the same role your `test_mic_stream.py` script has
been playing all along.

## Why it's structured this way

`call_state.py` is the only file that knows about call states. `orchestrator_service.py`
is the only file that knows how to talk to the STT Service over its
WebSocket contract (`API_CONTRACT.md` in the stt-service project). Neither
the NLU/LLM Service nor the TTS Service exist yet — this version has clearly
marked placeholders exactly where each one plugs in later, so adding them
means filling in those two spots, not rewriting the state machine.

## Setup

1. Make sure the STT Service is already running (separate project, separate
   terminal):
   ```
   uvicorn stt_service:app --reload --port 8000
   ```

2. In this project:
   ```
   python -m pip install -r requirements.txt
   cp .env.example .env
   ```
   Fill in `.env`:
   - `STT_SERVICE_TOKEN` — must match the value in the STT Service's own `.env`
   - `ORCHESTRATOR_TOKEN` — a new, different random string (this one protects
     the Orchestrator's own endpoint, not the STT Service's)

3. Run the Orchestrator:
   ```
   uvicorn orchestrator_service:app --reload --port 8001
   ```

## Test it with your mic

```
python test_call_mic.py
```

Speak into your mic. You should see, in order:
```
Bot: Hello! How can I help you today?
(caller speaking...)
Bot: You said: <whatever you said>
```

That `(caller speaking...)` line proves barge-in detection is flowing all
the way through — it fires the instant you start talking, before your
sentence is even finished.

## What's placeholder vs. real right now

| Piece | Status |
|---|---|
| Call state machine | Real |
| STT Service connection | Real |
| Barge-in signal (`speech_started`) | Real |
| "Understanding" what the caller said | **Real** — calls the NLU/LLM Service with full conversation history |
| The bot's spoken reply | **Placeholder** — sent as text, not audio (no TTS yet) |

## What's next

**TTS Service** — replace `client_ws.send_text({"event": "bot_speech", "text": ...})`
with real synthesized audio, so the bot actually talks instead of sending text.
Once that exists, `test_call_mic.py` becomes a real conversation you can
have out loud with your bot.
