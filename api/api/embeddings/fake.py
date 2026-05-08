"""
Deterministic, dependency-free encoder for tests.

Hashes input text with SHA-256, expands the digest into a unit vector,
and returns it. Same text → same vector. Different texts → different
vectors with overwhelming probability. Fast, hermetic, and trivially
reproducible across CI runs.

Not an approximation of E5 — it can't be — but it satisfies every
contract the rest of the system depends on (deterministic, unit-norm,
fixed dimension), which is the only reason a fake exists.
"""

from __future__ import annotations

import hashlib
import struct


class HashEncoder:
    """Deterministic SHA-256-based fake encoder."""

    def __init__(self, dimensions: int = 16) -> None:
        if dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {dimensions}")
        self._dim = dimensions

    @property
    def dimensions(self) -> int:
        return self._dim

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def _embed(self, text: str) -> list[float]:
        # Expand the hash to enough bytes to fill ``dimensions`` floats.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        needed_bytes = self._dim * 4
        repeats = (needed_bytes // len(digest)) + 1
        buffer = (digest * repeats)[:needed_bytes]
        floats = list(struct.unpack(f"{self._dim}f", buffer))

        # Normalise to unit length so cosine similarity reduces to a dot
        # product, matching how the real encoder is configured.
        norm = sum(x * x for x in floats) ** 0.5
        if norm == 0.0:
            # Pathological — would only happen if struct unpacking yields
            # all zeros, which SHA-256 won't produce. Guard anyway.
            return [0.0] * self._dim
        return [x / norm for x in floats]
