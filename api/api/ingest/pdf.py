"""
PDF parser: bytes → list[Page].

Uses ``pypdf`` for text extraction. Pages are 1-indexed to match PDF
viewer numbering and citation conventions; pages with no extractable
text are emitted with ``text=""`` rather than dropped, because section
heuristics and chunk-boundary logic still want positional awareness of
"this page exists but is mostly figures."

Scanned (image-only) PDFs come out empty here — that's a known limit and
the pivot to OCR (e.g. ``unstructured``) lives in a follow-up. The free
arXiv corpus is overwhelmingly text PDFs, so this covers the v1 path.
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from api.ingest.chunker import Page


class PdfParseError(Exception):
    """Raised when ``data`` is not a parseable PDF."""


def parse_pdf(data: bytes) -> list[Page]:
    """Parse PDF bytes into a list of ``Page`` records ordered by page number."""
    if not data:
        raise PdfParseError("empty PDF data")
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # pypdf raises a variety of types depending on cause
        raise PdfParseError(f"could not open PDF: {exc}") from exc

    pages: list[Page] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            # Don't let one malformed page break ingest — embed the page as
            # empty and let downstream see the gap rather than failing the
            # whole paper.
            text = ""
        pages.append(Page(number=index, text=text))
    return pages
