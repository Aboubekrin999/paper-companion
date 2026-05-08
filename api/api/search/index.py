"""
In-memory vector index with brute-force cosine search.

Sized for v1: tens-to-low-hundreds of papers, low-thousands of chunks.
At that scale brute force outperforms an approximate index in latency
*and* recall. When the slot-blocked Supabase deploy lands, swap in
``PgVectorIndex`` (same protocol) and indexes built here become a
fixture for tests.

Vectors are stored as plain ``list[float]`` rather than ``numpy``
arrays to keep the dependency surface small — the encoder hands us
lists and pgvector accepts lists. If the index ever becomes a hot
path, lift to ``numpy`` and benchmark.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    """One ranked result from a vector search."""

    chunk_id: str
    score: float


class InMemoryVectorIndex:
    """Brute-force cosine index. Vectors must all share ``dimensions``."""

    def __init__(self, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {dimensions}")
        self._dim = dimensions
        self._chunk_ids: list[str] = []
        self._vectors: list[list[float]] = []

    @property
    def dimensions(self) -> int:
        return self._dim

    def add(self, chunk_id: str, vector: Sequence[float]) -> None:
        if len(vector) != self._dim:
            raise ValueError(
                f"vector dim {len(vector)} does not match index dim {self._dim}"
            )
        self._chunk_ids.append(chunk_id)
        self._vectors.append(list(vector))

    def add_batch(self, items: Iterable[tuple[str, Sequence[float]]]) -> None:
        for chunk_id, vector in items:
            self.add(chunk_id, vector)

    def search(self, query: Sequence[float], k: int) -> list[SearchHit]:
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if len(query) != self._dim:
            raise ValueError(
                f"query dim {len(query)} does not match index dim {self._dim}"
            )
        if not self._vectors:
            return []

        scored = [
            (cid, _cosine(query, vec))
            for cid, vec in zip(self._chunk_ids, self._vectors)
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [SearchHit(chunk_id=cid, score=score) for cid, score in scored[:k]]

    def __len__(self) -> int:
        return len(self._chunk_ids)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / ((norm_a**0.5) * (norm_b**0.5))
