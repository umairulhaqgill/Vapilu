cd# STT Service — API contract

## Endpoint

```
ws://<host>:8000/ws/transcribe?token=<token>&encoding=linear16&sample_rate=16000&language=en
```

## Connection parameters (query string)

| Param | Required | Default | Notes |
|---|---|---|---|
| `token` | Yes, if `STT_SERVICE_TOKEN` is set | — | Rejected with close code `4401` if wrong/missing |
| `encoding` | No | `linear16` | e.g. `linear16` (mic/browser), `mulaw` (Twilio) |
| `sample_rate` | No | `16000` | e.g. `16000` (mic/browser), `8000` (Twilio) |
| `language` | No | `en` | BCP-47 language code |

## Input (client → service)

Binary WebSocket frames only. Each frame = a raw PCM/encoded audio chunk matching the `encoding`/`sample_rate` given at connect time. No wrapping, no JSON, no headers — just the audio bytes.

- Recommended chunk size: ~100ms of audio per frame (e.g. 3200 bytes for 16kHz/16-bit mono)
- Send frames continuously as audio becomes available (real-time pacing, not all at once)
- Closing the client's socket ends the session

## Output (service → client)

Text WebSocket frames, each a single JSON object.

**Speech started event** (caller began talking — use this for barge-in, i.e. interrupting your bot's TTS playback the instant the caller talks over it):
```json
{ "event": "speech_started" }
```

**Transcript event:**
```json
{ "transcript": "hello there", "confidence": 0.98, "is_final": true, "speech_final": true }
```

| Field | Type | Meaning |
|---|---|---|
| `transcript` | string | Recognized text for this chunk |
| `confidence` | float (0–1) | Model's confidence in this transcript — use a threshold to decide whether to trust it or ask the caller to repeat |
| `is_final` | bool | `false` = still refining; `true` = locked in |
| `speech_final` | bool | `true` = a pause was detected — treat as end of an utterance |

**Error event** (sent right before the socket closes):
```json
{ "error": "stt_stream_failed", "detail": "<message>" }
```

## Health check

```
GET /health  ->  { "status": "ok" }
```

## File transcription (pre-recorded audio, not live calls)

For voicemails, saved call recordings, or anything already fully recorded —
not for calls in progress (use the WebSocket above for those).

```
POST /transcribe/file?token=<token>&language=en
Content-Type: multipart/form-data
Body: file=<audio file>
```

**Response:**
```json
{ "transcript": "the full recognized text" }
```

Note: this is a normal request/response call, not a stream — Deepgram's
prerecorded API returns one complete result for the whole file, there's no
partial/progressive output to stream here.
