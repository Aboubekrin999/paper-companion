"""Tests for EvalItem persistence and validation."""

import json

import pytest

from api.eval.items import EvalItem, FaithfulnessScore, load_items, save_items


class TestRoundTrip:
    def test_save_then_load_preserves_items(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        items = [
            EvalItem(
                id="q1",
                question="What dataset?",
                paper_id="2401.12345",
                relevant_chunk_ids=["c1", "c2"],
            ),
            EvalItem(
                id="q2",
                question="What macro-F1?",
                paper_id="2401.12345",
                relevant_chunk_ids=["c5"],
                expected_answer="0.81",
            ),
        ]
        save_items(items, path)
        loaded = load_items(path)
        assert loaded == items

    def test_save_sorts_by_id(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        items = [
            EvalItem(id="zzz", question="?", paper_id="p"),
            EvalItem(id="aaa", question="?", paper_id="p"),
            EvalItem(id="mmm", question="?", paper_id="p"),
        ]
        save_items(items, path)
        loaded = load_items(path)
        assert [it.id for it in loaded] == ["aaa", "mmm", "zzz"]


class TestParsing:
    def test_blank_lines_skipped(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text(
            '\n{"id":"a","question":"?","paper_id":"p"}\n\n'
            '{"id":"b","question":"?","paper_id":"p"}\n'
        )
        loaded = load_items(path)
        assert {it.id for it in loaded} == {"a", "b"}

    def test_missing_required_field_raises(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text('{"id":"a","question":"?"}\n')  # paper_id missing
        with pytest.raises(ValueError, match="missing required fields"):
            load_items(path)

    def test_unicode_preserved(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        item = EvalItem(
            id="fr-1",
            question="Quelle méthodologie est utilisée ?",
            paper_id="hal-1234",
        )
        save_items([item], path)
        # Verify the JSONL on disk is human-readable (no \uXXXX escapes).
        raw = path.read_text(encoding="utf-8")
        assert "Quelle méthodologie" in raw
        loaded = load_items(path)
        assert loaded[0] == item

    def test_optional_fields_default(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text('{"id":"a","question":"?","paper_id":"p"}\n')
        loaded = load_items(path)
        assert loaded[0].relevant_chunk_ids == []
        assert loaded[0].expected_answer is None


class TestFaithfulnessScore:
    def test_score_fields(self):
        s = FaithfulnessScore(item_id="q1", score=2, grader="amrins", notes="minor drift")
        assert s.score == 2
        assert s.notes == "minor drift"

    def test_score_is_frozen(self):
        s = FaithfulnessScore(item_id="q1", score=2, grader="amrins")
        with pytest.raises(AttributeError):
            s.score = 3  # type: ignore[misc]


class TestEmptyFile:
    def test_empty_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "eval.jsonl"
        path.write_text("")
        assert load_items(path) == []
