"""Tests for the PDF parser."""

import pytest

from api.ingest.chunker import Page
from api.ingest.pdf import PdfParseError, parse_pdf


class TestSuccessful:
    def test_returns_one_page_per_pdf_page(self, two_page_pdf):
        pages = parse_pdf(two_page_pdf)
        assert len(pages) == 2

    def test_pages_are_one_indexed(self, two_page_pdf):
        pages = parse_pdf(two_page_pdf)
        assert [p.number for p in pages] == [1, 2]

    def test_returns_page_dataclass(self, two_page_pdf):
        pages = parse_pdf(two_page_pdf)
        assert all(isinstance(p, Page) for p in pages)

    def test_extracts_text(self, two_page_pdf):
        pages = parse_pdf(two_page_pdf)
        assert "First page" in pages[0].text
        assert "Second page" in pages[1].text

    def test_text_is_per_page(self, two_page_pdf):
        # Page 1's text shouldn't bleed into page 2.
        pages = parse_pdf(two_page_pdf)
        assert "Second page" not in pages[0].text
        assert "First page" not in pages[1].text


class TestEmptyAndDegenerate:
    def test_empty_bytes_raises(self):
        with pytest.raises(PdfParseError, match="empty"):
            parse_pdf(b"")

    def test_garbage_bytes_raises(self):
        with pytest.raises(PdfParseError, match="could not open"):
            parse_pdf(b"this is not a pdf, not even close")

    def test_pdf_with_no_pages_returns_empty_list(self, empty_pdf):
        pages = parse_pdf(empty_pdf)
        assert pages == []
