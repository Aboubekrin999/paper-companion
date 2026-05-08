"""Tests for the in-memory vector index."""

import math

import pytest

from api.search import InMemoryVectorIndex, SearchHit, VectorIndex


class TestProtocol:
    def test_satisfies_vector_index_protocol(self):
        idx = InMemoryVectorIndex(dimensions=4)
        assert isinstance(idx, VectorIndex)


class TestEmpty:
    def test_empty_index_returns_empty(self):
        idx = InMemoryVectorIndex(dimensions=4)
        assert idx.search([1.0, 0.0, 0.0, 0.0], k=5) == []

    def test_len_zero_when_empty(self):
        assert len(InMemoryVectorIndex(dimensions=4)) == 0

    def test_invalid_dim_rejected(self):
        with pytest.raises(ValueError, match="dimensions must be positive"):
            InMemoryVectorIndex(dimensions=0)


class TestInsertion:
    def test_add_single(self):
        idx = InMemoryVectorIndex(dimensions=3)
        idx.add("c1", [1.0, 0.0, 0.0])
        assert len(idx) == 1

    def test_add_batch(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add_batch([("c1", [1.0, 0.0]), ("c2", [0.0, 1.0])])
        assert len(idx) == 2

    def test_dim_mismatch_on_add_raises(self):
        idx = InMemoryVectorIndex(dimensions=4)
        with pytest.raises(ValueError, match="does not match index dim"):
            idx.add("c1", [1.0, 0.0])


class TestSearch:
    def test_returns_search_hit_records(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        hits = idx.search([1.0, 0.0], k=1)
        assert len(hits) == 1
        assert isinstance(hits[0], SearchHit)
        assert hits[0].chunk_id == "c1"

    def test_identical_vector_scores_one(self):
        idx = InMemoryVectorIndex(dimensions=3)
        idx.add("c1", [1.0, 0.0, 0.0])
        hits = idx.search([1.0, 0.0, 0.0], k=1)
        assert hits[0].score == pytest.approx(1.0)

    def test_orthogonal_vector_scores_zero(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        hits = idx.search([0.0, 1.0], k=1)
        assert hits[0].score == pytest.approx(0.0, abs=1e-9)

    def test_opposite_vector_scores_negative(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        hits = idx.search([-1.0, 0.0], k=1)
        assert hits[0].score == pytest.approx(-1.0)

    def test_results_sorted_by_score_descending(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("close", [1.0, 0.0])
        idx.add("orth", [0.0, 1.0])
        idx.add("near", [0.99, math.sqrt(1 - 0.99**2)])
        hits = idx.search([1.0, 0.0], k=3)
        ids = [h.chunk_id for h in hits]
        assert ids == ["close", "near", "orth"]
        assert hits[0].score >= hits[1].score >= hits[2].score

    def test_top_k_caps_result_length(self):
        idx = InMemoryVectorIndex(dimensions=2)
        for i in range(20):
            idx.add(f"c{i}", [1.0, float(i) / 100])
        hits = idx.search([1.0, 0.0], k=5)
        assert len(hits) == 5

    def test_k_larger_than_corpus_returns_all(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        idx.add("c2", [0.0, 1.0])
        hits = idx.search([1.0, 0.0], k=99)
        assert len(hits) == 2

    def test_invalid_k_rejected(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        with pytest.raises(ValueError, match="k must be positive"):
            idx.search([1.0, 0.0], k=0)

    def test_query_dim_mismatch_raises(self):
        idx = InMemoryVectorIndex(dimensions=4)
        idx.add("c1", [1.0, 0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="query dim"):
            idx.search([1.0, 0.0], k=1)


class TestZeroVector:
    def test_zero_query_scores_all_zero(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [1.0, 0.0])
        hits = idx.search([0.0, 0.0], k=1)
        assert hits[0].score == 0.0

    def test_zero_indexed_vector_scores_zero(self):
        idx = InMemoryVectorIndex(dimensions=2)
        idx.add("c1", [0.0, 0.0])
        hits = idx.search([1.0, 0.0], k=1)
        assert hits[0].score == 0.0
