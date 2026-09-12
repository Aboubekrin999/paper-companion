"""
Tests for ``build_encoder`` — the EMBEDDING_BACKEND seam from ADR-007.

The e5 and hosted branches are asserted by dispatch, not by construction:
building them for real would pull torch or require a token, neither of
which belongs in this suite.

Symbols are resolved through the module (``embeddings.build_encoder``)
rather than bound at import time. ``test_e5.py`` reloads this package to
prove the lazy import works, which rebinds every class it defines — a
module-level ``from api.embeddings import UnknownBackend`` would leave
this file holding a stale class that no longer matches what is raised.
"""

from __future__ import annotations

import pytest

import api.embeddings as embeddings


def test_defaults_to_hash_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_BACKEND", raising=False)
    assert isinstance(embeddings.build_encoder(), embeddings.HashEncoder)


def test_default_backend_constant_matches_actual_default() -> None:
    encoder = embeddings.build_encoder(embeddings.DEFAULT_BACKEND)
    assert isinstance(encoder, embeddings.HashEncoder)


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    assert isinstance(embeddings.build_encoder(), embeddings.HashEncoder)


def test_explicit_argument_wins_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_BACKEND", "e5")
    assert isinstance(embeddings.build_encoder("hash"), embeddings.HashEncoder)


@pytest.mark.parametrize("value", ["HASH", " hash ", "Hash"])
def test_name_is_case_and_space_insensitive(value: str) -> None:
    assert isinstance(embeddings.build_encoder(value), embeddings.HashEncoder)


def test_unknown_backend_names_the_valid_options() -> None:
    with pytest.raises(embeddings.UnknownBackend) as excinfo:
        embeddings.build_encoder("word2vec")
    message = str(excinfo.value)
    assert "word2vec" in message
    for valid in ("hash", "e5", "hosted"):
        assert valid in message


def test_unknown_backend_is_a_value_error() -> None:
    """Callers that only catch ValueError still behave sensibly."""
    with pytest.raises(ValueError):
        embeddings.build_encoder("word2vec")


def test_hosted_backend_without_token_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HUGGINGFACE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HUGGINGFACE_API_TOKEN"):
        embeddings.build_encoder("hosted")


def test_hash_encoder_is_not_shared_between_calls() -> None:
    """No process-wide singleton here — the route layer owns caching."""
    assert embeddings.build_encoder("hash") is not embeddings.build_encoder("hash")
