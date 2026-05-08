"""
Eval harness: retrieval metrics + a runner that scores any retriever.

The harness is retriever-agnostic. ``run_eval`` takes a callable of
``(question: str, k: int) -> list[chunk_id]`` and the eval set, then
emits a structured report. Faithfulness scoring is captured separately
because the roadmap deliberately uses a manual rubric for v1 — see
``docs/EVAL.md``.
"""

from api.eval.items import EvalItem, FaithfulnessScore, load_items, save_items
from api.eval.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank
from api.eval.runner import EvalReport, ItemResult, RetrieveFn, run_eval

__all__ = [
    "EvalItem",
    "FaithfulnessScore",
    "load_items",
    "save_items",
    "mean_reciprocal_rank",
    "recall_at_k",
    "reciprocal_rank",
    "EvalReport",
    "ItemResult",
    "RetrieveFn",
    "run_eval",
]
