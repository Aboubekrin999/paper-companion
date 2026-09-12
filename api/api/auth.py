"""
Supabase JWT verification.

Every request carrying data belongs to exactly one user. The web app signs
in through Supabase, receives a JWT, and forwards it as
``Authorization: Bearer <token>``. This module turns that header into a
:class:`CurrentUser`, or refuses the request.

Fails closed by design. If ``SUPABASE_JWT_SECRET`` is not configured the
protected routes return 503 rather than serving unauthenticated traffic —
there is no "auth off" switch, because a flag like that is exactly the
thing that survives to production by accident. Tests override the
``current_user`` dependency instead.

The database enforces the same boundary independently: every table in the
schema carries ``user_id`` with an RLS policy of ``auth.uid() = user_id``.
This layer is the application half of that pair, not a substitute for it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status

#: Supabase signs project JWTs with HS256 by default.
_ALGORITHMS = ["HS256"]

#: Supabase sets this audience on tokens issued to signed-in users.
_AUDIENCE = "authenticated"


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller. ``id`` matches ``auth.users.id``."""

    id: str
    email: str | None = None
    role: str | None = None


class AuthNotConfigured(RuntimeError):
    """``SUPABASE_JWT_SECRET`` is missing, so no token can be verified."""


def _secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise AuthNotConfigured(
            "SUPABASE_JWT_SECRET is not set; the API cannot verify Supabase "
            "sessions. Copy it from `supabase status` (local) or the project's "
            "API settings (hosted)."
        )
    return secret


def decode_token(token: str) -> CurrentUser:
    """Verify ``token`` and return its subject.

    Raises :class:`jwt.PyJWTError` for anything malformed, expired, wrongly
    signed, or missing a subject.
    """
    claims = jwt.decode(
        token,
        _secret(),
        algorithms=_ALGORITHMS,
        audience=_AUDIENCE,
        options={"require": ["exp", "sub"]},
    )

    subject = claims.get("sub")
    if not subject:
        raise jwt.InvalidTokenError("token has no subject")

    return CurrentUser(
        id=str(subject),
        email=claims.get("email"),
        role=claims.get("role"),
    )


async def current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """FastAPI dependency: the caller, or an HTTP error explaining why not."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="expected 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return decode_token(token.strip())
    except AuthNotConfigured as exc:
        # A server misconfiguration, not a client error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


#: Annotated alias so routes read as ``user: CurrentUserDep``.
CurrentUserDep = Depends(current_user)
