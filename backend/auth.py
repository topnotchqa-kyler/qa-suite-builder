"""
auth.py — Optional JWT verification FastAPI dependency.

Supports both JWT signing modes used by Supabase:
  - RS256 (asymmetric): used by modern Supabase projects (sb_publishable_* keys).
    Verified using PyJWKClient against the Supabase JWKS endpoint. Keys are
    cached in-process so only the first request per process incurs a fetch.
  - HS256 (symmetric): used by legacy Supabase projects and by unit tests.
    Verified using the SUPABASE_JWT_SECRET shared secret.

The algorithm is detected from the JWT header — no configuration needed.
"""

import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# PyJWKClient caches the fetched keys internally — one client per process.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> Optional[PyJWKClient]:
    """Return a cached PyJWKClient pointed at the Supabase JWKS endpoint."""
    global _jwks_client
    if _jwks_client is None and SUPABASE_URL:
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def get_optional_user_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency. Returns the Supabase user UUID string if a valid
    Bearer token is present in the Authorization header, otherwise None.

    Detects the JWT algorithm from the token header and routes to the
    appropriate verification path (RS256 via JWKS or HS256 via secret).

    Usage in a route:
        from auth import get_optional_user_id
        from fastapi import Depends

        @app.post("/api/generate-from-crawl")
        async def endpoint(
            request: Request,
            ...,
            user_id: Optional[str] = Depends(get_optional_user_id),
        ):
            ...
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning(
            "Auth: no Bearer token in request (header=%r)",
            auth_header[:20] if auth_header else "",
        )
        return None

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        logger.warning("Auth: Bearer header present but token is empty")
        return None

    # Peek at the header to select the verification path.
    try:
        alg = jwt.get_unverified_header(token).get("alg", "RS256")
    except jwt.DecodeError as exc:
        logger.warning("Auth: could not parse JWT header (%s)", exc)
        return None

    if alg == "HS256":
        # Legacy / test path: verify with shared secret.
        if not SUPABASE_JWT_SECRET:
            logger.warning("Auth: HS256 token received but SUPABASE_JWT_SECRET is not set")
            return None
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            logger.warning("JWT expired — treating as anonymous")
            return None
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT invalid (%s) — treating as anonymous", exc)
            return None
    else:
        # Modern path: verify with JWKS (RS256 and other asymmetric algorithms).
        client = _get_jwks_client()
        if client is None:
            logger.warning("Auth: SUPABASE_URL not set — cannot verify RS256 token")
            return None
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            logger.warning("JWT expired — treating as anonymous")
            return None
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT invalid (%s) — treating as anonymous", exc)
            return None
        except Exception as exc:
            logger.warning("JWT verification error (%s) — treating as anonymous", exc)
            return None


def get_required_user_id(request: Request) -> str:
    """
    FastAPI dependency. Like get_optional_user_id but raises HTTP 401 when
    no valid token is present. Use on endpoints that require authentication.

    Usage in a route:
        from auth import get_required_user_id
        from fastapi import Depends

        @app.patch("/api/suites/{suite_id}")
        async def endpoint(
            suite_id: str,
            user_id: str = Depends(get_required_user_id),
        ):
            ...
    """
    user_id = get_optional_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user_id
