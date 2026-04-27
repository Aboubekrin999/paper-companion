# 4-Week Roadmap to v1

Target: live demo URL by end of May 2026. Budget: ~10 hours per week.

Each week ends in a demo-able milestone. If a week slips, the milestone shrinks before the timeline does.

---

## Week 1 — Scaffold and "hello world" deploy
*Apr 27 – May 3*

- [x] Project structure, README, decisions log, .gitignore, license
- [ ] Next.js 16 app in `web/` with magic-link auth (Supabase) protecting the home page
- [ ] FastAPI app in `api/` with `/health` and one OpenAPI-typed route
- [ ] Supabase project provisioned, pgvector enabled, `papers` and `chunks` tables migrated
- [ ] Vercel + Railway deploys live, both pointing at the Supabase project
- [ ] CI: GitHub Actions runs lint + typecheck on every PR

**Milestone.** Empty app loads at a real URL, signed in, calling a real authenticated API.

---

## Week 2 — Ingest pipeline
*May 4 – May 10*

- [ ] PDF upload UI in `web/`
- [ ] arXiv link → PDF fetcher in `api/`
- [ ] PDF parser (pypdf, fall back to unstructured for scanned PDFs)
- [ ] Recursive chunker with overlap, preserves metadata (page numbers, section headers)
- [ ] multilingual-e5-large embedding pipeline running locally and on Railway
- [ ] Persist `papers` and `chunks` to Supabase
- [ ] Library view: list papers, click into chunk inspector

**Milestone.** Drop a PDF, see chunks land in the database, browse them.

---

## Week 3 — RAG chat with citations
*May 11 – May 17*

- [ ] Vector search endpoint (top-k chunks for a query, filtered by paper)
- [ ] Cross-encoder reranker on the top results
- [ ] Streaming chat endpoint that calls Claude with retrieved context
- [ ] Chat UI with citation chips that scroll the source paragraph into view on click
- [ ] Per-paper notes: write, save, list

**Milestone.** Ask a question of a paper, get a grounded answer, click a citation, see the source highlighted.

---

## Week 4 — Eval, polish, recruiter-ready README
*May 18 – May 24*

- [ ] Hand-built eval set: 30 question-answer pairs across 5 papers
- [ ] Baseline metrics: retrieval@5, answer faithfulness (manual rubric)
- [ ] Failure-mode log → 1-page write-up in `docs/EVAL.md`
- [ ] Loom or screen recording linked from the README
- [ ] Real local-dev quickstart in the README
- [ ] Live URL pinned at the top of the README

**Milestone.** A recruiter clicks the URL, signs in, drops a PDF, asks a question, gets a cited answer. v1 done.

---

## After v1

Not commitments — just where this is likely to grow.

- Multi-paper Q&A (cross-corpus retrieval)
- Library import from Zotero / Mendeley
- Mobile companion (Project 3 — flashcards generated from papers)
- Bilingual section classifier (Project 2) integrated as a smarter chunker
