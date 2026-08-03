"""
Generic NLU/LLM Service wrapper. Two backends:

  "openrouter" (default) - OpenRouter, a gateway in front of many providers
  (including Anthropic), speaking the OpenAI-compatible chat completions
  format rather than Anthropic's native Messages format. Two real
  differences from a direct Anthropic integration:

  1. The system prompt goes IN the messages list as a {"role": "system", ...}
     entry, not as a separate top-level parameter like Anthropic's API uses.
  2. The model string is an OpenRouter "slug" in provider/model form, e.g.
     "anthropic/claude-sonnet-4.6" - not the raw Anthropic model ID. Browse
     current slugs at https://openrouter.ai/models. You can also use the
     "~anthropic/claude-sonnet-latest" alias form to always resolve to the
     newest version in a family without updating this code.

  "ollama" - a local/LAN Ollama server, for when OpenRouter is unreachable
  or out of credits. Deliberately NOT going through Ollama's OpenAI-compat
  /v1 endpoint despite it existing: hybrid-reasoning models (qwen3.5 here)
  emit chain-of-thought into a separate "reasoning" field before the real
  answer, and that reasoning can only be turned off with think=False - a
  parameter the /v1 compat layer silently ignores. Measured on qwen3.5:4b:
  through /v1 it burned an entire 600-token budget on reasoning in 15+
  seconds and never produced an answer; through Ollama's native /api/chat
  with think=False it answers directly in under a second. So this backend
  speaks that native API with plain httpx instead of the openai SDK - a
  real difference in wire format, not just a base_url swap.

Same philosophy as before: this is the only file that knows which provider
or API shape is behind it. Everything else calls NluClient.get_reply() and
never needs to know OpenRouter or Ollama is involved at all.
"""

