"""Tests for the LLM Protocol and FakeLLM.

ClaudeLLM is exercised as a smoke import + a constructor test that
swaps in a stub anthropic client. The real network path lives in a
manual integration suite (not yet authored) that requires
``ANTHROPIC_API_KEY``.
"""

import pytest

from api.chat.llm import LLM, ClaudeLLM, FakeLLM


class TestProtocolConformance:
    def test_fake_llm_is_an_llm(self):
        assert isinstance(FakeLLM(), LLM)

    def test_claude_llm_class_imports(self):
        # ClaudeLLM importing means anthropic SDK loaded cleanly.
        assert callable(ClaudeLLM)


class TestFakeLLMStream:
    def test_yields_canned_response(self):
        llm = FakeLLM("the answer is 42", chunks=2)
        chunks = list(llm.stream(system="sys", context="ctx", question="q"))
        assert "".join(chunks) == "the answer is 42"

    def test_yields_in_multiple_pieces(self):
        llm = FakeLLM("x" * 80, chunks=4)
        chunks = list(llm.stream(system="sys", context="ctx", question="q"))
        assert len(chunks) >= 2

    def test_records_inputs_for_assertion(self):
        llm = FakeLLM("ok")
        list(llm.stream(system="SYS", context="CTX", question="Q"))
        assert llm.last_call == {"system": "SYS", "context": "CTX", "question": "Q"}

    def test_empty_response_yields_nothing(self):
        llm = FakeLLM("")
        assert list(llm.stream(system="s", context="c", question="q")) == []

    def test_invalid_chunks_rejected(self):
        with pytest.raises(ValueError, match="chunks must be positive"):
            FakeLLM("ok", chunks=0)


class TestClaudeLLMRequestShape:
    """Build the request the orchestrator hands to Claude using a stub client."""

    def test_marks_context_as_cached_question_as_uncached(self):
        captured = {}

        class StubMessages:
            def stream(self_inner, **kwargs):  # noqa: N805
                captured.update(kwargs)
                # Return a context manager whose ``text_stream`` is empty —
                # we only care about what the wrapper *sent*.
                class _CM:
                    def __enter__(self_):
                        return self_

                    def __exit__(self_, *exc):
                        return False

                    text_stream = iter(())

                return _CM()

        class StubClient:
            messages = StubMessages()

        llm = ClaudeLLM(model="claude-sonnet-4-6", client=StubClient())
        list(llm.stream(system="SYS", context="CTX_BLOCK", question="What?"))

        assert captured["model"] == "claude-sonnet-4-6"
        assert captured["system"] == "SYS"
        # Single user message with two blocks
        msgs = captured["messages"]
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        blocks = msgs[0]["content"]
        assert len(blocks) == 2
        # First block: the cached context.
        assert blocks[0]["text"] == "CTX_BLOCK"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        # Second block: the question, NOT cached.
        assert blocks[1]["text"] == "Question: What?"
        assert "cache_control" not in blocks[1]
