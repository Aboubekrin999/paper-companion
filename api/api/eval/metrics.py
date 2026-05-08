"""
Pure retrieval metrics.

All metrics work on a ranked list of retrieved chunk IDs and a set of
ground-truth relevant IDs — no dependency on the retriever, the eval
set, or any I/O. Easy to reason about and easy to test.

We expose ``recall_at_k`` (binary "any relevant in top k") because v1
eval items typically have very few ground-truth chunks per question;
classical precision@k is noisy at that scale.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def recall_at_k(
    retrieved: Sequence[str],
    relevant: Iterable[str],
    k: int,
) -> float:
    """
    Fraction of relevant chunks appearing in the top-k retrieved.

    With one relevant chunk this collapses to "hit@k" (0 or 1). With
    multiple it's the standard recall over the top-k cutoff.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    top_k = set(retrieved[:k])
    hits = relevant_set & top_k
    return len(hits) / len(relevant_set)


def reciprocal_rank(
    retrieved: Sequence[str],
    relevant: Iterable[str],
) -> float:
    """
    1 / (1-based rank of the first relevant chunk), or 0 if none retrieved.
    """
    relevant_set = set(relevant)
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant_set:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    runs: Iterable[tuple[Sequence[str], Iterable[str]]],
) -> float:
    """
    MRR across many (retrieved, relevant) pairs.

    An empty collection of runs returns 0.0 — caller should usually
    guard against that case for a more meaningful report.
    """
    rrs = [reciprocal_rank(r, rel) for r, rel in runs]
    if not rrs:
        return 0.0
    return sum(rrs) / len(rrs)
