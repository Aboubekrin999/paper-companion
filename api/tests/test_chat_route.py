"""Route tests for POST /papers/{id}/chat.

Streams JSONL events. We assert the framing (citations event, then
token events, then a done event) and the contents of each.
"""

import json
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.chat.llm import FakeLLM
from api.embeddings import HashEncoder
from api.index import app, get_llm, get_store
from api.store import PaperStore


def _make_pdf(pages: list[str]) -> bytes:
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    for body in pages:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(72, 720, body)
        pdf.showPage()
    pdf.save()
    return buf.getvalue()


def _store_with_paper(reference: str = "2401.12345") -> PaperStore:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_make_pdf(["Cats are mammals.", "Dogs are loyal."]),
            headers={"content-type": "application/pdf"},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )
    store = PaperStore(encoder=HashEncoder(dimensions=64), http_client=client)
    store.ingest_arxiv(reference)
    return store


@pytest.fixture
def client_with_paper():
    store = _store_with_paper()
    fake_llm = FakeLLM("Cats are mammals based on the context.", chunks=3)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: fake_llm
    try:
        yield TestClient(app), store, fake_llm
    finally:
        app.dependency_overrides.clear()


def _parse_jsonl(body: bytes) -> list[dict]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class TestStreamFraming:
    def test_first_event_is_citations(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "What are cats?", "k": 2},
        )
        assert response.status_code == 200
        events = _parse_jsonl(response.content)
        assert events[0]["type"] == "citations"

    def test_last_event_is_done(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "What are cats?"},
        )
        events = _parse_jsonl(response.content)
        assert events[-1] == {"type": "done"}

    def test_token_events_in_between(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "What are cats?"},
        )
        events = _parse_jsonl(response.content)
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) >= 1
        # Concatenated tokens reconstitute the canned answer.
        assert "".join(e["text"] for e in token_events) == "Cats are mammals based on the context."


class TestCitationsContent:
    def test_citations_have_chunk_id_and_score(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "Cats are mammals.", "k": 1},
        )
        citations = _parse_jsonl(response.content)[0]["citations"]
        assert len(citations) == 1
        assert "chunk_id" in citations[0]
        assert "score" in citations[0]
        assert "snippet" in citations[0]

    def test_k_caps_citation_count(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "anything", "k": 1},
        )
        citations = _parse_jsonl(response.content)[0]["citations"]
        assert len(citations) == 1


class TestErrors:
    def test_unknown_paper_returns_404(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/9999.99999/chat",
            json={"question": "hi"},
        )
        assert response.status_code == 404

    def test_empty_question_rejected_by_pydantic(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": ""},
        )
        assert response.status_code == 422

    def test_invalid_k_rejected(self, client_with_paper):
        client, _, _ = client_with_paper
        response = client.post(
            "/papers/2401.12345/chat",
            json={"question": "ok", "k": 0},
        )
        assert response.status_code == 422
