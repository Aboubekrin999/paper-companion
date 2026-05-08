"""
In-memory paper store: ingest, index, and chat against papers in a single process.

Holds three parallel maps keyed by ``paper_id``:
- the ``PaperRecord`` (paper-level metadata for the listing endpoint)
- the per-paper ``InMemoryVectorIndex``
- the per-paper ``chunk_id -> Chunk`` lookup the chat orchestrator needs

State lives only in memory — restart loses everything. That's the
right v1 trade-off: the schema migration in ``infra/supabase/`` is
already authored, and swapping this store for a Supabase-backed
implementation behind the same interface is a focused follow-up once
the slot lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from api.chat.llm import LLM
from api.chat.orchestrator import ChatContext, ChatResult, answer
from api.embeddings.encoder import Encoder
from api.ingest.chunker import Chunk
from api.ingest.pipeline import IngestResult, ingest_arxiv
from api.search import InMemoryVectorIndex
from api.search.protocol import VectorIndex


@dataclass(frozen=True)
class PaperRecord:
    """Paper-level metadata exposed by the listing endpoint."""

    id: str
    arxiv_id: str
    version: int | None
    abs_url: str
    pdf_url: str
    page_count: int
    chunk_count: int


class PaperNotFound(KeyError):
    """Raised when a route looks up a paper_id the store doesn't have."""


class PaperStore:
    """Per-process store of ingested papers, their indices, and their chunks."""

    def __init__(
        self,
        *,
        encoder: Encoder,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._encoder = encoder
        self._http = http_client
        self._papers: dict[str, PaperRecord] = {}
        self._indices: dict[str, VectorIndex] = {}
        self._chunks: dict[str, dict[str, Chunk]] = {}

    def ingest_arxiv(self, reference: str) -> PaperRecord:
        """Pull, parse, chunk, embed, and index a paper. Returns the new record.

        Re-ingesting an existing paper is idempotent: the new run replaces
        the old chunks and index. That makes the route forgiving when a
        user re-submits the same arXiv link.
        """
        result = ingest_arxiv(reference, client=self._http)
        paper_id = result.paper.id

        chunk_ids = [f"{paper_id}-{c.chunk_index}" for c in result.chunks]
        chunks_by_id = dict(zip(chunk_ids, result.chunks))

        index = InMemoryVectorIndex(dimensions=self._encoder.dimensions)
        if result.chunks:
            contents = [c.content for c in result.chunks]
            vectors = self._encoder.encode_passages(contents)
            index.add_batch(zip(chunk_ids, vectors))

        record = self._record_from(result)
        self._papers[paper_id] = record
        self._indices[paper_id] = index
        self._chunks[paper_id] = chunks_by_id
        return record

    def list_papers(self) -> list[PaperRecord]:
        """Records sorted by id for stable, readable JSON output."""
        return sorted(self._papers.values(), key=lambda r: r.id)

    def get(self, paper_id: str) -> PaperRecord:
        if paper_id not in self._papers:
            raise PaperNotFound(paper_id)
        return self._papers[paper_id]

    def chat(self, paper_id: str, question: str, *, k: int, llm: LLM) -> ChatResult:
        if paper_id not in self._papers:
            raise PaperNotFound(paper_id)
        ctx = ChatContext(
            encoder=self._encoder,
            index=self._indices[paper_id],
            chunks_by_id=self._chunks[paper_id],
            llm=llm,
        )
        return answer(question, ctx, k=k)

    def _record_from(self, result: IngestResult) -> PaperRecord:
        paper = result.paper
        return PaperRecord(
            id=paper.id,
            arxiv_id=paper.id,
            version=paper.version,
            abs_url=paper.abs_url,
            pdf_url=paper.pdf_url,
            page_count=result.page_count,
            chunk_count=len(result.chunks),
        )
