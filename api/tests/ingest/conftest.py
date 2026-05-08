"""Shared pytest fixtures for ingest tests."""

from __future__ import annotations

from io import BytesIO
from typing import Sequence

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def make_pdf(pages: Sequence[str]) -> bytes:
    """
    Build an in-memory PDF with one page per string in ``pages``.

    Each page renders its source string as a single text line at a
    fixed origin — enough for ``pypdf`` to extract recognizable text
    in tests without bringing in heavyweight typesetting.
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    for body in pages:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(72, 720, body)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture
def two_page_pdf() -> bytes:
    return make_pdf(["First page content.", "Second page content."])


@pytest.fixture
def empty_pdf() -> bytes:
    return make_pdf([])
