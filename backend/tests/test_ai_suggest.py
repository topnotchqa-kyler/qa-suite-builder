"""
Unit and integration tests for POST /api/ai-suggest endpoint
and generate_field_suggestion() service function.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
import generation

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Unit tests — generate_field_suggestion()
# ---------------------------------------------------------------------------

class TestGenerateFieldSuggestion:

    def test_returns_suggestion_string(self, mocker):
        """Returns the model response text, stripped of surrounding whitespace."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="  Complete this step.  ")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mocker.patch("generation.anthropic.Anthropic", return_value=mock_client)
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "test-key")

        result = generation.generate_field_suggestion(
            field="description",
            current_value="Navigate to the login page and",
            context={
                "title": "Login test", "priority": "High", "category": "Functional",
                "description": "", "preconditions": "", "steps": "", "expected_result": "",
            },
        )
        assert result == "Complete this step."

    def test_strips_whitespace_from_response(self, mocker):
        """Leading/trailing newlines and spaces are stripped from the suggestion."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="\n  Padded suggestion.\n  ")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mocker.patch("generation.anthropic.Anthropic", return_value=mock_client)
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "test-key")

        result = generation.generate_field_suggestion("steps", "1. Open the app\n2. Tap", {})
        assert result == "Padded suggestion."

    def test_raises_value_error_when_no_key(self, mocker):
        """ValueError raised when neither user key nor env var is present."""
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "")
        with pytest.raises(ValueError, match="No Anthropic API key"):
            generation.generate_field_suggestion(
                "description", "some text here for testing", {}, api_key=None
            )

    def test_uses_provided_api_key_not_env(self, mocker):
        """User-supplied api_key takes precedence over the ANTHROPIC_API_KEY env var."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Suggestion.")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_cls = mocker.patch("generation.anthropic.Anthropic", return_value=mock_client)
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "env-key")

        generation.generate_field_suggestion(
            "description", "some value here for test", {}, api_key="user-key"
        )

        mock_cls.assert_called_once_with(api_key="user-key")

    def test_prompt_contains_field_name(self, mocker):
        """The generated prompt includes the name of the field being completed."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Result.")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mocker.patch("generation.anthropic.Anthropic", return_value=mock_client)
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "test-key")

        generation.generate_field_suggestion("expected_result", "The user should see the", {})

        call_args = mock_client.messages.create.call_args
        prompt_text = call_args.kwargs["messages"][0]["content"]
        assert "expected_result" in prompt_text

    def test_uses_suggest_model_not_main_model(self, mocker):
        """Suggestions use SUGGEST_MODEL (Haiku), not MODEL (Sonnet)."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Result.")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mocker.patch("generation.anthropic.Anthropic", return_value=mock_client)
        mocker.patch.object(generation, "ANTHROPIC_API_KEY", "test-key")

        generation.generate_field_suggestion(
            "description", "some text here for the test pad", {}
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == generation.SUGGEST_MODEL
        assert call_args.kwargs["model"] != generation.MODEL


# ---------------------------------------------------------------------------
# Endpoint integration tests — POST /api/ai-suggest
# ---------------------------------------------------------------------------

class TestAiSuggestEndpoint:

    def test_valid_request_returns_suggestion(self, mocker):
        """200 with {suggestion: ...} for a valid field and value."""
        mocker.patch(
            "main.generate_field_suggestion",
            return_value="Enter valid credentials and click Submit.",
        )
        res = client.post(
            "/api/ai-suggest",
            json={
                "field": "steps",
                "current_value": "1. Navigate to the login page\n2. Enter",
                "context": {
                    "title": "Login", "priority": "High", "category": "Functional",
                    "description": "", "preconditions": "", "steps": "", "expected_result": "",
                },
            },
            headers={"X-Api-Key": "test-key"},
        )
        assert res.status_code == 200
        assert res.json()["suggestion"] == "Enter valid credentials and click Submit."

    def test_missing_api_key_returns_400(self, mocker):
        """400 with a descriptive message when no API key is available."""
        mocker.patch(
            "main.generate_field_suggestion",
            side_effect=ValueError("No Anthropic API key provided."),
        )
        res = client.post(
            "/api/ai-suggest",
            json={
                "field": "description",
                "current_value": "This test validates the login flow by checking",
                "context": {},
            },
        )
        assert res.status_code == 400
        assert "API key" in res.json()["detail"]

    def test_invalid_field_returns_400(self):
        """400 when field is not one of the allowed suggestion fields."""
        res = client.post(
            "/api/ai-suggest",
            json={
                "field": "title",    # not in SUGGEST_FIELDS
                "current_value": "Some title text here padding",
                "context": {},
            },
        )
        assert res.status_code == 400

    def test_value_too_short_returns_400(self):
        """400 when current_value is fewer than 15 characters."""
        res = client.post(
            "/api/ai-suggest",
            json={
                "field": "description",
                "current_value": "Too short",    # < 15 chars
                "context": {},
            },
        )
        assert res.status_code == 400

    def test_anthropic_exception_returns_500(self, mocker):
        """500 when the Anthropic call raises an unexpected exception."""
        mocker.patch(
            "main.generate_field_suggestion",
            side_effect=RuntimeError("API timeout"),
        )
        res = client.post(
            "/api/ai-suggest",
            json={
                "field": "description",
                "current_value": "This test validates something important here",
                "context": {},
            },
        )
        assert res.status_code == 500
