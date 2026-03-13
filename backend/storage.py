"""
storage.py — Supabase persistence for generated test suites.

All operations are best-effort: callers should catch exceptions rather than
letting a storage failure abort an otherwise successful generation.
"""

import logging
import os
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ENV = os.getenv("SUPABASE_ENV", "development")


def _get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def save_suite(
    crawl_data: dict,
    test_suite: dict,
    user_id: Optional[str] = None,
) -> str:
    """
    Persist a generated test suite alongside its crawl data.
    Returns the new row's UUID string.

    user_id is optional — anonymous suites are saved with user_id=NULL.
    """
    client = _get_client()
    result = (
        client.table("test_suites")
        .insert({
            "base_url":    crawl_data.get("base_url", ""),
            "site_name":   test_suite.get("site_name", ""),
            "crawl_data":  crawl_data,
            "test_suite":  test_suite,
            "environment": SUPABASE_ENV,
            "user_id":     user_id,   # NULL when anonymous — column accepts NULL
        })
        .execute()
    )
    return result.data[0]["id"]


def get_suite(suite_id: str) -> Optional[dict]:
    """
    Fetch a saved suite by UUID.
    Returns the full row dict or None if not found.
    """
    client = _get_client()
    result = (
        client.table("test_suites")
        .select("*")
        .eq("id", suite_id)
        .single()
        .execute()
    )
    return result.data if result.data else None


def list_suites(user_id: str, limit: int = 20) -> list:
    """
    Return the authenticated user's most recent suites, newest first.
    Only returns metadata columns (no crawl_data / test_suite blobs).
    """
    client = _get_client()
    result = (
        client.table("test_suites")
        .select("id, base_url, site_name, created_at, environment")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def snapshot_version(suite_id: str, current_test_suite: dict) -> int:
    """
    Capture the current test_suite as a version snapshot before an edit overwrites it.
    Returns the new version_number (1-based, monotonically increasing per suite).

    This is NOT best-effort. Callers must abort the PATCH if this raises —
    overwriting without a snapshot would silently destroy history.
    """
    client = _get_client()
    result = (
        client.table("test_suite_versions")
        .select("version_number")
        .eq("suite_id", suite_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    prev = result.data[0]["version_number"] if result.data else 0
    next_version = prev + 1
    client.table("test_suite_versions").insert({
        "suite_id":       suite_id,
        "version_number": next_version,
        "test_suite":     current_test_suite,
    }).execute()
    return next_version


def update_suite_test_suite(suite_id: str, test_suite: dict) -> None:
    """
    Overwrite the test_suite JSONB column for an existing suite.
    Does not touch crawl_data, user_id, or any other column.
    Raises ValueError if suite_id is not found or update returns no rows.
    """
    client = _get_client()
    result = (
        client.table("test_suites")
        .update({"test_suite": test_suite})
        .eq("id", suite_id)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Suite {suite_id} not found or update returned no rows.")


def list_suite_versions(suite_id: str, limit: int = 20) -> list:
    """
    Return [{id, version_number, created_at}] for a suite, newest first.
    Does NOT return the test_suite JSONB blob — keeps the list response lightweight.
    """
    client = _get_client()
    result = (
        client.table("test_suite_versions")
        .select("id, version_number, created_at")
        .eq("suite_id", suite_id)
        .order("version_number", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_suite_version(suite_id: str, version_number: int) -> Optional[dict]:
    """
    Return {version_number, test_suite, created_at} for a single snapshot, or None.
    """
    client = _get_client()
    result = (
        client.table("test_suite_versions")
        .select("version_number, test_suite, created_at")
        .eq("suite_id", suite_id)
        .eq("version_number", version_number)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
