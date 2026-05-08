"""Tests for retrieval metrics."""

import pytest

from api.eval.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank


class TestRecallAtK:
    def test_full_hit(self):
        assert recall_at_k(["a", "b", "c"], ["a"], k=3) == 1.0

    def test_no_hit(self):
        assert recall_at_k(["x", "y", "z"], ["a"], k=3) == 0.0

    def test_partial_hit(self):
        # 1 of 2 relevant chunks present in top-2
        assert recall_at_k(["a", "x"], ["a", "b"], k=2) == 0.5

    def test_relevant_outside_topk(self):
        # 'a' is at position 5, k=3 -> miss
        assert recall_at_k(["x", "y", "z", "w", "a"], ["a"], k=3) == 0.0

    def test_relevant_at_boundary(self):
        # 'a' at position k -> hit
        assert recall_at_k(["x", "y", "a"], ["a"], k=3) == 1.0

    def test_empty_relevant_returns_zero(self):
        assert recall_at_k(["a", "b"], [], k=2) == 0.0

    def test_empty_retrieved_returns_zero(self):
        assert recall_at_k([], ["a"], k=5) == 0.0

    def test_invalid_k_raises(self):
        with pytest.raises(ValueError, match="k must be positive"):
            recall_at_k(["a"], ["a"], k=0)

    def test_duplicates_in_retrieved_dont_double_count(self):
        # Even if 'a' appears twice in retrieved, recall is still 1/1.
        assert recall_at_k(["a", "a", "x"], ["a"], k=3) == 1.0


class TestReciprocalRank:
    def test_first_position(self):
        assert reciprocal_rank(["a", "b"], ["a"]) == 1.0

    def test_third_position(self):
        assert reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)

    def test_no_relevant_in_retrieved(self):
        assert reciprocal_rank(["x", "y"], ["a"]) == 0.0

    def test_empty_retrieved(self):
        assert reciprocal_rank([], ["a"]) == 0.0

    def test_first_relevant_wins(self):
        # 'a' at position 2, 'b' at position 1 — both relevant; the first
        # relevant hit determines RR.
        assert reciprocal_rank(["b", "a"], ["a", "b"]) == 1.0


class TestMeanReciprocalRank:
    def test_single_run(self):
        assert mean_reciprocal_rank([(["a"], ["a"])]) == 1.0

    def test_two_runs(self):
        # RR = 1.0 and 0.5 -> MRR = 0.75
        runs = [(["a", "x"], ["a"]), (["x", "a"], ["a"])]
        assert mean_reciprocal_rank(runs) == 0.75

    def test_empty_runs_returns_zero(self):
        assert mean_reciprocal_rank([]) == 0.0
