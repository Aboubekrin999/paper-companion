"""Tests for the prompt template helpers."""

from api.chat.prompts import (
    SYSTEM_PROMPT,
    build_user_message,
    format_chunk_block,
)


class TestSystemPrompt:
    def test_constrains_answer_to_context(self):
        assert "context" in SYSTEM_PROMPT.lower()

    def test_demands_citations(self):
        assert "[" in SYSTEM_PROMPT and "]" in SYSTEM_PROMPT
        assert "chunk_id" in SYSTEM_PROMPT or "cite" in SYSTEM_PROMPT.lower()

    def test_forbids_outside_knowledge(self):
        # Subtle changes here move faithfulness scores; pin the directive.
        lowered = SYSTEM_PROMPT.lower()
        assert "outside knowledge" in lowered or "not guess" in lowered


class TestFormatChunkBlock:
    def test_includes_chunk_id_and_page(self):
        block = format_chunk_block("c-1", 7, "Some content.")
        assert "c-1" in block
        assert "page 7" in block
        assert "Some content." in block

    def test_handles_unknown_page(self):
        block = format_chunk_block("c-1", None, "Some content.")
        assert "page n/a" in block


class TestBuildUserMessage:
    def test_question_appears_after_context(self):
        msg = build_user_message("What is X?", ["[c1 | page 1]\nbody"])
        # Question must come at the end so the model reads context first.
        assert msg.endswith("Question: What is X?")

    def test_blocks_separated(self):
        msg = build_user_message("?", ["block A", "block B"])
        assert "block A" in msg and "block B" in msg
        assert "block A\n\nblock B" in msg

    def test_no_context_marker(self):
        # When retrieval returns nothing, the model should know the
        # context is empty rather than inventing answers.
        msg = build_user_message("?", [])
        assert "no relevant context" in msg.lower()
