"""
Unit tests for auth.py — get_optional_user_id FastAPI dependency.

Note: SUPABASE_JWT_SECRET is read at module import time in auth.py, so we
patch `auth.SUPABASE_JWT_SECRET` directly rather than the environment variable.
"""
import time
from unittest.mock import MagicMock

import jwt as pyjwt
import pytest

import auth
from auth import get_optional_user_id

TEST_SECRET = "test-secret-minimum-32-chars-long!!"
TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


def make_token(overrides=None, secret=TEST_SECRET):
    """Mint a HS256 JWT with the given payload overrides."""
    payload = {"sub": TEST_USER_ID, "aud": "authenticated", **(overrides or {})}
    return pyjwt.encode(payload, secret, algorithm="HS256")


def make_request(auth_header=None):
    """Create a minimal mock FastAPI Request with the given Authorization header value."""
    mock = MagicMock()
    mock.headers.get.return_value = auth_header or ""
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetOptionalUserId:
    def test_no_jwt_secret_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "")
        request = make_request(f"Bearer {make_token()}")
        assert get_optional_user_id(request) is None

    def test_no_auth_header_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        request = make_request(None)
        assert get_optional_user_id(request) is None

    def test_empty_auth_header_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        request = make_request("")
        assert get_optional_user_id(request) is None

    def test_non_bearer_header_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        request = make_request("Basic dXNlcjpwYXNz")
        assert get_optional_user_id(request) is None

    def test_valid_token_returns_user_id(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        token = make_token()
        request = make_request(f"Bearer {token}")
        assert get_optional_user_id(request) == TEST_USER_ID

    def test_expired_token_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        past = int(time.time()) - 3600  # 1 hour ago
        token = make_token({"exp": past})
        request = make_request(f"Bearer {token}")
        assert get_optional_user_id(request) is None

    def test_wrong_secret_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        token = make_token(secret="completely-different-secret-value!!")
        request = make_request(f"Bearer {token}")
        assert get_optional_user_id(request) is None

    def test_token_missing_sub_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        # Mint token without "sub" claim
        payload = {"aud": "authenticated"}
        token = pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")
        request = make_request(f"Bearer {token}")
        # payload.get("sub") returns None → function returns None
        assert get_optional_user_id(request) is None

    def test_malformed_token_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", TEST_SECRET)
        request = make_request("Bearer this.is.not.a.valid.jwt")
        assert get_optional_user_id(request) is None
