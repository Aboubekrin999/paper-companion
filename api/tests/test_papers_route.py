"""Route tests for /papers (ingest, list, get).

Uses dependency_overrides to inject a PaperStore wired to a MockTransport
httpx.Client serving a generated PDF, so the ingest path runs end-to-end
without touching the network.
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

from api.embeddings import HashEncoder
from api.index import app, get_store
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


def _store_serving(pdf_bytes: bytes) -> PaperStore:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=pdf_bytes, headers={"content-type": "application/pdf"}
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )
    return PaperStore(encoder=HashEncoder(dimensions=64), http_client=client)


@pytest.fixture
def client_with_store():
    store = _store_serving(_make_pdf(["First page.", "Second page."]))
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield TestClient(app), store
    finally:
        app.dependency_overrides.clear()


class TestCreatePaper:
    def test_returns_201_with_paper_record(self, client_with_store):
        client, _ = client_with_store
        response = client.post("/papers", json={"reference": "2401.12345"})
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "2401.12345"
        assert body["page_count"] == 2
        assert body["chunk_count"] >= 1

    def test_invalid_reference_returns_400(self, client_with_store):
        client, _ = client_with_store
        response = client.post("/papers", json={"reference": "not-an-arxiv-id"})
        assert response.status_code == 400
        assert "not a recognizable arXiv reference" in response.json()["detail"]

    def test_missing_field_returns_422(self, client_with_store):
        client, _ = client_with_store
        response = client.post("/papers", json={})
        assert response.status_code == 422

    def test_re_ingest_is_idempotent(self, client_with_store):
        client, store = client_with_store
        client.post("/papers", json={"reference": "2401.12345"})
        response = client.post("/papers", json={"reference": "2401.12345"})
        assert response.status_code == 201
        assert len(store.list_papers()) == 1

    def test_fetch_failure_returns_502(self):
        def handler(request):
            return httpx.Response(500)

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "test"},
            follow_redirects=True,
        )
        store = PaperStore(encoder=HashEncoder(dimensions=64), http_client=client)
        app.dependency_overrides[get_store] = lambda: store
        try:
            response = TestClient(app).post("/papers", json={"reference": "2401.12345"})
            assert response.status_code == 502
        finally:
            app.dependency_overrides.clear()


class TestListAndGet:
    def test_list_returns_empty_when_no_papers(self):
        store = PaperStore(encoder=HashEncoder(dimensions=64))
        app.dependency_overrides[get_store] = lambda: store
        try:
            response = TestClient(app).get("/papers")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_list_returns_ingested_papers(self, client_with_store):
        client, _ = client_with_store
        client.post("/papers", json={"reference": "2401.12345"})
        response = client.get("/papers")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == "2401.12345"

    def test_get_returns_paper(self, client_with_store):
        client, _ = client_with_store
        client.post("/papers", json={"reference": "2401.12345"})
        response = client.get("/papers/2401.12345")
        assert response.status_code == 200
        assert response.json()["id"] == "2401.12345"

    def test_get_unknown_paper_returns_404(self, client_with_store):
        client, _ = client_with_store
        response = client.get("/papers/9999.99999")
        assert response.status_code == 404
