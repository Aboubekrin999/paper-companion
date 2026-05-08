"""End-to-end tests for ``ingest_arxiv``.

Exercises the full reference → fetch → parse → chunk path with a mocked
HTTP transport so the test stays hermetic.
"""

import httpx
import pytest

from api.ingest.fetcher import USER_AGENT
from api.ingest.pipeline import IngestResult, ingest_arxiv


def _make_client_serving(pdf_bytes: bytes) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=pdf_bytes, headers={"content-type": "application/pdf"}
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


class TestEndToEnd:
    def test_returns_ingest_result(self, two_page_pdf):
        with _make_client_serving(two_page_pdf) as client:
            result = ingest_arxiv("2401.12345", client=client)
        assert isinstance(result, IngestResult)

    def test_paper_id_extracted(self, two_page_pdf):
        with _make_client_serving(two_page_pdf) as client:
            result = ingest_arxiv("https://arxiv.org/abs/2401.12345v2", client=client)
        assert result.paper.id == "2401.12345"
        assert result.paper.version == 2

    def test_page_count_matches_pdf(self, two_page_pdf):
        with _make_client_serving(two_page_pdf) as client:
            result = ingest_arxiv("2401.12345", client=client)
        assert result.page_count == 2

    def test_chunks_emitted(self, two_page_pdf):
        with _make_client_serving(two_page_pdf) as client:
            result = ingest_arxiv("2401.12345", client=client)
        assert len(result.chunks) >= 1
        assert all(c.content for c in result.chunks)

    def test_chunks_carry_page_numbers(self, two_page_pdf):
        with _make_client_serving(two_page_pdf) as client:
            result = ingest_arxiv(
                "2401.12345", chunk_size=200, overlap=20, client=client
            )
        assert all(c.page_number in (1, 2) for c in result.chunks)


class TestRejection:
    def test_invalid_reference_raises_before_fetching(self, two_page_pdf):
        # No client touched — fetch must not be reached.
        with pytest.raises(ValueError, match="not a recognizable arXiv reference"):
            ingest_arxiv("not an arxiv id")
