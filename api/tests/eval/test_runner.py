"""Tests for the eval runner."""

import pytest

from api.eval.items import EvalItem
from api.eval.runner import EvalReport, run_eval


def _stub_retriever(answers: dict[str, list[str]]):
    """Build a RetrieveFn that returns canned chunk IDs per question."""

    def retrieve(question: str, k: int) -> list[str]:
        return answers.get(question, [])[:k]

    return retrieve


class TestEmpty:
    def test_no_items_returns_zeroed_report(self):
        report = run_eval([], _stub_retriever({}), ks=(1, 5))
        assert isinstance(report, EvalReport)
        assert report.n_items == 0
        assert report.recall_at_k == {1: 0.0, 5: 0.0}
        assert report.mean_reciprocal_rank == 0.0
        assert report.per_item == []

    def test_empty_ks_raises(self):
        with pytest.raises(ValueError, match="at least one k"):
            run_eval([], _stub_retriever({}), ks=())


class TestPerItemResults:
    def test_records_each_items_retrieval(self):
        items = [
            EvalItem(id="q1", question="What?", paper_id="p", relevant_chunk_ids=["c1"]),
            EvalItem(id="q2", question="Why?", paper_id="p", relevant_chunk_ids=["c5"]),
        ]
        retriever = _stub_retriever(
            {"What?": ["c1", "c2", "c3"], "Why?": ["c9", "c5"]}
        )
        report = run_eval(items, retriever, ks=(1, 3))
        assert report.n_items == 2

        by_id = {r.item_id: r for r in report.per_item}
        assert by_id["q1"].retrieved == ["c1", "c2", "c3"]
        assert by_id["q1"].recall_by_k == {1: 1.0, 3: 1.0}
        assert by_id["q1"].reciprocal_rank == 1.0

        assert by_id["q2"].retrieved == ["c9", "c5", ]
        assert by_id["q2"].recall_by_k == {1: 0.0, 3: 1.0}
        assert by_id["q2"].reciprocal_rank == pytest.approx(0.5)


class TestAggregation:
    def test_recall_at_k_averaged_across_items(self):
        items = [
            EvalItem(id="q1", question="A", paper_id="p", relevant_chunk_ids=["x"]),
            EvalItem(id="q2", question="B", paper_id="p", relevant_chunk_ids=["x"]),
        ]
        # q1 hits at rank 1, q2 misses entirely
        retriever = _stub_retriever({"A": ["x"], "B": ["a", "b"]})
        report = run_eval(items, retriever, ks=(1,))
        assert report.recall_at_k == {1: 0.5}

    def test_mrr_averaged(self):
        items = [
            EvalItem(id="q1", question="A", paper_id="p", relevant_chunk_ids=["x"]),
            EvalItem(id="q2", question="B", paper_id="p", relevant_chunk_ids=["x"]),
        ]
        # RR = 1.0 and 0.0 -> MRR = 0.5
        retriever = _stub_retriever({"A": ["x"], "B": ["y"]})
        report = run_eval(items, retriever, ks=(1, 5))
        assert report.mean_reciprocal_rank == 0.5


class TestKHandling:
    def test_ks_deduplicated_and_sorted(self):
        items = [
            EvalItem(id="q1", question="A", paper_id="p", relevant_chunk_ids=["x"])
        ]
        retriever = _stub_retriever({"A": ["x"]})
        report = run_eval(items, retriever, ks=(5, 1, 5, 3))
        assert sorted(report.recall_at_k.keys()) == [1, 3, 5]

    def test_retrieves_max_k_only_once(self):
        # Track how many times the retriever is invoked per item — must be once.
        calls: list[int] = []

        def retriever(question: str, k: int) -> list[str]:
            calls.append(k)
            return ["x"] * k

        items = [
            EvalItem(id="q1", question="A", paper_id="p", relevant_chunk_ids=["x"])
        ]
        run_eval(items, retriever, ks=(1, 3, 10))
        # One call total, requested at max k = 10
        assert calls == [10]
