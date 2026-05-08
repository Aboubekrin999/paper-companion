"""
Eval-item schema and JSONL persistence.

Each item is a (question, ground-truth-chunks) pair authored by hand.
The harness scores retrieval against the ``relevant_chunk_ids`` set;
``expected_answer`` is reserved for the manual faithfulness rubric.

Persisted as JSONL — one item per line — so the eval set composes well
with shell tools (``wc -l``, ``head``, ``grep``) and diffs cleanly in
PRs as the set grows.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalItem:
    """A single hand-authored question with ground-truth chunk IDs."""

    id: str
    question: str
    paper_id: str
    relevant_chunk_ids: list[str] = field(default_factory=list)
    expected_answer: str | None = None


@dataclass(frozen=True)
class FaithfulnessScore:
    """A single human grading event for one eval item.

    ``score`` follows the rubric in ``docs/EVAL.md``: 0 = unsupported,
    1 = partially grounded, 2 = mostly grounded with minor drift,
    3 = fully grounded with citations matching the source.
    """

    item_id: str
    score: int
    grader: str
    notes: str = ""


def load_items(path: str | Path) -> list[EvalItem]:
    """Read a JSONL file of eval items. Blank lines are skipped."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        return [_item_from_dict(json.loads(line)) for line in fh if line.strip()]


def save_items(items: Iterable[EvalItem], path: str | Path) -> None:
    """Write items as JSONL, one item per line, sorted by ``id`` for stable diffs."""
    sorted_items = sorted(items, key=lambda it: it.id)
    p = Path(path)
    with p.open("w", encoding="utf-8") as fh:
        for item in sorted_items:
            fh.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def _item_from_dict(raw: dict) -> EvalItem:
    missing = {"id", "question", "paper_id"} - raw.keys()
    if missing:
        raise ValueError(
            f"eval item missing required fields: {sorted(missing)}; got {raw!r}"
        )
    return EvalItem(
        id=raw["id"],
        question=raw["question"],
        paper_id=raw["paper_id"],
        relevant_chunk_ids=list(raw.get("relevant_chunk_ids", [])),
        expected_answer=raw.get("expected_answer"),
    )
