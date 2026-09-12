"""
Tests for ``HFInferenceEncoder``.

No network: a stub ``httpx`` transport returns canned payloads, so these
cover prefixing, both response shapes HF returns, normalisation, and the
error paths.
"""

from __future__ import annotations

import json

import httpx
import pytest

from api.embeddings.hosted import (
    EmbeddingServiceError,
    HFInferenceEncoder,
    _l2_normalise,
    _mean_pool,
)

TOKEN = "hf_test_token"


def _encoder(handler) -> tuple[HFInferenceEncoder, dict]:
    """Encoder wired to ``handler``, plus a dict capturing the request."""
    captured: dict = {}

    def _transport(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        captured["url"] = str(request.url)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(_transport))
    return HFInferenceEncoder(api_token=TOKEN, client=client), captured


def _ok(vectors):
    return lambda request: httpx.Response(200, json=vectors)


def test_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HUGGINGFACE_API_TOKEN"):
        HFInferenceEncoder()


def test_reads_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "hf_from_env")
    assert HFInferenceEncoder().dimensions == 1024


def test_passage_prefix_is_applied() -> None:
    enc, captured = _encoder(_ok([[1.0, 0.0]]))
    enc.encode_passages(["hello"])
    assert captured["body"]["inputs"] == ["passage: hello"]


def test_query_prefix_is_applied() -> None:
    enc, captured = _encoder(_ok([[1.0, 0.0]]))
    enc.encode_queries(["hello"])
    assert captured["body"]["inputs"] == ["query: hello"]


def test_sends_bearer_token_and_waits_for_model() -> None:
    enc, captured = _encoder(_ok([[1.0, 0.0]]))
    enc.encode_queries(["hello"])
    assert captured["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert captured["body"]["options"]["wait_for_model"] is True


def test_empty_input_makes_no_request() -> None:
    def _explode(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not have issued a request")

    enc, _ = _encoder(_explode)
    assert enc.encode_passages([]) == []
    assert enc.encode_queries([]) == []


def test_pooled_response_shape_is_returned_normalised() -> None:
    enc, _ = _encoder(_ok([[3.0, 4.0]]))
    assert enc.encode_passages(["x"]) == [[0.6, 0.8]]


def test_unpooled_response_shape_is_mean_pooled() -> None:
    """Some revisions return [n, tokens, dim]; mean-pool to match E5."""
    enc, _ = _encoder(_ok([[[3.0, 4.0], [3.0, 4.0]]]))
    assert enc.encode_passages(["x"]) == [[0.6, 0.8]]


def test_output_is_unit_length() -> None:
    enc, _ = _encoder(_ok([[5.0, 12.0]]))
    (vector,) = enc.encode_queries(["x"])
    assert sum(v * v for v in vector) == pytest.approx(1.0)


def test_batch_preserves_order() -> None:
    enc, _ = _encoder(_ok([[1.0, 0.0], [0.0, 1.0]]))
    assert enc.encode_passages(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_vector_count_mismatch_is_an_error() -> None:
    enc, _ = _encoder(_ok([[1.0, 0.0]]))
    with pytest.raises(EmbeddingServiceError, match="expected 2 vectors"):
        enc.encode_passages(["a", "b"])


def test_non_200_surfaces_status_and_body() -> None:
    enc, _ = _encoder(lambda r: httpx.Response(503, text="model loading"))
    with pytest.raises(EmbeddingServiceError, match="503"):
        enc.encode_queries(["x"])


def test_transport_failure_is_wrapped() -> None:
    def _fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    enc, _ = _encoder(_fail)
    with pytest.raises(EmbeddingServiceError, match="hosted embedding request failed"):
        enc.encode_queries(["x"])


def test_non_json_body_is_an_error() -> None:
    enc, _ = _encoder(lambda r: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(EmbeddingServiceError, match="non-JSON"):
        enc.encode_queries(["x"])


def test_unexpected_payload_shape_is_an_error() -> None:
    enc, _ = _encoder(lambda r: httpx.Response(200, json={"error": "nope"}))
    with pytest.raises(EmbeddingServiceError, match="unexpected embedding payload"):
        enc.encode_queries(["x"])


def test_ragged_token_vectors_are_rejected() -> None:
    with pytest.raises(EmbeddingServiceError, match="ragged"):
        _mean_pool([[1.0, 2.0], [1.0]])


def test_zero_vector_normalises_without_dividing_by_zero() -> None:
    assert _l2_normalise([0.0, 0.0]) == [0.0, 0.0]


def test_dimensions_match_the_schema_column() -> None:
    """vector(1024) in 0001_init.sql — see ADR-007."""
    enc, _ = _encoder(_ok([[1.0]]))
    assert enc.dimensions == 1024
