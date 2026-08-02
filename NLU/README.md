# NLU/LLM Service

Turns conversation history into the bot's next reply, using Claude via
**OpenRouter** (a gateway that speaks an OpenAI-compatible API in front of
many providers, including Anthropic).

## Why it's structured this way

`nlu_client.py` is the only file that knows about OpenRouter/the OpenAI SDK
- same pattern as `stt_client.py` in the STT project. `nlu_service.py`
exposes it as a plain HTTP endpoint (not a WebSocket - this is a normal
request/response call, no streaming need here the way there is for live audio).

**This service has no memory of its own.** Every request must include the
entire conversation so far. That's intentional: the Orchestrator is the one
that owns and grows conversation history per call - this service just turns
"history so far" into "next reply." See the Orchestrator's `call_state.py`
for where that history actually lives.

## A note on using OpenRouter instead of Anthropic directly

OpenRouter uses the OpenAI-compatible chat completions format, not
Anthropic's native Messages API - two real differences baked into
`nlu_client.py`:
- The system prompt goes inside the `messages` list as a `{"role": "system"}`
  entry, not a separate parameter.
- The model string is an OpenRouter **slug** in `provider/model` form (e.g.
  `anthropic/claude-sonnet-4.6`), not a raw Anthropic model ID. Browse
  current slugs at https://openrouter.ai/models - or use the
  `~anthropic/claude-sonnet-latest` alias to always resolve to the newest
  version without changing code.

## Setup

```
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `OPENROUTER_API_KEY` - from https://openrouter.ai/keys
- `NLU_SERVICE_TOKEN` - a new random string, different from your other services' tokens

## Run it

```
uvicorn nlu_service:app --reload --port 8002
```

## Test a real conversation

```
python test_conversation.py
```

This has a short 3-turn conversation and asks the bot to recall something
from 2 turns earlier - if it answers correctly, you've confirmed the
history is actually being passed through and used, not just the latest message.

## API contract (short version)

```
POST /reply
Body: {
  "token": "...",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    ...
  ]
}
Response: { "reply": "..." }
```

## What's next

This is the piece that plugs into the Orchestrator's placeholder line:
```python
reply_text = f"You said: {transcript}"
```
becomes a real call to this service, with `session.conversation_history`
passed as the request body and the reply appended back into that same
history for the next turn.
