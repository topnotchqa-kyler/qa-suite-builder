"""
Security and behaviour tests for PATCH /api/suites/{suite_id}.

All external dependencies (Supabase, auth JWT) are mocked via
app.dependency_overrides and mocker.patch.  No real network calls are made.

Test matrix:
  - owner can PATCH               → 200, returns {suite_id, version_number}
  - non-owner gets 403
  - unauthenticated gets 401
  - anonymous suite (user_id=None) gets 403
  - missing suite gets 404
  - snapshot failure returns 500 and does NOT call update_suite_test_suite
"""

import pytest
from fastapi.testclient import TestClient

import main
from main import app
from auth import get_required_user_id

# ── Constants ──────────────────────────────────────────────────────────────────

OWNER_ID   = "aaaaaaaa-0000-0000-0000-000000000001"
OTHER_ID   = "bbbbbbbb-0000-0000-0000-000000000002"
SUITE_ID   = "cccccccc-0000-0000-0000-000000000003"

STORED_SUITE = {
    "id":         SUITE_ID,
    "user_id":    OWNER_ID,
    "base_url":   "https://example.com",
    "site_name":  "Example",
    "test_suite": {
        "site_name": "Example",
        "sections":  [],
    },
}

NEW_TEST_SUITE = {
    "site_name": "Example",
    "sections":  [{"name": "Home", "source_url": "https://example.com", "test_cases": []}],
}

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _override_user(user_id: str):
    """Override get_required_user_id to return the given user_id."""
    app.dependency_overrides[get_required_user_id] = lambda: user_id


def _clear_overrides():
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPatchSuiteEndpoint:

    def test_owner_can_patch(self, mocker):
        """Owner receives 200 with suite_id and version_number."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.snapshot_version", return_value=1)
        mocker.patch("main.update_suite_test_suite", return_value=None)

        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        assert res.status_code == 200
        data = res.json()
        assert data["suite_id"] == SUITE_ID
        assert data["version_number"] == 1

        _clear_overrides()

    def test_non_owner_gets_403(self, mocker):
        """A different authenticated user cannot edit someone else's suite."""
        _override_user(OTHER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)  # suite owned by OWNER_ID

        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        assert res.status_code == 403

        _clear_overrides()

    def test_unauthenticated_gets_401(self):
        """No dependency override → real get_required_user_id → 401 (no valid token)."""
        # Do NOT override get_required_user_id; real dependency runs.
        # TestClient sends no Authorization header so user_id → None → 401.
        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})
        assert res.status_code == 401

        _clear_overrides()

    def test_anonymous_suite_gets_403(self, mocker):
        """A suite with user_id=None is uneditable by any authenticated user."""
        _override_user(OWNER_ID)
        anon_suite = {**STORED_SUITE, "user_id": None}
        mocker.patch("main.get_suite", return_value=anon_suite)

        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        assert res.status_code == 403

        _clear_overrides()

    def test_missing_suite_gets_404(self, mocker):
        """Suite not found in storage → 404."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=None)

        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        assert res.status_code == 404

        _clear_overrides()

    def test_snapshot_failure_returns_500(self, mocker):
        """If snapshot_version raises, the endpoint returns 500."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.snapshot_version", side_effect=RuntimeError("DB down"))
        mock_update = mocker.patch("main.update_suite_test_suite")

        res = client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        assert res.status_code == 500

        _clear_overrides()

    def test_snapshot_failure_does_not_call_update(self, mocker):
        """If snapshot_version fails, update_suite_test_suite must NOT be called."""
        _override_user(OWNER_ID)
        mocker.patch("main.get_suite", return_value=STORED_SUITE)
        mocker.patch("main.snapshot_version", side_effect=RuntimeError("DB down"))
        mock_update = mocker.patch("main.update_suite_test_suite")

        client.patch(f"/api/suites/{SUITE_ID}", json={"test_suite": NEW_TEST_SUITE})

        mock_update.assert_not_called()

        _clear_overrides()
