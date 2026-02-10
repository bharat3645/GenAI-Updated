"""
Abstracted LLM provider using LiteLLM.

Supports Ollama (local), OpenAI, Anthropic — swap by changing env vars.
All services import this instead of making direct LLM calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import litellm
from litellm import acompletion, aembedding

from .config import get_settings

logger = logging.getLogger(__name__)

# Suppress litellm noise
litellm.suppress_debug_info = True


class LLMProvider:
    """Unified LLM interface backed by Ollama via LiteLLM."""

    def __init__(self, model: str | None = None, embed_model: str | None = None):
        settings = get_settings()
        self._model = model or f"ollama/{settings.ollama.model}"
        self._embed_model = embed_model or f"ollama/{settings.ollama.embed_model}"
        self._base_url = settings.ollama.base_url

    # ── Text Completion ──────────────────────────────────────────

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Single-shot completion. Returns the full response text."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_base": self._base_url,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await acompletion(**kwargs)
        return response.choices[0].message.content

    async def complete_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming completion. Yields token chunks."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await acompletion(
            model=model or self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_base=self._base_url,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ── Structured Output ────────────────────────────────────────

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict | list:
        """Completion that parses the response as JSON."""
        if system:
            system += "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        else:
            system = "You MUST respond with valid JSON only. No markdown, no explanation."

        raw = await self.complete(
            prompt,
            system=system,
            model=model,
            temperature=temperature,
        )

        # Try to extract JSON from the response
        raw = raw.strip()
        if raw.startswith("```"):
            # Strip markdown code fences
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        return json.loads(raw)

    # ── Embeddings ───────────────────────────────────────────────

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        response = await aembedding(
            model=model or self._embed_model,
            input=texts,
            api_base=self._base_url,
        )
        return [item["embedding"] for item in response.data]

    async def embed_single(self, text: str, *, model: str | None = None) -> list[float]:
        """Embed a single text string."""
        result = await self.embed([text], model=model)
        return result[0]


# Module-level singleton
_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Return a module-level LLMProvider singleton."""
    global _provider
    if _provider is None:
        _provider = LLMProvider()
    return _provider
