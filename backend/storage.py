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


def list_suites(limit: int = 20) -> list:
    """
    Return the most recent suites, newest first.
    Only returns metadata columns (no crawl_data / test_suite blobs).
    """
    client = _get_client()
    result = (
        client.table("test_suites")
        .select("id, base_url, site_name, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
