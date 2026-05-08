"""
Ingest pipeline: arXiv reference → fetched PDF → parsed pages → chunks.

The pure parsers (``arxiv``, ``chunker``) are testable without I/O. The
``fetcher`` adds HTTP and ``pdf`` adds binary parsing; ``pipeline`` is
the composed top-level entry point HTTP routes call.
"""

from api.ingest.arxiv import ArxivPaper, parse_arxiv
from api.ingest.chunker import Chunk, Page, chunk_pages, chunk_text
from api.ingest.fetcher import FetchError, fetch_arxiv_pdf
from api.ingest.pdf import PdfParseError, parse_pdf
from api.ingest.pipeline import IngestResult, ingest_arxiv

__all__ = [
    "ArxivPaper",
    "parse_arxiv",
    "Chunk",
    "Page",
    "chunk_pages",
    "chunk_text",
    "FetchError",
    "fetch_arxiv_pdf",
    "PdfParseError",
    "parse_pdf",
    "IngestResult",
    "ingest_arxiv",
]
