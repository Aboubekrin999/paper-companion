"""
Real ``intfloat/multilingual-e5-large`` encoder.

Wraps ``sentence-transformers`` with the prompt prefixes E5 was trained
with — ``query: ...`` for retrieval queries, ``passage: ...`` for
indexed chunks — and returns L2-normalised vectors so cosine similarity
collapses to a dot product (matching ADR-002's pgvector setup).

``sentence-transformers`` is imported lazily so importing this module
in an environment without the ML stack raises a clean
``RuntimeError`` instead of an ``ImportError`` at import time. CI runs
without the ML deps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "intfloat/multilingual-e5-large"
_E5_DIMENSIONS = 1024  # multilingual-e5-large output


class E5Encoder:
    """``multilingual-e5-large`` via ``sentence-transformers``."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        device: str | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only without the dep
            raise RuntimeError(
                "E5Encoder requires sentence-transformers. "
                "Install with `pip install sentence-transformers` or use "
                "HashEncoder for tests."
            ) from exc

        self._model: SentenceTransformer = SentenceTransformer(
            model_name, device=device
        )
        # Trust the model's reported dimension over the constant when it
        # disagrees — protects against passing a non-large variant.
        reported = self._model.get_sentence_embedding_dimension()
        self._dim = reported if reported else _E5_DIMENSIONS

    @property
    def dimensions(self) -> int:
        return self._dim

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {t}" for t in texts])

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"query: {t}" for t in texts])

    def _encode(self, prefixed: list[str]) -> list[list[float]]:
        if not prefixed:
            return []
        vectors: Any = self._model.encode(
            prefixed,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
