"""
End-to-end ingest: arXiv reference → embedding-ready chunks.

Composes the pure parsers (``parse_arxiv``, ``parse_pdf``,
``chunk_pages``) with the network fetcher into a single function the
HTTP layer can call. Splitting the network step out keeps everything
above this module testable without HTTP, and lets future ingest
sources (DOI, HAL, raw upload) reuse the parser + chunker stack.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from api.ingest.arxiv import ArxivPaper, parse_arxiv
from api.ingest.chunker import Chunk, chunk_pages
from api.ingest.fetcher import fetch_arxiv_pdf
from api.ingest.pdf import parse_pdf


@dataclass(frozen=True)
class IngestResult:
    """Output of a full arXiv ingest run."""

    paper: ArxivPaper
    page_count: int
    chunks: list[Chunk]


def ingest_arxiv(
    reference: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
    client: httpx.Client | None = None,
) -> IngestResult:
    """
    Ingest an arXiv paper end-to-end.

    Args:
        reference: arXiv URL, raw ID, or ``arxiv:`` prefixed string.
        chunk_size: target maximum characters per chunk.
        overlap: characters of overlap between consecutive chunks.
        client: optional pre-built ``httpx.Client`` for connection reuse.

    Raises:
        ValueError: ``reference`` does not contain a recognizable arXiv ID.
    """
    paper = parse_arxiv(reference)
    if paper is None:
        raise ValueError(f"not a recognizable arXiv reference: {reference!r}")
    pdf_bytes = fetch_arxiv_pdf(paper, client=client)
    pages = parse_pdf(pdf_bytes)
    chunks = chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
    return IngestResult(paper=paper, page_count=len(pages), chunks=chunks)
