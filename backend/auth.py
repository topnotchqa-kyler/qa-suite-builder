"""
auth.py — Optional JWT verification FastAPI dependency.

Extracts the user_id from a valid Supabase-issued JWT, or returns None
if no token is present or the token is invalid. Never raises — auth is
optional for all current endpoints.
"""

import logging
import os
from typing import Optional

import jwt
from fastapi import Request

logger = logging.getLogger(__name__)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def get_optional_user_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency. Returns the Supabase user UUID string if a valid
    Bearer token is present in the Authorization header, otherwise None.

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
    if not SUPABASE_JWT_SECRET:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            # Supabase sets aud="authenticated" but we don't pass audience=
            # so we must disable audience verification to avoid InvalidAudienceError.
            # Signature verification with the secret is still fully enforced.
            options={"verify_aud": False},
        )
        # "sub" claim holds the user UUID in all Supabase-issued JWTs
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired — treating as anonymous")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT invalid (%s) — treating as anonymous", exc)
        return None
