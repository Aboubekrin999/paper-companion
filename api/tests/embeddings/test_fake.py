"""Tests for the dependency-free HashEncoder fake."""

import math

import pytest

from api.embeddings import Encoder, HashEncoder


class TestProtocolConformance:
    def test_satisfies_encoder_protocol(self):
        # ``runtime_checkable`` lets isinstance check the protocol shape.
        encoder = HashEncoder(dimensions=8)
        assert isinstance(encoder, Encoder)


class TestDeterminism:
    def test_same_text_same_vector(self):
        encoder = HashEncoder(dimensions=16)
        a = encoder.encode_passages(["the quick brown fox"])[0]
        b = encoder.encode_passages(["the quick brown fox"])[0]
        assert a == b

    def test_different_text_different_vector(self):
        encoder = HashEncoder(dimensions=16)
        [a] = encoder.encode_passages(["fox"])
        [b] = encoder.encode_passages(["dog"])
        assert a != b


class TestShape:
    @pytest.mark.parametrize("dim", [4, 16, 64, 1024])
    def test_emits_requested_dimensions(self, dim):
        encoder = HashEncoder(dimensions=dim)
        [vec] = encoder.encode_passages(["hello"])
        assert len(vec) == dim
        assert encoder.dimensions == dim

    def test_invalid_dim_rejected(self):
        with pytest.raises(ValueError, match="dimensions must be positive"):
            HashEncoder(dimensions=0)


class TestNormalisation:
    def test_unit_length(self):
        encoder = HashEncoder(dimensions=32)
        [vec] = encoder.encode_passages(["any text at all"])
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_unit_length_for_unicode(self):
        encoder = HashEncoder(dimensions=32)
        [vec] = encoder.encode_queries(["méthodologie d'évaluation"])
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=1e-6)


class TestBatch:
    def test_batch_preserves_order(self):
        encoder = HashEncoder(dimensions=8)
        texts = ["a", "b", "c"]
        batch = encoder.encode_passages(texts)
        per_item = [encoder.encode_passages([t])[0] for t in texts]
        assert batch == per_item

    def test_empty_batch_returns_empty(self):
        encoder = HashEncoder(dimensions=8)
        assert encoder.encode_passages([]) == []
        assert encoder.encode_queries([]) == []
