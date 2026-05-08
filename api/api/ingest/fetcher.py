"""
arXiv PDF fetcher.

Thin wrapper around ``httpx`` that pulls a paper's PDF bytes from the
canonical URL produced by ``parse_arxiv``. Designed so callers can pass
their own ``httpx.Client`` for connection pooling, retries, or test
mocking via ``MockTransport``.

Live HTTP is deliberately *not* exercised in unit tests — tests inject a
mocked transport and verify the request shape and error handling. A
single live integration test belongs in a separate suite (not yet
authored) gated on a ``RUN_LIVE`` env flag.
"""

from __future__ import annotations

import httpx

from api.ingest.arxiv import ArxivPaper

DEFAULT_TIMEOUT_SECONDS = 30.0
USER_AGENT = (
    "paper-companion/0.0.1 "
    "(+https://github.com/Aboubekrin999/paper-companion)"
)


class FetchError(Exception):
    """Raised when an HTTP fetch fails for a non-transient, non-retriable reason."""


def fetch_arxiv_pdf(
    paper: ArxivPaper,
    *,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """
    Download ``paper.pdf_url`` and return the raw PDF bytes.

    A caller-supplied ``client`` is reused as-is (caller owns its
    lifecycle). When omitted, a fresh client is created and closed
    inside this call.

    Raises:
        FetchError: on non-2xx status, missing/wrong Content-Type, or
            empty body. Network-level errors propagate as ``httpx``
            exceptions for the caller to retry.
    """
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
    try:
        response = client.get(paper.pdf_url)
        if response.status_code != 200:
            raise FetchError(
                f"arXiv returned {response.status_code} for {paper.pdf_url}"
            )
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower():
            raise FetchError(
                f"expected PDF content-type, got {content_type!r} "
                f"for {paper.pdf_url}"
            )
        if not response.content:
            raise FetchError(f"empty response body for {paper.pdf_url}")
        return response.content
    finally:
        if owns_client:
            client.close()
