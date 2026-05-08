"""
Chat orchestration: retrieve top-k chunks, ground a Claude answer in them.

The orchestrator is plain Python — encoder, vector index, chunk lookup
and LLM are all injected so the same code path runs in tests against a
``FakeLLM`` and in production against ``ClaudeLLM``. The HTTP route
that wraps this lives in the API surface (added in a follow-up PR).
"""

from api.chat.llm import LLM, ClaudeLLM, FakeLLM
from api.chat.orchestrator import (
    ChatContext,
    ChatResult,
    Citation,
    answer,
)
from api.chat.prompts import SYSTEM_PROMPT

__all__ = [
    "LLM",
    "ClaudeLLM",
    "FakeLLM",
    "ChatContext",
    "ChatResult",
    "Citation",
    "answer",
    "SYSTEM_PROMPT",
]
