"""
LLM Protocol + a streaming Claude implementation.

The orchestrator depends on the Protocol so unit tests inject
``FakeLLM`` and never touch the network. ``ClaudeLLM`` wraps
``anthropic.Anthropic.messages.stream`` and uses prompt caching on the
context block — papers are large and the same context is reused across
many follow-up questions about the same paper, so caching is a
straightforward 90%+ cost reduction in this access pattern.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

import anthropic

# Default to Sonnet 4.6 per ADR-003 — strong long-context reading at a
# reasonable price. Override via the ``model`` constructor arg when
# experimenting.
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024


@runtime_checkable
class LLM(Protocol):
    """Streaming chat-completion interface."""

    def stream(self, *, system: str, context: str, question: str) -> Iterator[str]:
        """Yield response text incrementally."""
        ...


class ClaudeLLM:
    """``anthropic.Anthropic`` streaming wrapper with context-block caching."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def stream(self, *, system: str, context: str, question: str) -> Iterator[str]:
        # Caching the context block lets follow-up questions about the same
        # paper hit the cache. The question goes in a separate, uncached
        # block because it changes every turn.
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"Question: {question}",
                    },
                ],
            }
        ]
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream


class FakeLLM:
    """Hermetic LLM for tests. Yields a canned response one chunk at a time."""

    def __init__(self, response: str = "stub answer", *, chunks: int = 4) -> None:
        if chunks <= 0:
            raise ValueError(f"chunks must be positive, got {chunks}")
        self._response = response
        self._chunks = chunks
        self.last_call: dict[str, str] | None = None

    def stream(self, *, system: str, context: str, question: str) -> Iterator[str]:
        # Capture inputs so tests can assert what the orchestrator sent.
        self.last_call = {"system": system, "context": context, "question": question}
        # Split the canned response into roughly even pieces to mimic streaming.
        if not self._response:
            return
            yield  # unreachable; satisfies the generator contract
        size = max(1, len(self._response) // self._chunks)
        for i in range(0, len(self._response), size):
            yield self._response[i : i + size]
