"""
Eval runner.

Orchestrates a retrieval pass over a set of ``EvalItem`` records and
emits a structured ``EvalReport``. The retriever is injected — callers
plug in whichever vector search / reranker / hybrid stack they want to
score, and the harness stays unaware of how chunks are produced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Callable

from api.eval.items import EvalItem
from api.eval.metrics import recall_at_k, reciprocal_rank

RetrieveFn = Callable[[str, int], Sequence[str]]
"""(question, k) -> ranked list of chunk IDs."""


@dataclass(frozen=True)
class ItemResult:
    """Per-item scoring detail. Useful for failure-mode triage."""

    item_id: str
    retrieved: list[str]
    recall_by_k: dict[int, float]
    reciprocal_rank: float


@dataclass(frozen=True)
class EvalReport:
    """Aggregated retrieval metrics over an eval set."""

    n_items: int
    recall_at_k: dict[int, float]
    mean_reciprocal_rank: float
    per_item: list[ItemResult] = field(default_factory=list)


def run_eval(
    items: Sequence[EvalItem],
    retrieve: RetrieveFn,
    *,
    ks: Sequence[int] = (1, 5, 10),
) -> EvalReport:
    """
    Run a retrieval eval over ``items`` using ``retrieve``.

    For each item, retrieves ``max(ks)`` chunks once and computes recall
    at every requested k from that single ranked list — no need to call
    the retriever multiple times per item. Reciprocal rank uses the same
    list (so it implicitly caps at ``max(ks)``; widen ``ks`` if you want
    to see deeper reciprocal ranks).
    """
    if not ks:
        raise ValueError("at least one k value is required")
    ks = tuple(sorted(set(ks)))
    top_k = max(ks)

    per_item: list[ItemResult] = []
    for item in items:
        retrieved = list(retrieve(item.question, top_k))
        recall_by_k = {k: recall_at_k(retrieved, item.relevant_chunk_ids, k) for k in ks}
        rr = reciprocal_rank(retrieved, item.relevant_chunk_ids)
        per_item.append(
            ItemResult(
                item_id=item.id,
                retrieved=retrieved,
                recall_by_k=recall_by_k,
                reciprocal_rank=rr,
            )
        )

    n = len(per_item)
    if n == 0:
        return EvalReport(
            n_items=0,
            recall_at_k={k: 0.0 for k in ks},
            mean_reciprocal_rank=0.0,
            per_item=[],
        )

    aggregated_recall = {
        k: sum(r.recall_by_k[k] for r in per_item) / n for k in ks
    }
    mrr = sum(r.reciprocal_rank for r in per_item) / n
    return EvalReport(
        n_items=n,
        recall_at_k=aggregated_recall,
        mean_reciprocal_rank=mrr,
        per_item=per_item,
    )
