"""
Chat orchestrator: question → top-k retrieval → grounded LLM answer.

Pure plumbing. The encoder, vector index, chunk lookup and LLM are all
injected; this module owns only (a) the order of operations, (b) the
shape of the context block handed to the model, and (c) the citation
records that the UI uses to render footnote chips.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Mapping

from api.chat.llm import LLM
from api.chat.prompts import SYSTEM_PROMPT, build_user_message, format_chunk_block
from api.embeddings.encoder import Encoder
from api.ingest.chunker import Chunk
from api.search.protocol import VectorIndex


@dataclass(frozen=True)
class Citation:
    """One retrieved chunk that grounded the answer.

    The UI uses ``snippet`` for hover-cards and the ``page_number`` to
    scroll the source into view. ``score`` is exposed so the UI can
    visually de-emphasise low-confidence citations.
    """

    chunk_id: str
    page_number: int | None
    snippet: str
    score: float


@dataclass
class ChatContext:
    """Bundle of injected components the orchestrator depends on."""

    encoder: Encoder
    index: VectorIndex
    chunks_by_id: Mapping[str, Chunk]
    llm: LLM


@dataclass(frozen=True)
class ChatResult:
    """The output of a single ``answer`` call.

    ``citations`` is materialised eagerly (the full retrieval result),
    while ``answer_stream`` is the token iterator; consume one before
    consuming the other if your UI shows citations next to the
    streaming text.
    """

    citations: list[Citation]
    answer_stream: Iterator[str]


SNIPPET_CHARS = 240


def answer(
    question: str,
    ctx: ChatContext,
    *,
    k: int = 5,
    snippet_chars: int = SNIPPET_CHARS,
) -> ChatResult:
    """
    Run one end-to-end chat turn.

    Encodes the query, retrieves the top-k chunks from the injected
    index, builds a context block for the LLM, and returns a
    ``ChatResult`` whose ``answer_stream`` is the LLM's token stream
    and whose ``citations`` describe the chunks the model was given.

    Raises ``KeyError`` if the index returns a chunk_id missing from
    ``ctx.chunks_by_id`` — that's a contract violation between the
    indexer and the chunk store, surfaced loudly rather than papered
    over with empty citations.
    """
    if not question.strip():
        raise ValueError("question must not be empty")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    [query_vec] = ctx.encoder.encode_queries([question])
    hits = ctx.index.search(query_vec, k=k)

    citations: list[Citation] = []
    blocks: list[str] = []
    for hit in hits:
        chunk = ctx.chunks_by_id[hit.chunk_id]
        snippet = chunk.content[:snippet_chars]
        if len(chunk.content) > snippet_chars:
            snippet = snippet.rstrip() + "…"
        citations.append(
            Citation(
                chunk_id=hit.chunk_id,
                page_number=chunk.page_number,
                snippet=snippet,
                score=hit.score,
            )
        )
        blocks.append(
            format_chunk_block(
                chunk_id=hit.chunk_id,
                page_number=chunk.page_number,
                content=chunk.content,
            )
        )

    user_message = build_user_message(question, blocks)
    stream = ctx.llm.stream(
        system=SYSTEM_PROMPT,
        context=user_message,
        question=question,
    )
    return ChatResult(citations=citations, answer_stream=stream)
