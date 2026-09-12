"""
Tests for Supabase JWT verification.

Tokens are minted here with PyJWT and the same secret the module reads,
so these exercise real signature verification rather than a stub. The
route-level consequences (401 shapes, cross-user isolation) live in
``tests/test_auth_routes.py``.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import jwt
import pytest
from fastapi import HTTPException

from api.auth import AuthNotConfigured, CurrentUser, current_user, decode_token

SECRET = "local-development-jwt-secret-not-a-real-one"
SUBJECT = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)


def _token(
    *,
    secret: str = SECRET,
    subject: str | None = SUBJECT,
    audience: str | None = "authenticated",
    expires_in: dt.timedelta = dt.timedelta(hours=1),
    algorithm: str = "HS256",
    **extra,
) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims: dict = {"iat": now, "exp": now + expires_in, **extra}
    if subject is not None:
        claims["sub"] = subject
    if audience is not None:
        claims["aud"] = audience
    return jwt.encode(claims, secret, algorithm=algorithm)


class TestDecodeToken:
    def test_valid_token_yields_the_subject(self) -> None:
        assert decode_token(_token()).id == SUBJECT

    def test_email_and_role_are_carried_through(self) -> None:
        user = decode_token(_token(email="a@example.test", role="authenticated"))
        assert user.email == "a@example.test"
        assert user.role == "authenticated"

    def test_optional_claims_default_to_none(self) -> None:
        user = decode_token(_token())
        assert user.email is None and user.role is None

    def test_wrong_secret_is_rejected(self) -> None:
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(_token(secret="a-different-secret-long-enough-for-hmac-sha256"))

    def test_expired_token_is_rejected(self) -> None:
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(_token(expires_in=dt.timedelta(hours=-1)))

    def test_missing_expiry_is_rejected(self) -> None:
        """A token that never expires is not one we accept."""
        now = dt.datetime.now(dt.timezone.utc)
        token = jwt.encode(
            {"sub": SUBJECT, "aud": "authenticated", "iat": now}, SECRET, algorithm="HS256"
        )
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_token(token)

    def test_missing_subject_is_rejected(self) -> None:
        with pytest.raises(jwt.PyJWTError):
            decode_token(_token(subject=None))

    def test_wrong_audience_is_rejected(self) -> None:
        with pytest.raises(jwt.InvalidAudienceError):
            decode_token(_token(audience="anon"))

    def test_unsigned_token_is_rejected(self) -> None:
        """`alg: none` is the classic JWT bypass; the allowlist blocks it."""
        token = jwt.encode({"sub": SUBJECT, "aud": "authenticated"}, None, algorithm="none")
        with pytest.raises(jwt.PyJWTError):
            decode_token(token)

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(jwt.DecodeError):
            decode_token("not-a-jwt")

    def test_missing_secret_raises_auth_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(AuthNotConfigured, match="SUPABASE_JWT_SECRET"):
            decode_token(_token())


class TestCurrentUserDependency:
    """Driven with ``asyncio.run`` so the suite needs no async plugin config."""

    @staticmethod
    def _call(header: str | None) -> CurrentUser:
        return asyncio.run(current_user(authorization=header))

    def test_valid_bearer_header_authenticates(self) -> None:
        user = self._call(f"Bearer {_token()}")
        assert user.id == SUBJECT

    def test_scheme_is_case_insensitive(self) -> None:
        user = self._call(f"bearer {_token()}")
        assert user.id == SUBJECT

    def test_missing_header_is_401(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            self._call(None)
        assert excinfo.value.status_code == 401
        assert excinfo.value.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.parametrize("header", ["Basic abc123", "Bearer", "Bearer    ", "token abc"])
    def test_malformed_header_is_401(self, header: str) -> None:
        with pytest.raises(HTTPException) as excinfo:
            self._call(header)
        assert excinfo.value.status_code == 401

    def test_expired_token_says_so(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            self._call(f"Bearer {_token(expires_in=dt.timedelta(hours=-1))}")
        assert excinfo.value.status_code == 401
        assert "expired" in excinfo.value.detail

    def test_bad_signature_is_401_without_detail_leak(self) -> None:
        with pytest.raises(HTTPException) as excinfo:
            self._call(f"Bearer {_token(secret='another-secret-long-enough-for-hmac-sha256')}")
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "invalid token"

    def test_unconfigured_server_is_503_not_401(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing secret is our bug, not the caller's — and never a 200."""
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(HTTPException) as excinfo:
            self._call(f"Bearer {_token()}")
        assert excinfo.value.status_code == 503
