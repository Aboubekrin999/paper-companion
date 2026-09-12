"""
Shared fixtures for the route suites.

Every data route is authenticated, so route tests need a caller. They
override the ``current_user`` dependency rather than minting real JWTs:
token verification is covered directly in ``tests/test_auth.py``, and
routes should not re-test it.
"""

from __future__ import annotations

import pytest

from api.auth import CurrentUser

#: The default caller in route tests.
ALICE = CurrentUser(id="11111111-1111-4111-8111-111111111111", email="alice@example.test", role="authenticated")

#: A second caller, for asserting one user cannot reach another's papers.
BOB = CurrentUser(id="22222222-2222-4222-8222-222222222222", email="bob@example.test", role="authenticated")


@pytest.fixture
def alice() -> CurrentUser:
    return ALICE


@pytest.fixture
def bob() -> CurrentUser:
    return BOB
