"""
Route-level authentication and per-user isolation.

Two properties matter here and neither is covered by the happy-path route
suites:

1. Every route that touches user data refuses an unauthenticated caller.
2. One user cannot observe another user's papers — not by listing, not by
   guessing an id, not by asking a question of one.

The second is the reason ``PaperStore`` is keyed by ``(user_id,
paper_id)``. Without it a single process serving two people leaks one
library into the other.
"""

from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.auth import current_user
from api.chat.llm import FakeLLM
from api.embeddings import HashEncoder
from api.index import app, get_llm, get_store
from api.store import PaperStore
from tests.conftest import ALICE, BOB

PAPER = "2401.12345"

#: Every route that reads or writes user data.
PROTECTED_ROUTES = [
    ("POST", "/papers", {"reference": PAPER}),
    ("GET", "/papers", None),
    ("GET", f"/papers/{PAPER}", None),
    ("POST", f"/papers/{PAPER}/chat", {"question": "What is this?"}),
]


def _make_pdf() -> bytes:
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(72, 720, "Cats are mammals.")
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def _store() -> PaperStore:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_make_pdf(), headers={"content-type": "application/pdf"}
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "test"},
        follow_redirects=True,
    )
    return PaperStore(encoder=HashEncoder(dimensions=64), http_client=client)


@pytest.fixture
def store_with_alices_paper() -> PaperStore:
    store = _store()
    store.ingest_arxiv(PAPER, user_id=ALICE.id)
    return store


@pytest.fixture
def as_bob(store_with_alices_paper: PaperStore):
    """A client authenticated as Bob, against a store holding Alice's paper."""
    app.dependency_overrides[get_store] = lambda: store_with_alices_paper
    app.dependency_overrides[get_llm] = lambda: FakeLLM("answer", chunks=1)
    app.dependency_overrides[current_user] = lambda: BOB
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated(store_with_alices_paper: PaperStore):
    """No ``current_user`` override — the real dependency runs."""
    app.dependency_overrides[get_store] = lambda: store_with_alices_paper
    app.dependency_overrides[get_llm] = lambda: FakeLLM("answer", chunks=1)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestUnauthenticated:
    @pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
    def test_routes_reject_a_caller_with_no_token(
        self, unauthenticated: TestClient, method: str, path: str, body: dict | None
    ) -> None:
        response = unauthenticated.request(method, path, json=body)
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
    def test_routes_reject_a_garbage_token(
        self,
        unauthenticated: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "a-secret-long-enough-for-hmac-sha256")
        response = unauthenticated.request(
            method, path, json=body, headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert response.status_code == 401

    def test_unconfigured_server_refuses_rather_than_serving(
        self, unauthenticated: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No secret must never mean "let everyone through"."""
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        response = unauthenticated.get(
            "/papers", headers={"Authorization": "Bearer anything"}
        )
        assert response.status_code == 503

    def test_health_stays_public(self, unauthenticated: TestClient) -> None:
        """Uptime checks must not need a token."""
        assert unauthenticated.get("/health").status_code == 200


class TestCrossUserIsolation:
    def test_another_users_paper_is_absent_from_the_listing(
        self, as_bob: TestClient
    ) -> None:
        response = as_bob.get("/papers")
        assert response.status_code == 200
        assert response.json() == []

    def test_fetching_another_users_paper_is_404_not_403(
        self, as_bob: TestClient
    ) -> None:
        """403 would confirm the id exists and leak the library by guessing."""
        assert as_bob.get(f"/papers/{PAPER}").status_code == 404

    def test_chatting_with_another_users_paper_is_404(
        self, as_bob: TestClient
    ) -> None:
        response = as_bob.post(
            f"/papers/{PAPER}/chat", json={"question": "What is this?"}
        )
        assert response.status_code == 404

    def test_same_arxiv_id_ingested_twice_stays_separate(
        self, store_with_alices_paper: PaperStore
    ) -> None:
        """Two users reading the same paper get two independent records."""
        store = store_with_alices_paper
        store.ingest_arxiv(PAPER, user_id=BOB.id)

        assert len(store.list_papers(user_id=ALICE.id)) == 1
        assert len(store.list_papers(user_id=BOB.id)) == 1
        assert store.get(PAPER, user_id=ALICE.id).id == PAPER
        assert store.get(PAPER, user_id=BOB.id).id == PAPER

    def test_a_user_with_no_papers_sees_an_empty_library(
        self, store_with_alices_paper: PaperStore
    ) -> None:
        assert store_with_alices_paper.list_papers(user_id=BOB.id) == []
