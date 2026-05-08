"""
Ingest pipeline: parse arXiv references, chunk text into RAG-ready passages.

Pure-function modules. No network, no database — those layers live above.
"""

from api.ingest.arxiv import ArxivPaper, parse_arxiv
from api.ingest.chunker import Chunk, Page, chunk_pages, chunk_text

__all__ = [
    "ArxivPaper",
    "parse_arxiv",
    "Chunk",
    "Page",
    "chunk_pages",
    "chunk_text",
]
