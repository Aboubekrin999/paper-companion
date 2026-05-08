"""End-to-end tests for the chat orchestrator using HashEncoder + InMemoryVectorIndex + FakeLLM."""

import pytest

from api.chat import (
    ChatContext,
    Citation,
    FakeLLM,
    answer,
)
from api.embeddings import HashEncoder
from api.ingest.chunker import Chunk
from api.search import InMemoryVectorIndex


def _build_context(passages: dict[str, tuple[int, str]], llm_response: str = "stub answer"):
    """Build a ChatContext for tests.

    ``passages`` maps chunk_id -> (page_number, content).
    """
    encoder = HashEncoder(dimensions=64)
    index = InMemoryVectorIndex(dimensions=encoder.dimensions)
    chunks_by_id: dict[str, Chunk] = {}

    for i, (cid, (page, content)) in enumerate(passages.items()):
        chunks_by_id[cid] = Chunk(
            content=content,
            chunk_index=i,
            char_start=0,
            char_end=len(content),
            page_number=page,
            token_count=len(content) // 4,
        )

    chunk_ids = list(passages.keys())
    contents = [chunks_by_id[cid].content for cid in chunk_ids]
    vectors = encoder.encode_passages(contents)
    index.add_batch(zip(chunk_ids, vectors))

    return ChatContext(
        encoder=encoder,
        index=index,
        chunks_by_id=chunks_by_id,
        llm=FakeLLM(llm_response),
    )


class TestRetrievalIntegration:
    def test_returns_citations_for_top_k(self):
        ctx = _build_context(
            {
                "c1": (1, "Cats are mammals that meow."),
                "c2": (2, "Dogs are loyal companions."),
                "c3": (3, "Pythons are reptiles."),
            }
        )
        result = answer("Cats are mammals that meow.", ctx, k=2)
        assert len(result.citations) == 2
        assert all(isinstance(c, Citation) for c in result.citations)
        # Best citation matches the query semantically (here, exactly).
        assert result.citations[0].chunk_id == "c1"

    def test_citations_carry_page_numbers(self):
        ctx = _build_context({"c1": (7, "content")})
        result = answer("content", ctx, k=1)
        assert result.citations[0].page_number == 7

    def test_citations_carry_score(self):
        ctx = _build_context({"c1": (1, "exact match")})
        result = answer("exact match", ctx, k=1)
        # HashEncoder is deterministic — same text encoded as both passage and
        # query collapses to a self-cosine of 1.0.
        assert result.citations[0].score == pytest.approx(1.0)


class TestSnippets:
    def test_snippet_truncates_long_content(self):
        long_text = "x " * 500  # 1000 chars
        ctx = _build_context({"c1": (1, long_text)})
        result = answer("query", ctx, k=1, snippet_chars=100)
        # 100 chars + ellipsis
        assert len(result.citations[0].snippet) <= 102
        assert result.citations[0].snippet.endswith("…")

    def test_short_content_not_truncated(self):
        ctx = _build_context({"c1": (1, "short content.")})
        result = answer("q", ctx, k=1)
        assert result.citations[0].snippet == "short content."


class TestLLMHandoff:
    def test_system_prompt_passed_to_llm(self):
        ctx = _build_context({"c1": (1, "content")})
        result = answer("query", ctx, k=1)
        # Drain the stream so FakeLLM records the call.
        list(result.answer_stream)
        assert ctx.llm.last_call is not None
        assert "research assistant" in ctx.llm.last_call["system"].lower()

    def test_context_block_includes_chunk_id_and_page(self):
        ctx = _build_context({"c-paper-1": (12, "some passage text")})
        result = answer("query", ctx, k=1)
        list(result.answer_stream)
        ctx_block = ctx.llm.last_call["context"]
        assert "c-paper-1" in ctx_block
        assert "page 12" in ctx_block
        assert "some passage text" in ctx_block

    def test_question_passed_through(self):
        ctx = _build_context({"c1": (1, "content")})
        result = answer("What is the answer?", ctx, k=1)
        list(result.answer_stream)
        assert ctx.llm.last_call["question"] == "What is the answer?"

    def test_streamed_answer_yields_canned_response(self):
        ctx = _build_context({"c1": (1, "content")}, llm_response="hello world")
        result = answer("query", ctx, k=1)
        assert "".join(result.answer_stream) == "hello world"


class TestEmptyContext:
    def test_search_with_empty_index_still_returns_result(self):
        encoder = HashEncoder(dimensions=64)
        index = InMemoryVectorIndex(dimensions=encoder.dimensions)
        ctx = ChatContext(
            encoder=encoder,
            index=index,
            chunks_by_id={},
            llm=FakeLLM("nothing to ground"),
        )
        result = answer("anything", ctx, k=5)
        assert result.citations == []
        list(result.answer_stream)  # drain
        # The orchestrator told the model the context is empty so it can refuse rather than guess.
        assert "no relevant context" in ctx.llm.last_call["context"].lower()


class TestValidation:
    def test_empty_question_rejected(self):
        ctx = _build_context({"c1": (1, "content")})
        with pytest.raises(ValueError, match="question must not be empty"):
            answer("", ctx)

    def test_whitespace_only_question_rejected(self):
        ctx = _build_context({"c1": (1, "content")})
        with pytest.raises(ValueError, match="question must not be empty"):
            answer("   \n", ctx)

    def test_invalid_k_rejected(self):
        ctx = _build_context({"c1": (1, "content")})
        with pytest.raises(ValueError, match="k must be positive"):
            answer("question", ctx, k=0)

    def test_missing_chunk_in_lookup_raises_keyerror(self):
        # Index references a chunk that the chunk store doesn't know about.
        encoder = HashEncoder(dimensions=64)
        index = InMemoryVectorIndex(dimensions=encoder.dimensions)
        index.add("orphan", encoder.encode_passages(["x"])[0])
        ctx = ChatContext(
            encoder=encoder,
            index=index,
            chunks_by_id={},  # orphan not present
            llm=FakeLLM("ok"),
        )
        with pytest.raises(KeyError):
            answer("query", ctx, k=1)
