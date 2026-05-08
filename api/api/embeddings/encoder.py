"""
Encoder protocol.

The rest of the system depends on this protocol, not on any concrete
implementation. That keeps the eval harness, vector index, and HTTP
routes unaware of whether vectors come from a self-hosted XLM-R, a
hosted inference API, or a deterministic test fake.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Encoder(Protocol):
    """Asymmetric text encoder.

    Most modern dense retrievers (E5, BGE, GTE) treat queries and
    passages slightly differently — at minimum via a prompt prefix.
    Encoding both through a single ``encode`` method works but
    silently degrades retrieval quality, so the protocol forces the
    caller to declare intent.
    """

    @property
    def dimensions(self) -> int:
        """Output vector size. Must match the schema's ``vector(N)`` column."""
        ...

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        """Encode chunks/documents for indexing."""
        ...

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        """Encode user queries for retrieval."""
        ...
