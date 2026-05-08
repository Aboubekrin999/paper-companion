"""
Recursive character chunker for paper text.

The chunker takes either raw text or a list of pages and returns ``Chunk``
records with content, sequence index, character offsets in the source, the
page where each chunk starts, and a rough token-count estimate.

Boundaries are chosen by preference: paragraph break first, then sentence
boundaries, then any whitespace, then a hard cut. Consecutive chunks share
roughly ``overlap`` characters so retrieval queries can match across chunk
seams without losing context.

No tokenizer dependency here — token counts are character-based estimates
(roughly 4 chars per token) intended for sizing decisions before the
embedding model is invoked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Ordered from strongest semantic boundary to weakest. The empty string at
# the end signals "hard cut" — accepted as a last resort when no separator
# fits inside the remaining window.
_DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
    "",
)

_PAGE_JOIN = "\n\n"
_CHARS_PER_TOKEN = 4  # rough estimate for XLM-RoBERTa on EN+FR mixes


@dataclass(frozen=True)
class Page:
    """A single page of source text with its 1-based page number."""

    number: int
    text: str


@dataclass(frozen=True)
class Chunk:
    """A chunked passage ready for embedding."""

    content: str
    chunk_index: int
    char_start: int
    char_end: int
    page_number: int | None
    token_count: int


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[Chunk]:
    """
    Chunk a single text blob with no page metadata.

    Use ``chunk_pages`` instead when page-level provenance matters (almost
    always, for paper RAG).
    """
    _validate(chunk_size, overlap)
    pieces = _split_with_offsets(text, chunk_size, overlap, _DEFAULT_SEPARATORS)
    return [
        Chunk(
            content=content,
            chunk_index=i,
            char_start=start,
            char_end=end,
            page_number=None,
            token_count=_estimate_tokens(content),
        )
        for i, (content, start, end) in enumerate(pieces)
    ]


def chunk_pages(
    pages: Sequence[Page],
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[Chunk]:
    """
    Chunk a paper given as a sequence of pages.

    Pages are joined with a paragraph break before chunking so the splitter
    naturally prefers page boundaries; chunks may still span pages when a
    section runs across a page break, which is what we want for retrieval.
    The ``page_number`` on each chunk is the page that contains its
    starting character.
    """
    _validate(chunk_size, overlap)
    if not pages:
        return []

    parts: list[str] = []
    page_offsets: list[tuple[int, int, int]] = []  # (page_number, start, end)
    cursor = 0
    for i, page in enumerate(pages):
        page_offsets.append((page.number, cursor, cursor + len(page.text)))
        parts.append(page.text)
        cursor += len(page.text)
        if i < len(pages) - 1:
            parts.append(_PAGE_JOIN)
            cursor += len(_PAGE_JOIN)

    full = "".join(parts)
    pieces = _split_with_offsets(full, chunk_size, overlap, _DEFAULT_SEPARATORS)
    return [
        Chunk(
            content=content,
            chunk_index=i,
            char_start=start,
            char_end=end,
            page_number=_page_for_offset(start, page_offsets),
            token_count=_estimate_tokens(content),
        )
        for i, (content, start, end) in enumerate(pieces)
    ]


def _validate(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size}) "
            "or the chunker cannot make forward progress"
        )


def _split_with_offsets(
    text: str,
    chunk_size: int,
    overlap: int,
    separators: tuple[str, ...],
) -> list[tuple[str, int, int]]:
    if not text:
        return []
    n = len(text)
    if n <= chunk_size:
        return [(text, 0, n)]

    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            end = _find_boundary(text, start, end, separators)
        chunks.append((text[start:end], start, end))
        if end >= n:
            break
        # Step forward with overlap, snapping to a separator when possible
        # so the overlap doesn't begin mid-word.
        next_start = max(end - overlap, start + 1)
        next_start = _snap_forward(text, next_start, end, separators)
        start = next_start
    return chunks


def _find_boundary(
    text: str,
    start: int,
    end: int,
    separators: tuple[str, ...],
) -> int:
    """
    Return the largest ``boundary <= end`` where the slice ``text[start:boundary]``
    ends on a separator. Falls back to ``end`` (a hard cut) when no separator
    fits within the second half of the candidate window.

    The lower bound prevents tiny degenerate chunks: we require the chunk to
    be at least half of ``end - start`` long. With that lower bound a hard
    cut is always preferable to a boundary so close to ``start`` that the
    chunk carries almost no content.
    """
    min_end = start + max((end - start) // 2, 1)
    for sep in separators:
        if not sep:
            break
        idx = text.rfind(sep, min_end, end)
        if idx != -1:
            return idx + len(sep)
    return end


def _snap_forward(
    text: str,
    start: int,
    upper: int,
    separators: tuple[str, ...],
) -> int:
    """Move ``start`` forward to the first separator boundary at or before ``upper``."""
    for sep in separators:
        if not sep:
            break
        idx = text.find(sep, start, upper)
        if idx != -1:
            return idx + len(sep)
    return start


def _page_for_offset(
    offset: int,
    page_offsets: list[tuple[int, int, int]],
) -> int | None:
    if not page_offsets:
        return None
    for number, page_start, page_end in page_offsets:
        if page_start <= offset < page_end:
            return number
    # Offset landed on a page-join separator or past the last page —
    # attribute it to the closest preceding page.
    last_with_start_le = None
    for number, page_start, _ in page_offsets:
        if page_start <= offset:
            last_with_start_le = number
    return last_with_start_le if last_with_start_le is not None else page_offsets[-1][0]


def _estimate_tokens(content: str) -> int:
    return max(1, len(content) // _CHARS_PER_TOKEN) if content else 0
