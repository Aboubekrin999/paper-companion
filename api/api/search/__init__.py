"""
Vector search — protocol + an in-memory cosine implementation.

The in-memory index is brute force and fine for v1's tens-to-low-hundreds
of papers per user. When the corpus grows or the slot-blocked Supabase
deploy comes online, ``PgVectorIndex`` slots in via the same
``VectorIndex`` protocol with no changes to the routes that consume it.
"""

from api.search.index import InMemoryVectorIndex, SearchHit
from api.search.protocol import VectorIndex

__all__ = ["InMemoryVectorIndex", "SearchHit", "VectorIndex"]
