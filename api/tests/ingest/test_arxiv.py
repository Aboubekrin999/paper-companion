"""Tests for arXiv reference parsing."""

import pytest

from api.ingest.arxiv import ArxivPaper, parse_arxiv


class TestNewFormat:
    """Post-2007.04 ID scheme: YYMM.NNNNN."""

    def test_bare_id_5_digits(self):
        result = parse_arxiv("2401.12345")
        assert result == ArxivPaper(
            id="2401.12345",
            version=None,
            abs_url="https://arxiv.org/abs/2401.12345",
            pdf_url="https://arxiv.org/pdf/2401.12345.pdf",
        )

    def test_bare_id_4_digits(self):
        # Pre-2015 papers used 4 digits in the suffix.
        result = parse_arxiv("1411.4555")
        assert result is not None
        assert result.id == "1411.4555"
        assert result.version is None

    def test_id_with_version(self):
        result = parse_arxiv("2401.12345v2")
        assert result is not None
        assert result.id == "2401.12345"
        assert result.version == 2

    def test_id_with_double_digit_version(self):
        result = parse_arxiv("2401.12345v10")
        assert result is not None
        assert result.version == 10

    def test_abs_url(self):
        result = parse_arxiv("https://arxiv.org/abs/2401.12345")
        assert result is not None
        assert result.id == "2401.12345"

    def test_abs_url_with_version(self):
        result = parse_arxiv("https://arxiv.org/abs/2401.12345v3")
        assert result is not None
        assert result.id == "2401.12345"
        assert result.version == 3

    def test_pdf_url(self):
        result = parse_arxiv("https://arxiv.org/pdf/2401.12345")
        assert result is not None
        assert result.id == "2401.12345"

    def test_pdf_url_with_extension(self):
        result = parse_arxiv("https://arxiv.org/pdf/2401.12345.pdf")
        assert result is not None
        assert result.id == "2401.12345"

    def test_pdf_url_with_version_and_extension(self):
        result = parse_arxiv("https://arxiv.org/pdf/2401.12345v2.pdf")
        assert result is not None
        assert result.id == "2401.12345"
        assert result.version == 2

    def test_http_scheme_accepted(self):
        result = parse_arxiv("http://arxiv.org/abs/2401.12345")
        assert result is not None

    def test_arxiv_prefix(self):
        result = parse_arxiv("arXiv:2401.12345")
        assert result is not None
        assert result.id == "2401.12345"

    def test_canonical_urls_use_https(self):
        result = parse_arxiv("2401.12345")
        assert result is not None
        assert result.abs_url.startswith("https://")
        assert result.pdf_url.startswith("https://")

    def test_pdf_url_always_has_pdf_suffix(self):
        result = parse_arxiv("2401.12345")
        assert result is not None
        assert result.pdf_url.endswith(".pdf")


class TestOldFormat:
    """Pre-2007.04 ID scheme: archive[.SC]/NNNNNNN."""

    def test_simple_archive(self):
        result = parse_arxiv("cs/0301001")
        assert result is not None
        assert result.id == "cs/0301001"
        assert result.version is None

    def test_archive_with_subcategory(self):
        result = parse_arxiv("math.GT/0309136")
        assert result is not None
        assert result.id == "math.GT/0309136"

    def test_dashed_archive(self):
        result = parse_arxiv("cond-mat/0102536")
        assert result is not None
        assert result.id == "cond-mat/0102536"

    def test_old_with_version(self):
        result = parse_arxiv("cs/0301001v1")
        assert result is not None
        assert result.id == "cs/0301001"
        assert result.version == 1

    def test_old_abs_url(self):
        result = parse_arxiv("https://arxiv.org/abs/cs/0301001")
        assert result is not None
        assert result.id == "cs/0301001"


class TestRejection:
    """Inputs that should not parse as arXiv references."""

    @pytest.mark.parametrize(
        "garbage",
        [
            "",
            "not an arxiv id",
            "https://example.com/paper.pdf",
            "doi:10.1234/foo",
            "12345",
            "cs/12345",  # too few digits for old format
            "9999.1",    # too few digits in suffix
        ],
    )
    def test_returns_none(self, garbage):
        assert parse_arxiv(garbage) is None


class TestPermissive:
    """Embedded IDs in copy-pasted text should be extracted."""

    def test_id_inside_sentence(self):
        result = parse_arxiv("See arXiv:2401.12345 for details.")
        assert result is not None
        assert result.id == "2401.12345"

    def test_id_with_surrounding_whitespace(self):
        result = parse_arxiv("  2401.12345  ")
        assert result is not None
        assert result.id == "2401.12345"