import json
import os
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI, OpenAI

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful voice assistant answering phone calls for a business. "
    "This is a spoken phone call, not a chat window - reply the way a "
    "person actually talks on the phone: one short sentence, sometimes just "
    "a few words. Never more than one sentence per turn. Never bullet "
    "points, numbered lists, markdown, or multi-sentence explanations. Ask "
    "one thing at a time. If you don't have enough information to help, say "
    "so plainly and ask a short clarifying question - still one sentence. "
    "Every turn, you must say something out loud - even on turns where you "
    "also record details with a tool call. The caller can only hear your "
    "spoken words, never the tool call itself, so a tool call with no "
    "accompanying reply is silence to them: they'll think the call dropped "
    "and repeat themselves. At minimum, a few words confirming what you "
    "heard and asking for whatever's next."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class NluClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        model: str = "anthropic/claude-sonnet-4.6",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 150,
    ):
        self._provider = provider or os.environ.get("NLU_PROVIDER", "openrouter")
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens

        if self._provider == "ollama":
            ollama_base = (base_url or os.environ.get("NLU_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
            self._ollama_sync = httpx.Client(base_url=ollama_base, timeout=60.0)
            self._ollama_async = httpx.AsyncClient(base_url=ollama_base, timeout=60.0)
            self._client = None
            self._async_client = None
        else:
            base_url = base_url or os.environ.get("NLU_BASE_URL") or OPENROUTER_BASE_URL
            key = api_key or os.environ.get("NLU_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise ValueError(
                    "No OpenRouter API key found. Set OPENROUTER_API_KEY in your "
                    "environment or .env file, or pass api_key= explicitly."
                )
            self._client = OpenAI(base_url=base_url, api_key=key)
            self._async_client = AsyncOpenAI(base_url=base_url, api_key=key)
            self._ollama_sync = None
            self._ollama_async = None

    def _build_system_prompt(self, tenant_context: dict | None) -> str:
        """
        Combines the generic voice-assistant instructions with this
        business's own context. Without tenant context this returns the
        base prompt unchanged, so a call with no tenant still works.
        """
        if not tenant_context:
            return self._system_prompt

        parts = [self._system_prompt]

        business_name = tenant_context.get("business_name")
        if business_name:
            parts.append(f"You are answering calls for: {business_name}.")

        extra = tenant_context.get("system_prompt_extra")
        if extra:
            parts.append(extra)

        capabilities = tenant_context.get("capabilities")
        if capabilities:
            listed = "; ".join(capabilities)
            parts.append(
                f"You can help with: {listed}. "
                "If asked for something outside this, say plainly that you "
                "can't help with that rather than improvising."
            )

        hours = tenant_context.get("business_hours")
        if hours:
            day_parts = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                value = hours.get(day)
                day_parts.append(f"{day.capitalize()}: {value if value else 'closed'}")
            timezone = hours.get("timezone", "UTC")
            parts.append(f"Opening hours ({timezone}) - " + ", ".join(day_parts) + ".")

        escalation = tenant_context.get("escalation_phone")
        if escalation:
            parts.append(
                "If the caller asks for a human, or you cannot help them, "
                f"offer to transfer them to {escalation}."
            )

        return "\n\n".join(parts)

    def get_reply(self, conversation_history: list[dict], tenant_context: dict | None = None) -> str:
        """
        conversation_history: the FULL conversation so far, as a list of
        {"role": "user" | "assistant", "content": "..."} dicts. The system
        prompt is prepended automatically - don't include it yourself.

        Returns just the reply text.
        """
        messages = [{"role": "system", "content": self._build_system_prompt(tenant_context)}] + conversation_history

        if self._provider == "ollama":
            resp = self._ollama_sync.post("/api/chat", json={
                "model": self._model,
                "messages": messages,
                "think": False,
                "stream": False,
            })
            resp.raise_for_status()
            return resp.json()["message"]["content"] or ""

        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=messages,
            extra_headers={
                # Optional but recommended by OpenRouter for attribution on
                # their leaderboards - harmless to leave as-is, or remove.
                "HTTP-Referer": "https://github.com/",
                "X-Title": "Voice Bot NLU Service",
            },
        )
        return response.choices[0].message.content or ""

    async def get_reply_stream(
        self,
        conversation_history: list[dict],
        tenant_context: dict | None = None,
        flow_instructions: str | None = None,
        extract_fields: list[dict] | None = None,
    ):
        """
        Streams the reply, and - when extract_fields is given - also reports
        which of those fields the caller just supplied.

        Yields dicts rather than plain strings:
          {"delta": "..."}      a chunk of reply text
          {"extracted": {...}}  field values the caller gave this turn

        Why one call instead of two: extraction and replying could be
        separate LLM calls, but that would double the latency on the
        critical path of every turn. Tool calling lets the model do both in
        one pass - it reports what it heard AND answers naturally.

        OpenRouter's tool call arguments arrive as fragments across many
        chunks and have to be reassembled by index before they can be
        parsed - that's what the tool_buffers bookkeeping below is doing.
        Ollama's native API doesn't fragment them (see _ollama_stream).
        """
        system_prompt = self._build_system_prompt(tenant_context)
        if flow_instructions:
            system_prompt += "\n\n" + flow_instructions

        messages = [{"role": "system", "content": system_prompt}] + conversation_history
        tools = self._tool_spec(extract_fields)

        if self._provider == "ollama":
            async for item in self._ollama_stream(messages, tools):
                yield item
            return

        kwargs = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
            "stream": True,
            "extra_headers": {
                "HTTP-Referer": "https://github.com/",
                "X-Title": "Voice Bot NLU Service",
            },
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self._async_client.chat.completions.create(**kwargs)

        tool_buffers: dict[int, str] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                yield {"delta": delta.content}

            for call in (delta.tool_calls or []):
                # Arguments arrive in fragments keyed by index - concatenate
                # until the stream ends, then parse once.
                tool_buffers[call.index] = tool_buffers.get(call.index, "")
                if call.function and call.function.arguments:
                    tool_buffers[call.index] += call.function.arguments

        for raw in tool_buffers.values():
            if not raw.strip():
                continue
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError:
                # A truncated or malformed tool call means we didn't hear a
                # usable value. Better to drop it and re-ask than to record
                # something wrong into a real booking.
                continue
            if isinstance(extracted, dict) and extracted:
                yield {"extracted": extracted}

    @staticmethod
    def _tool_spec(extract_fields: list[dict] | None) -> list[dict] | None:
        """Same tool-call JSON schema shape for both backends - OpenAI and
        Ollama's native API both use {"type": "function", "function": {...}}."""
        if not extract_fields:
            return None
        properties = {}
        for f in extract_fields:
            spec = {"type": "string", "description": f.get("prompt", f["name"])}
            if f.get("options"):
                spec["enum"] = f["options"]
            properties[f["name"]] = spec

        return [{
            "type": "function",
            "function": {
                "name": "record_details",
                "description": (
                    "Record details the caller just provided. Call this whenever "
                    "the caller gives any of these details, including several at "
                    "once. Only include fields they actually stated - never guess "
                    "or fill in placeholder values. Calling this tool does NOT "
                    "say anything to the caller - you must ALSO reply in words "
                    "in the same turn (e.g. confirm what you recorded and ask "
                    "for the next thing), or the caller hears nothing at all."
                ),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }]

    async def _ollama_stream(self, messages: list[dict], tools: list[dict] | None):
        """
        Ollama's native /api/chat, streaming. Newline-delimited JSON like
        OpenRouter's stream, but shaped differently: each line carries the
        full incremental message, content is the new text only (an actual
        delta, not accumulated), and - unlike OpenRouter - tool call
        arguments arrive already parsed as a JSON object in one line rather
        than fragmented across many, so there's no reassembly step here.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "think": False,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with self._ollama_async.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                message = chunk.get("message") or {}

                content = message.get("content")
                if content:
                    yield {"delta": content}

                for call in message.get("tool_calls") or []:
                    args = call.get("function", {}).get("arguments")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            continue
                    if isinstance(args, dict) and args:
                        yield {"extracted": args}
