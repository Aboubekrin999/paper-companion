# Architecture Decisions

Lightweight ADRs (Architecture Decision Records). Each entry: context → decision → consequences. Read this before changing infrastructure.

---

<a id="adr-001"></a>

## ADR-001 — Split Next.js (web) and FastAPI (api) instead of Next.js-only

**Date:** 2026-04-27
**Status:** Accepted

**Context.** A single Next.js app could serve as both UI and backend via API routes. That is simpler to deploy.

**Decision.** Split into `web/` (Next.js) and `api/` (Python FastAPI).

**Why.**
- The RAG ecosystem (sentence-transformers, LlamaIndex, custom eval harnesses) is Python-first. Re-implementing chunking and eval logic in Node would slow down the companion fine-tuning project, [bilingual-section-classifier](https://github.com/Aboubekrin999/bilingual-section-classifier).
- The future mobile client needs the same backend. A clean OpenAPI surface is reusable; Next.js API routes are not.
- Keeps the door open for swapping the LLM and embedding layer without touching the UI.

**Consequences.** Two deploy targets. Slightly more glue code: CORS, auth token forwarding. Worth it.

> Superseded in part by [ADR-006](#adr-006): the split stands, but both targets are now Vercel projects and Railway is out of the stack.

---

<a id="adr-002"></a>

## ADR-002 — Supabase Postgres with pgvector instead of a dedicated vector DB

**Date:** 2026-04-27
**Status:** Accepted

**Context.** Pinecone, Weaviate, and Qdrant are purpose-built for vector search and would scale further.

**Decision.** Use Supabase Postgres with the `pgvector` extension.

**Why.**
- v1 has tens of papers, not millions of vectors. pgvector is ample.
- One service for auth + relational data + vector search beats juggling three.
- Free tier covers this entire project. No surprise bills.
- If scale ever demands a dedicated index, the embedding rows in Postgres make migration trivial.

**Consequences.** Bound to Postgres scale ceilings. Acceptable trade for v1.

---

<a id="adr-003"></a>

## ADR-003 — Anthropic Claude for chat, multilingual-e5 for embeddings

**Date:** 2026-04-27
**Status:** Accepted

**Context.** Many viable LLM and embedding providers.

**Decision.**
- Chat: Claude Sonnet by default; Claude Haiku for cheap pre-processing (chunk summaries, classification).
- Embeddings: `intfloat/multilingual-e5-large`, self-hosted in the FastAPI service.

**Why.**
- Claude's long-context reading and citation honesty fit a research tool.
- multilingual-e5-large is open, free at inference, and competitive on MTEB for both English and French — a hard requirement for HAL papers and bilingual coursework.
- Reserves OpenAI's `text-embedding-3` as a fallback if multilingual-e5 underperforms on real eval (the [classifier project](https://github.com/Aboubekrin999/bilingual-section-classifier) will produce that comparison).

**Consequences.** Embedding cost moves to RAM and CPU on the API host instead of per-call billing. Acceptable for v1 traffic.

---

<a id="adr-004"></a>

## ADR-004 — Monorepo with `web/` and `api/` siblings, no workspace tooling yet

**Date:** 2026-04-27
**Status:** Accepted

**Context.** Could split into two repos. Could also adopt Turborepo or Nx now.

**Decision.** Single repo. `web/` and `api/` as siblings. No workspace tooling until shared TypeScript types between `web/` and the future mobile client justify it.

**Why.** One PR can land a feature that touches both layers; history is easier to read; adding Turborepo later is cheap. Adding it now is premature optimization.

**Consequences.** CI needs to detect changed paths and skip unaffected pipelines. The current workflow runs both pipelines on every PR; path filtering is a later optimisation.

---

<a id="adr-005"></a>

## ADR-005 — No auto-summarization at ingest

**Date:** 2026-04-27
**Status:** Accepted

**Context.** Tempting to auto-summarize each paper at upload time so the user gets value immediately.

**Decision.** Don't. Summarization happens on demand through chat ("summarize this paper").

**Why.** Auto-summarization burns tokens on papers the user never reads, and a one-shot summary often misses what the user actually cares about. On-demand retrieval surfaces the user's *specific* question and grounds the answer in the relevant chunks.

**Consequences.** First chat per paper has slightly higher latency (no pre-baked summary). Acceptable.

---

<a id="adr-006"></a>

## ADR-006 — Vercel Python Functions instead of Railway for the FastAPI backend

**Date:** 2026-04-27
**Status:** Accepted (supersedes the Railway choice in [ADR-001](#adr-001))

**Context.** ADR-001 chose to split `web/` and `api/` into separate deploy targets — Vercel for Next.js, Railway for FastAPI. Vercel has since matured Python Functions (managed serverless Python runtime) into a real option for Python web frameworks.

**Decision.** Deploy the FastAPI backend as Vercel Python Functions, in a separate Vercel project that builds from `api/`. Keep the architectural split (two Vercel projects), drop Railway from the stack.

**Why.**
- One platform for both `web/` and `api/` — single dashboard, single billing, single environment-variable surface.
- Vercel Python Functions support FastAPI directly; the entry point is `api/index.py`, which the runtime detects automatically.
- Vercel's free tier covers v1's expected traffic.
- Cold-start latency is acceptable for an interactive research tool (single-digit seconds at worst, <500ms warm).
- Reduces failure surface: one auth flow to manage with the platform, one CLI, one set of environment variables.

**Consequences.**
- Long-running tasks (e.g., heavy embedding jobs) hit Vercel's max function duration. Mitigation: defer batch work to a separate worker if/when needed (probably not in v1; we embed at ingest time per chunk, which is fast).
- Inner directory layout becomes `api/api/index.py` (the outer `api/` is the project folder, the inner `api/` is Vercel's required functions directory). Ugly but documented.


---

<a id="adr-007"></a>

## ADR-007 — Same encoder protocol, different backends per environment

**Date:** 2026-09-12
**Status:** Accepted

**Context.** [ADR-003](#adr-003) chose `intfloat/multilingual-e5-large`, "self-hosted in the FastAPI service." [ADR-006](#adr-006) then moved that service to Vercel Python Functions. Those two decisions are not compatible, and nothing in the repo acknowledged it.

The model is ~2.2 GB of weights; `torch` alone is several hundred MB more. A Vercel Serverless Function has a 250 MB unzipped bundle limit. `multilingual-e5-small` is smaller but still clears that limit once torch is counted. No variant of "ship the weights inside the function" works.

Three ways out:

| Option | Cost | Retrieval quality | Fits ADR-006 |
|---|---|---|---|
| **A.** Separate always-on service (Fly / Railway) holding the model | A second platform, a paid instance to stay warm | Full | No — reintroduces the platform split ADR-006 removed |
| **B.** Smaller model inside the function | Free | Lower, and still over the size limit in practice | No |
| **C.** Hosted inference for the same model, called over HTTP | Free tier, then per-call | Full — identical weights | Yes |

**Decision.** Option C, expressed as a third implementation of the existing `Encoder` protocol rather than a change to any caller.

- **Local development and tests** use `E5Encoder` — the real model, running on the developer's machine, no network, no cost.
- **Deployed environments** use `HFInferenceEncoder`, which calls the Hugging Face Inference API for the same `multilingual-e5-large` weights.
- **CI** uses `HashEncoder`, as it already does.

`EMBEDDING_BACKEND` selects between them at startup.

**Why this works.** All three produce vectors for the same protocol, and A and C produce the *same 1024-dimension vectors from the same weights* — so `vector(1024)` in [the initial migration](../supabase/migrations/20260427000000_init.sql) is correct for both, and an index built locally is valid in production. No caller — store, orchestrator, eval harness, routes — learns which backend is in use.

**Consequences.**

- A network round-trip per ingest batch and per query in deployed environments. Ingest is already network-bound (fetching the PDF), so the marginal cost lands mostly on query latency.
- A hosted-inference outage degrades retrieval to an error rather than a slow path. Acceptable for v1; a local fallback is possible later because the protocol allows it.
- Vector dimensions are now a property of the *model*, not the backend. Any future switch to a different model is a migration of the `vector(N)` column, and the encoder's `dimensions` must be checked against the schema at startup rather than assumed.
- `HashEncoder`'s 64 dimensions never match the schema. It is a test double only, and the store must refuse to persist vectors whose width disagrees with the column.
