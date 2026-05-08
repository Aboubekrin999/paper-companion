"""
Encoder protocol + implementations.

Two implementations live here:

- ``HashEncoder`` — deterministic, dependency-free, used in tests so
  the rest of the system can be exercised without pulling torch.
- ``E5Encoder`` — production ``intfloat/multilingual-e5-large`` via
  ``sentence-transformers``. The dependency is imported lazily so this
  module is importable in CI without the ML stack installed.

The ``Encoder`` protocol distinguishes ``encode_queries`` from
``encode_passages`` because E5 (and most modern asymmetric encoders)
prefix queries and passages differently before encoding. Implementations
that don't care about the distinction can return the same vectors from
both methods.
"""

from api.embeddings.encoder import Encoder
from api.embeddings.fake import HashEncoder

__all__ = ["Encoder", "HashEncoder", "E5Encoder"]


# Lazy attribute access so importing this package doesn't pull
# ``sentence-transformers`` (and therefore torch) into the process.
def __getattr__(name: str):
    if name == "E5Encoder":
        from api.embeddings.e5 import E5Encoder

        return E5Encoder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
