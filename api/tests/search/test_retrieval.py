"""
Integration: encoder + index wired together as the retrieval substrate.

Plugs the dependency-free ``HashEncoder`` into ``InMemoryVectorIndex``
so the test suite exercises the full encode → index → query → rank
path without pulling torch.
"""

from api.embeddings import HashEncoder
from api.search import InMemoryVectorIndex


def _build_index(passages: dict[str, str], encoder: HashEncoder) -> InMemoryVectorIndex:
    index = InMemoryVectorIndex(dimensions=encoder.dimensions)
    chunk_ids = list(passages.keys())
    vectors = encoder.encode_passages(list(passages.values()))
    index.add_batch(zip(chunk_ids, vectors))
    return index


class TestEndToEnd:
    def test_query_returns_its_own_passage_first(self):
        encoder = HashEncoder(dimensions=64)
        passages = {
            "c1": "the quick brown fox jumps over the lazy dog",
            "c2": "machine learning eats software",
            "c3": "le renard rapide saute par-dessus le chien",
        }
        index = _build_index(passages, encoder)
        [query_vec] = encoder.encode_queries(
            ["machine learning eats software"]
        )
        hits = index.search(query_vec, k=3)
        assert hits[0].chunk_id == "c2"

    def test_returns_chunk_ids_in_score_order(self):
        encoder = HashEncoder(dimensions=64)
        passages = {f"c{i}": f"unique passage number {i}" for i in range(10)}
        index = _build_index(passages, encoder)
        [query_vec] = encoder.encode_queries(["unique passage number 7"])
        hits = index.search(query_vec, k=10)
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
        assert hits[0].chunk_id == "c7"

    def test_index_dimensions_must_match_encoder(self):
        encoder = HashEncoder(dimensions=32)
        index = InMemoryVectorIndex(dimensions=encoder.dimensions)
        # Adding an encoder-produced vector succeeds.
        [vec] = encoder.encode_passages(["text"])
        index.add("c1", vec)
        assert len(index) == 1
