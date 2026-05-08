# Evaluation Methodology

Goal: produce a defendable retrieval baseline before the eval set grows past hand-craftable size, then track the headline metrics over every retrieval-touching change.

## What we measure

| Metric | What it answers | Notes |
| --- | --- | --- |
| **Recall@1** | "Did the top result contain a ground-truth chunk?" | Strict — useful as a ceiling on chat quality. |
| **Recall@5** | "Did any top-5 result contain a ground-truth chunk?" | Headline metric. Typical RAG operating point. |
| **Recall@10** | "How forgiving does retrieval have to be before relevant material shows up?" | Diagnostic — a wide gap from R@5 → R@10 means the reranker matters. |
| **MRR** | "Where does the first relevant chunk land on average?" | Single scalar; useful for quick regression checks. |
| **Faithfulness (manual)** | "Is the generated answer actually supported by the cited chunks?" | Rubric grade 0–3, see below. Manual for v1 because automated faithfulness scorers themselves drift. |

Recall is reported binary per relevant chunk: a single chunk found in the top-k is a hit, regardless of position. Many eval items have only one relevant chunk, which makes precision noisy at small k.

## Eval set

Hand-authored items, one JSON object per line, in `eval/<set>.jsonl`. Schema:

```json
{
  "id": "ex-1",
  "question": "What dataset was used to fine-tune the model?",
  "paper_id": "2401.12345",
  "relevant_chunk_ids": ["c-2401.12345-12", "c-2401.12345-13"],
  "expected_answer": "optional, used by the manual rubric only"
}
```

Target for v1: **30 items across 5 papers**, balanced EN/FR. Each item is reviewed by the author before commit. `relevant_chunk_ids` are derived from the chunker's deterministic IDs, so the eval set is reproducible from the source PDF + chunker config — no hidden state.

## Faithfulness rubric

Manually graded against the chat answer, captured as a `FaithfulnessScore` record:

| Score | Meaning |
| --- | --- |
| **0** | Unsupported. Claims appear with no chunk that says them. |
| **1** | Partially grounded. Some claims supported, others fabricated or drifted. |
| **2** | Mostly grounded. Minor paraphrase drift but no fabrications. |
| **3** | Fully grounded. Every load-bearing claim traces to a cited chunk. |

The grader records their initials and free-text `notes` so error analysis can later cluster failure modes.

## How to run

```python
from api.eval import load_items, run_eval

items = load_items("eval/v1.jsonl")
report = run_eval(items, retrieve_fn, ks=(1, 5, 10))
print(report.recall_at_k, report.mean_reciprocal_rank)
```

`retrieve_fn` is any `(question: str, k: int) -> list[chunk_id]` callable. The harness calls it once per item with `k = max(ks)` and computes every requested cutoff from the same ranked list — no double work.

## What's intentionally out of scope for v1

- **Automated faithfulness.** LLM-judge faithfulness has its own drift; the v1 set is small enough to grade by hand, which is more honest.
- **Latency benchmarks.** Tracked separately when retrieval lands.
- **Cross-paper retrieval.** v1 retrieves within a single paper; multi-paper eval comes after the chunk index spans the library.
