"""
FastAPI entry point for paper-companion.

Deployed as a single Vercel Python Function. The route layer is thin —
all business logic lives in ``api.store``, ``api.chat``,
``api.embeddings``, ``api.search`` — so the HTTP shape is the easiest
piece to evolve as the front-end requirements settle.
"""

import json
import os
from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.chat.llm import LLM, ClaudeLLM, FakeLLM
from api.chat.orchestrator import Citation
from api.embeddings import HashEncoder
from api.embeddings.encoder import Encoder
from api.ingest.fetcher import FetchError
from api.store import PaperNotFound, PaperRecord, PaperStore

app = FastAPI(
    title="Paper Companion API",
    description="Backend for paper-companion: PDF ingest, embeddings, RAG chat.",
    version="0.0.1",
    docs_url="/docs",
    redoc_url=None,
)

_allowed = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency providers
#
# Tests override these via ``app.dependency_overrides`` rather than mutating
# globals, so suites stay hermetic. A single process-wide ``PaperStore`` is
# the v1 model — moving to per-user state lands when auth lands.
# ---------------------------------------------------------------------------


def get_encoder() -> Encoder:
    """Default to ``HashEncoder`` until the ML stack is on the deploy box."""
    return HashEncoder(dimensions=64)


_STORE: PaperStore | None = None


def get_store(
    encoder: Annotated[Encoder, Depends(get_encoder)],
) -> PaperStore:
    global _STORE
    if _STORE is None:
        _STORE = PaperStore(encoder=encoder)
    return _STORE


def get_llm() -> LLM:
    """Use Claude when ``ANTHROPIC_API_KEY`` is set, else a stub.

    The stub keeps the route demoable without an API key; the response
    text says so explicitly so a curl session can't be misread.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeLLM()
    return FakeLLM(
        "ANTHROPIC_API_KEY is not configured on this server, so the chat layer "
        "is in stub mode. Set the env var to enable grounded answers from Claude."
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class CreatePaperRequest(BaseModel):
    reference: str = Field(
        ...,
        description="arXiv URL, raw ID, or 'arxiv:'-prefixed string.",
    )


class PaperResponse(BaseModel):
    id: str
    arxiv_id: str
    version: int | None
    abs_url: str
    pdf_url: str
    page_count: int
    chunk_count: int

    @classmethod
    def from_record(cls, record: PaperRecord) -> "PaperResponse":
        return cls(**asdict(record))


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(5, ge=1, le=50)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe. Used by uptime checks and the web app's boot ping."""
    return HealthResponse(status="ok", version=app.version)


@app.post(
    "/papers",
    response_model=PaperResponse,
    status_code=201,
    tags=["papers"],
)
async def create_paper(
    body: CreatePaperRequest,
    store: Annotated[PaperStore, Depends(get_store)],
) -> PaperResponse:
    """Ingest an arXiv paper: fetch, parse, chunk, embed, index. Idempotent."""
    try:
        record = store.ingest_arxiv(body.reference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PaperResponse.from_record(record)


@app.get("/papers", response_model=list[PaperResponse], tags=["papers"])
async def list_papers(
    store: Annotated[PaperStore, Depends(get_store)],
) -> list[PaperResponse]:
    return [PaperResponse.from_record(r) for r in store.list_papers()]


@app.get("/papers/{paper_id}", response_model=PaperResponse, tags=["papers"])
async def get_paper(
    paper_id: str,
    store: Annotated[PaperStore, Depends(get_store)],
) -> PaperResponse:
    try:
        record = store.get(paper_id)
    except PaperNotFound as exc:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not found") from exc
    return PaperResponse.from_record(record)


@app.post("/papers/{paper_id}/chat", tags=["chat"])
async def chat(
    paper_id: str,
    body: ChatRequest,
    store: Annotated[PaperStore, Depends(get_store)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> StreamingResponse:
    """Stream a grounded chat answer as JSONL events.

    Wire format (one JSON object per line):

    - ``{"type":"citations","citations":[...]}`` — emitted first, once
    - ``{"type":"token","text":"..."}`` — zero or more
    - ``{"type":"done"}`` — emitted last
    """
    try:
        result = store.chat(paper_id, body.question, k=body.k, llm=llm)
    except PaperNotFound as exc:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        _jsonl_events(result.citations, result.answer_stream),
        media_type="application/x-ndjson",
    )


def _jsonl_events(
    citations: list[Citation],
    tokens: Iterator[str],
) -> Iterator[bytes]:
    """Encode citations + token stream as newline-delimited JSON."""
    citations_payload = {
        "type": "citations",
        "citations": [asdict(c) for c in citations],
    }
    yield (json.dumps(citations_payload) + "\n").encode("utf-8")
    for piece in tokens:
        yield (json.dumps({"type": "token", "text": piece}) + "\n").encode("utf-8")
    yield (json.dumps({"type": "done"}) + "\n").encode("utf-8")
