"""
``HFInferenceEncoder`` — ``multilingual-e5-large`` over the Hugging Face
Inference API.

Same weights as :class:`api.embeddings.e5.E5Encoder`, same 1024-dimension
output, same ``query:`` / ``passage:`` prefixes — so an index built with
one is valid for the other. See ADR-007 for why deployed environments
call the model instead of holding it.

Only ``httpx`` is required, which the API already depends on, so this
module imports cleanly in a Vercel function with no ML stack present.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_MODEL = "intfloat/multilingual-e5-large"
_E5_DIMENSIONS = 1024
_DEFAULT_TIMEOUT = 30.0


class EmbeddingServiceError(RuntimeError):
    """Hosted inference was unreachable or returned an unusable body."""


class HFInferenceEncoder:
    """Encode via HF Inference. Requires ``HUGGINGFACE_API_TOKEN``."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        api_token: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        token = api_token or os.environ.get("HUGGINGFACE_API_TOKEN")
        if not token:
            raise RuntimeError(
                "HFInferenceEncoder requires a Hugging Face token. Set "
                "HUGGINGFACE_API_TOKEN, or use E5Encoder locally."
            )
        self._model = model_name
        self._token = token
        self._timeout = timeout
        self._client = client
        self._url = (
            f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
        )

    @property
    def dimensions(self) -> int:
        return _E5_DIMENSIONS

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {t}" for t in texts])

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"query: {t}" for t in texts])

    def _encode(self, prefixed: list[str]) -> list[list[float]]:
        if not prefixed:
            return []

        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"inputs": prefixed, "options": {"wait_for_model": True}},
            )
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError(
                f"hosted embedding request failed: {exc}"
            ) from exc
        finally:
            if self._client is None:
                client.close()

        if response.status_code != 200:
            raise EmbeddingServiceError(
                f"hosted embedding returned {response.status_code}: "
                f"{response.text[:200]}"
            )

        vectors = self._parse(response)
        if len(vectors) != len(prefixed):
            raise EmbeddingServiceError(
                f"expected {len(prefixed)} vectors, got {len(vectors)}"
            )
        return [_l2_normalise(v) for v in vectors]

    def _parse(self, response: httpx.Response) -> list[list[float]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingServiceError("hosted embedding returned non-JSON") from exc

        if not isinstance(payload, list) or not payload:
            raise EmbeddingServiceError(
                f"unexpected embedding payload shape: {type(payload).__name__}"
            )

        # feature-extraction returns [n, dim]; some revisions return the
        # unpooled [n, tokens, dim], which we mean-pool to match E5's
        # sentence-transformers behaviour.
        first = payload[0]
        if isinstance(first, list) and first and isinstance(first[0], list):
            return [_mean_pool(seq) for seq in payload]
        return payload


def _mean_pool(token_vectors: list[list[float]]) -> list[float]:
    if not token_vectors:
        raise EmbeddingServiceError("cannot mean-pool an empty token sequence")
    width = len(token_vectors[0])
    sums = [0.0] * width
    for vector in token_vectors:
        if len(vector) != width:
            raise EmbeddingServiceError("ragged token vectors in embedding payload")
        for i, value in enumerate(vector):
            sums[i] += value
    count = len(token_vectors)
    return [s / count for s in sums]


def _l2_normalise(vector: list[float]) -> list[float]:
    """Match E5Encoder's normalised output so cosine == dot product."""
    norm = sum(v * v for v in vector) ** 0.5
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]
