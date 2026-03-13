"""
Security and behaviour tests for version history endpoints:
  GET /api/suites/{suite_id}/versions
  GET /api/suites/{suite_id}/versions/{version_number}

All external dependencies (Supabase, auth JWT) are mocked via
app.dependency_overrides and mocker.patch.  No real network calls are made.

Test matrix:
  - owner can list versions              → 200, {versions: [...]}
  - non-owner cannot list versions       → 403
  - unauthenticated cannot list versions → 401
  - missing suite on list               → 404
  - owner can get a specific version    → 200, {version_number, test_suite, created_at}
  - non-owner cannot get version        → 403
  - missing version returns 404
"""

import pytest
from fastapi.testclient import TestClient

import main
from main import app
from auth import get_required_user_id

# ── Constants ──────────────────────────────────────────────────────────────────

OWNER_ID  = "aaaaaaaa-0000-0000-0000-000000000001"
OTHER_ID  = "bbbbbbbb-0000-0000-0000-000000000002"
SUITE_ID  = "cccccccc-0000-0000-0000-000000000003"

STORED_SUITE = {
    "id":         SUITE_ID,
    "user_id":    OWNER_ID,
    "base_url":   "https://example.com",
    "site_name":  "Example",
    "test_suite": {"site_name": "Example", "sections": []},
}

STORED_VERSIONS = [
    {"id": "vv000001", "version_number": 2, "created_at": "2026-03-13T01:00:00+00:00"},
    {"id": "vv000002", "version_number": 1, "created_at": "2026-03-12T10:00:00+00:00"},
]

STORED_VERSION = {
    "version_number": 1,
    "test_suite": {"site_name": "Example", "sections": []},
    "created_at": "2026-03-12T10:00:00+00:00",
}

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _override_user(user_id: str):
    """Override get_required_user_id to return the given user_id."""
    app.dependency_overrides[get_required_user_id] = lambda: user_id


def _clear_overrides():
    app.dependency_overrides.clear()


# ── Tests: GET /api/suites/{suite_id}/versions ────────────────────────────────

class TestListVersionsEndpoint:

    def test_owner_can_list_versions(self, mocker):
        """Owner receives 200 with the version list."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.list_suite_versions", return_value=STORED_VERSIONS)

        res = client.get(f"/api/suites/{SUITE_ID}/versions")

        assert res.status_code == 200
        data = res.json()
        assert "versions" in data
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version_number"] == 2

        _clear_overrides()

    def test_non_owner_cannot_list_versions(self, mocker):
        """A different authenticated user cannot view another user's version history."""
        _override_user(OTHER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)  # owned by OWNER_ID

        res = client.get(f"/api/suites/{SUITE_ID}/versions")

        assert res.status_code == 403

        _clear_overrides()

    def test_unauthenticated_list_versions(self):
        """No token → real get_required_user_id → 401."""
        # Do NOT override get_required_user_id; real dependency runs.
        res = client.get(f"/api/suites/{SUITE_ID}/versions")
        assert res.status_code == 401

        _clear_overrides()

    def test_missing_suite_list_versions(self, mocker):
        """Suite not found in storage → 404."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=None)

        res = client.get(f"/api/suites/{SUITE_ID}/versions")

        assert res.status_code == 404

        _clear_overrides()


# ── Tests: GET /api/suites/{suite_id}/versions/{version_number} ───────────────

class TestGetVersionEndpoint:

    def test_owner_can_get_version(self, mocker):
        """Owner receives 200 with the snapshot content."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.get_suite_version", return_value=STORED_VERSION)

        res = client.get(f"/api/suites/{SUITE_ID}/versions/1")

        assert res.status_code == 200
        data = res.json()
        assert data["version_number"] == 1
        assert "test_suite" in data
        assert "created_at" in data

        _clear_overrides()

    def test_non_owner_cannot_get_version(self, mocker):
        """A different authenticated user cannot fetch another user's snapshot."""
        _override_user(OTHER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)  # owned by OWNER_ID

        res = client.get(f"/api/suites/{SUITE_ID}/versions/1")

        assert res.status_code == 403

        _clear_overrides()

    def test_missing_version_returns_404(self, mocker):
        """Version number not found → 404."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.get_suite_version", return_value=None)

        res = client.get(f"/api/suites/{SUITE_ID}/versions/99")

        assert res.status_code == 404

        _clear_overrides()
