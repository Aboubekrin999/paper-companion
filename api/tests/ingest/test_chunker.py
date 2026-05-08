"""Tests for the recursive text chunker."""

import pytest

from api.ingest.chunker import Chunk, Page, chunk_pages, chunk_text


class TestSizing:
    """Chunks must respect the configured size."""

    def test_short_text_returns_single_chunk(self):
        chunks = chunk_text("Hello world.", chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world."
        assert chunks[0].chunk_index == 0
        assert chunks[0].char_start == 0
        assert chunks[0].char_end == len("Hello world.")

    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("", chunk_size=100, overlap=10) == []

    def test_each_chunk_within_chunk_size(self):
        text = "abc " * 500  # 2000 chars
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1
        assert all(len(c.content) <= 200 for c in chunks)

    def test_chunks_are_indexed_in_order(self):
        text = "x " * 1000
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i


class TestBoundaries:
    """The splitter prefers semantic boundaries over hard cuts."""

    def test_prefers_paragraph_break(self):
        a = "x" * 80
        b = "y" * 80
        chunks = chunk_text(f"{a}\n\n{b}", chunk_size=100, overlap=10)
        # First chunk should end at the paragraph break, not mid-word.
        assert chunks[0].content.rstrip().endswith("x")

    def test_prefers_sentence_break_when_no_paragraph(self):
        sentence_a = "Cats are mammals. " * 4   # ~72 chars
        sentence_b = "Dogs are too. " * 4        # ~56 chars
        text = (sentence_a + sentence_b).strip()
        chunks = chunk_text(text, chunk_size=80, overlap=8)
        # No paragraph breaks present; sentence boundary should be used.
        assert all(
            c.content.rstrip().endswith(("mammals.", "too.", "are mammals.", "are too."))
            or len(c.content) >= 60
            for c in chunks[:-1]
        )

    def test_falls_back_to_hard_cut_when_no_separator(self):
        text = "x" * 500  # no separators at all
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        assert all(len(c.content) <= 100 for c in chunks)


class TestOverlap:
    """Consecutive chunks share content for retrieval continuity."""

    def test_consecutive_chunks_overlap(self):
        text = ("word " * 400).strip()  # 1999 chars
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 2
        # char ranges overlap (or at least touch) between consecutive chunks
        for prev, curr in zip(chunks, chunks[1:]):
            assert curr.char_start < prev.char_end
            assert curr.char_start >= prev.char_start  # forward progress


class TestProgress:
    """The chunker must always make forward progress."""

    def test_terminates_on_pathological_input(self):
        text = "a" * 10_000
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) > 0
        assert chunks[-1].char_end == len(text)

    def test_rejects_overlap_ge_chunk_size(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("hello", chunk_size=10, overlap=10)

    def test_rejects_negative_overlap(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("hello", chunk_size=10, overlap=-1)

    def test_rejects_zero_chunk_size(self):
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("hello", chunk_size=0, overlap=0)


class TestCoverage:
    """Concatenating chunks must reproduce the original text (modulo overlap)."""

    def test_chunks_cover_full_text(self):
        text = "The quick brown fox. " * 100
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        # First chunk starts at 0, last chunk ends at len(text)
        assert chunks[0].char_start == 0
        assert chunks[-1].char_end == len(text)

    def test_chunk_content_matches_offsets(self):
        text = "The quick brown fox. " * 100
        chunks = chunk_text(text, chunk_size=150, overlap=30)
        for c in chunks:
            assert c.content == text[c.char_start : c.char_end]


class TestPages:
    """Page-aware chunking attaches page numbers and respects page joins."""

    def test_empty_pages_returns_no_chunks(self):
        assert chunk_pages([], chunk_size=100, overlap=10) == []

    def test_single_page_short(self):
        pages = [Page(number=1, text="One short page.")]
        chunks = chunk_pages(pages, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0].page_number == 1
        assert chunks[0].content == "One short page."

    def test_chunks_carry_starting_page(self):
        page1 = Page(number=1, text="A" * 80)
        page2 = Page(number=2, text="B" * 80)
        page3 = Page(number=3, text="C" * 80)
        chunks = chunk_pages([page1, page2, page3], chunk_size=100, overlap=20)
        page_numbers_seen = {c.page_number for c in chunks}
        # All three pages are reachable as starting pages of some chunk
        assert page_numbers_seen.issuperset({1, 2, 3})

    def test_chunks_can_span_pages(self):
        # A single chunk may contain content from multiple pages — that's fine,
        # the chunk reports the page where it starts.
        page1 = Page(number=1, text="hello")
        page2 = Page(number=2, text="world")
        chunks = chunk_pages([page1, page2], chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert "hello" in chunks[0].content
        assert "world" in chunks[0].content

    def test_page_numbers_preserved_when_non_sequential(self):
        # The classifier uses real page numbers from the PDF, not array indices.
        pages = [Page(number=7, text="Seven."), Page(number=8, text="Eight.")]
        chunks = chunk_pages(pages, chunk_size=100, overlap=10)
        assert chunks[0].page_number == 7


class TestTokenEstimate:
    """Token counts are rough but monotonic."""

    def test_empty_chunk_zero_tokens(self):
        # We never emit empty chunks, but the helper should still be sane.
        chunks = chunk_text(" ", chunk_size=100, overlap=10)
        if chunks:
            assert chunks[0].token_count >= 0

    def test_longer_content_more_tokens(self):
        short = chunk_text("abcd " * 10, chunk_size=200, overlap=20)
        long = chunk_text("abcd " * 100, chunk_size=200, overlap=20)
        # The longest chunk in the long doc has more tokens than the short doc's chunk
        assert max(c.token_count for c in long) > short[0].token_count


class TestChunkType:
    """Sanity checks on the public dataclass."""

    def test_chunk_is_frozen(self):
        chunks = chunk_text("hello world", chunk_size=100, overlap=10)
        with pytest.raises(Exception):
            chunks[0].content = "mutated"  # type: ignore[misc]

    def test_chunk_fields(self):
        chunks = chunk_text("hello world", chunk_size=100, overlap=10)
        c = chunks[0]
        assert isinstance(c, Chunk)
        assert isinstance(c.content, str)
        assert isinstance(c.chunk_index, int)
        assert isinstance(c.char_start, int)
        assert isinstance(c.char_end, int)
        assert isinstance(c.token_count, int)
