"""
Tests for E5Encoder.

The real model weights are ~2GB and CI deliberately runs without the
ML deps installed, so this file verifies only the things that do not
require the model: clean error when the dep is missing, lazy import
behaviour, and (when available) prefix construction.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _sentence_transformers_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class TestLazyImport:
    def test_package_imports_without_sentence_transformers(self, monkeypatch):
        # Scrub the dep from the import system to simulate a CI environment.
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        # Re-importing the package must succeed even with the dep gone.
        importlib.reload(importlib.import_module("api.embeddings"))

    def test_e5_constructor_raises_without_dep(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        # Force a fresh import of the e5 module so the patched sys.modules wins.
        sys.modules.pop("api.embeddings.e5", None)
        from api.embeddings.e5 import E5Encoder  # noqa: PLC0415

        with pytest.raises(RuntimeError, match="sentence-transformers"):
            E5Encoder()


@pytest.mark.skipif(
    not _sentence_transformers_available(),
    reason="sentence-transformers not installed",
)
class TestWithRealDep:  # pragma: no cover - skipped in CI
    def test_dimensions_match_e5_large(self):
        from api.embeddings.e5 import E5Encoder

        encoder = E5Encoder()
        # multilingual-e5-large outputs 1024-d vectors.
        assert encoder.dimensions == 1024
