"""Tests for the arXiv PDF fetcher.

All tests use ``httpx.MockTransport`` — no real network. A live
integration test against arxiv.org belongs in a separate suite gated
on an env flag (not yet authored).
"""

import httpx
import pytest

from api.ingest.arxiv import parse_arxiv
from api.ingest.fetcher import USER_AGENT, FetchError, fetch_arxiv_pdf


def _client_with(handler) -> httpx.Client:
    """Build a Client whose transport is a MockTransport for ``handler``."""
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


PAPER = parse_arxiv("2401.12345")
assert PAPER is not None  # narrows for the type checker


class TestSuccess:
    def test_returns_response_body(self):
        body = b"%PDF-1.7\n...mock pdf bytes..."

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "application/pdf"})

        with _client_with(handler) as client:
            result = fetch_arxiv_pdf(PAPER, client=client)
        assert result == body

    def test_requests_canonical_pdf_url(self):
        seen_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_urls.append(str(request.url))
            return httpx.Response(
                200, content=b"%PDF-1.7\nx", headers={"content-type": "application/pdf"}
            )

        with _client_with(handler) as client:
            fetch_arxiv_pdf(PAPER, client=client)
        assert seen_urls == ["https://arxiv.org/pdf/2401.12345.pdf"]

    def test_sends_user_agent(self):
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["ua"] = request.headers.get("user-agent", "")
            return httpx.Response(
                200, content=b"%PDF-1.7\nx", headers={"content-type": "application/pdf"}
            )

        with _client_with(handler) as client:
            fetch_arxiv_pdf(PAPER, client=client)
        assert "paper-companion" in captured["ua"]


class TestFailure:
    def test_404_raises_fetch_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with _client_with(handler) as client, pytest.raises(FetchError, match="404"):
            fetch_arxiv_pdf(PAPER, client=client)

    def test_500_raises_fetch_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        with _client_with(handler) as client, pytest.raises(FetchError, match="500"):
            fetch_arxiv_pdf(PAPER, client=client)

    def test_wrong_content_type_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"<html></html>", headers={"content-type": "text/html"}
            )

        with _client_with(handler) as client, pytest.raises(FetchError, match="content-type"):
            fetch_arxiv_pdf(PAPER, client=client)

    def test_empty_body_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"", headers={"content-type": "application/pdf"})

        with _client_with(handler) as client, pytest.raises(FetchError, match="empty"):
            fetch_arxiv_pdf(PAPER, client=client)


class TestClientLifecycle:
    def test_caller_supplied_client_is_not_closed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"%PDF-1.7\nx", headers={"content-type": "application/pdf"}
            )

        client = _client_with(handler)
        try:
            fetch_arxiv_pdf(PAPER, client=client)
            # Reuse — second call must still work, proving the client wasn't closed
            fetch_arxiv_pdf(PAPER, client=client)
        finally:
            client.close()
