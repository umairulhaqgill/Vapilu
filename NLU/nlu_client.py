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

    def get_reply(self, conversation_history: list[dict]) -> str:
        """
        conversation_history: the FULL conversation so far, as a list of
        {"role": "user" | "assistant", "content": "..."} dicts. The system
        prompt is prepended automatically - don't include it yourself.

        Returns just the reply text.
        """
        messages = [{"role": "system", "content": self._system_prompt}] + conversation_history

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

    async def get_reply_stream(self, conversation_history: list[dict]) -> AsyncIterator[str]:
        """
        Same as get_reply, but yields the reply as it's generated instead of
        waiting for the whole thing. This is what makes the bot feel
        responsive instead of pausing for its entire answer before saying
        anything - critical once TTS exists, since it lets speech start on
        the first sentence while later sentences are still being generated.

        Yields plain text deltas (small chunks of new text, not the
        cumulative text so far) - the caller is responsible for
        accumulating them if it needs the full reply at the end.
        """
        messages = [{"role": "system", "content": self._system_prompt}] + conversation_history

        stream = await self._async_client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=messages,
            stream=True,
            extra_headers={
                "HTTP-Referer": "https://github.com/",
                "X-Title": "Voice Bot NLU Service",
            },
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta