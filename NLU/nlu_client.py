"""
Generic NLU/LLM Service wrapper - now using OpenRouter instead of calling
Anthropic directly.

OpenRouter is a gateway in front of many providers (including Anthropic),
speaking the OpenAI-compatible chat completions format rather than
Anthropic's native Messages format. Two real differences from a direct
Anthropic integration:

1. The system prompt goes IN the messages list as a {"role": "system", ...}
   entry, not as a separate top-level parameter like Anthropic's API uses.
2. The model string is an OpenRouter "slug" in provider/model form, e.g.
   "anthropic/claude-sonnet-4.6" - not the raw Anthropic model ID. Browse
   current slugs at https://openrouter.ai/models. You can also use the
   "~anthropic/claude-sonnet-latest" alias form to always resolve to the
   newest version in a family without updating this code.

Same philosophy as before: this is the only file that knows which provider
or API shape is behind it. Everything else calls NluClient.get_reply() and
never needs to know OpenRouter is involved at all.
"""

import json
import os
from typing import AsyncIterator

from openai import AsyncOpenAI, OpenAI

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful voice assistant answering phone calls for a business. "
    "Keep replies short and conversational - like something a person would "
    "actually say out loud, not something they'd read. Avoid bullet points, "
    "numbered lists, markdown, or long multi-sentence explanations. If you "
    "don't have enough information to help, say so plainly and ask a "
    "clarifying question."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class NluClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "anthropic/claude-sonnet-4.6",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 150,
    ):
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError(
                "No OpenRouter API key found. Set OPENROUTER_API_KEY in your "
                "environment or .env file, or pass api_key= explicitly."
            )
        self._client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)
        self._async_client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens

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

        Tool call arguments arrive as fragments across many chunks and have
        to be reassembled by index before they can be parsed - that's what
        the tool_buffers bookkeeping below is doing.
        """
        system_prompt = self._build_system_prompt(tenant_context)
        if flow_instructions:
            system_prompt += "\n\n" + flow_instructions

        messages = [{"role": "system", "content": system_prompt}] + conversation_history

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

        if extract_fields:
            properties = {}
            for f in extract_fields:
                spec = {"type": "string", "description": f.get("prompt", f["name"])}
                if f.get("options"):
                    spec["enum"] = f["options"]
                properties[f["name"]] = spec

            kwargs["tools"] = [{
                "type": "function",
                "function": {
                    "name": "record_details",
                    "description": (
                        "Record details the caller just provided. Call this whenever "
                        "the caller gives any of these details, including several at "
                        "once. Only include fields they actually stated - never guess "
                        "or fill in placeholder values."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                    },
                },
            }]

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
