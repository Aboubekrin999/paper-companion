"""
``VectorIndex`` protocol — the seam between in-memory dev and pgvector prod.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from api.search.index import SearchHit


@runtime_checkable
class VectorIndex(Protocol):
    """Insert chunk vectors, query for top-k by cosine similarity."""

    @property
    def dimensions(self) -> int:
        """Vector size every inserted/queried vector must match."""
        ...

    def add(self, chunk_id: str, vector: Sequence[float]) -> None: ...

    def add_batch(self, items: Iterable[tuple[str, Sequence[float]]]) -> None: ...

    def search(self, query: Sequence[float], k: int) -> list[SearchHit]: ...

    def __len__(self) -> int: ...
