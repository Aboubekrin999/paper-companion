"""
Encoder protocol + implementations.

Three implementations live here, one per environment (see ADR-007):

- ``HashEncoder`` — deterministic, dependency-free, used in tests so
  the rest of the system can be exercised without pulling torch.
- ``E5Encoder`` — ``intfloat/multilingual-e5-large`` via
  ``sentence-transformers``, for local development. The dependency is
  imported lazily so this module is importable in CI without the ML stack.
- ``HFInferenceEncoder`` — the same weights over the Hugging Face
  Inference API, for deployed environments where 2.2 GB of weights
  cannot ship inside the function.

``build_encoder`` selects between them from ``EMBEDDING_BACKEND``.

The ``Encoder`` protocol distinguishes ``encode_queries`` from
``encode_passages`` because E5 (and most modern asymmetric encoders)
prefix queries and passages differently before encoding. Implementations
that don't care about the distinction can return the same vectors from
both methods.
"""

from __future__ import annotations

import os

from api.embeddings.encoder import Encoder
from api.embeddings.fake import HashEncoder

__all__ = [
    "Encoder",
    "HashEncoder",
    "E5Encoder",
    "HFInferenceEncoder",
    "build_encoder",
    "UnknownBackend",
]

#: ``EMBEDDING_BACKEND`` value used when the variable is unset.
DEFAULT_BACKEND = "hash"

#: Dimensions for ``HashEncoder`` when it is selected by name.
_HASH_DIMENSIONS = 64


class UnknownBackend(ValueError):
    """``EMBEDDING_BACKEND`` named a backend that does not exist."""


def build_encoder(backend: str | None = None) -> Encoder:
    """Construct the encoder named by ``backend`` or ``EMBEDDING_BACKEND``.

    Kept deliberately dumb: no caching, no singletons. Callers that want
    one instance per process hold it themselves, which keeps tests from
    inheriting each other's encoders.
    """
    name = (backend or os.environ.get("EMBEDDING_BACKEND") or DEFAULT_BACKEND).strip().lower()

    if name == "hash":
        return HashEncoder(dimensions=_HASH_DIMENSIONS)
    if name == "e5":
        from api.embeddings.e5 import E5Encoder

        return E5Encoder()
    if name == "hosted":
        from api.embeddings.hosted import HFInferenceEncoder

        return HFInferenceEncoder()

    raise UnknownBackend(
        f"unknown EMBEDDING_BACKEND {name!r}; expected one of: hash, e5, hosted"
    )


# Lazy attribute access so importing this package doesn't pull
# ``sentence-transformers`` (and therefore torch) into the process.
def __getattr__(name: str):
    if name == "E5Encoder":
        from api.embeddings.e5 import E5Encoder

        return E5Encoder
    if name == "HFInferenceEncoder":
        from api.embeddings.hosted import HFInferenceEncoder

        return HFInferenceEncoder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
