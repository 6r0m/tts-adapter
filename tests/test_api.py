"""API tests for TTS adapter.

Run with: uv run pytest tests/test_api.py -v
Requires running server at localhost:9880
"""

import pytest
import httpx

BASE_URL = "http://localhost:9880"


@pytest.fixture
def client():
    """HTTP client for API tests."""
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


class TestHealth:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint returns ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_health_contains_engine_info(self, client):
        """Health endpoint contains engine and model info."""
        response = client.get("/health")
        data = response.json()
        assert "engine" in data
        assert "model" in data
        assert "device" in data

    def test_health_contains_capabilities(self, client):
        """Health endpoint contains capability flags."""
        response = client.get("/health")
        data = response.json()
        assert "supports_cloning" in data
        assert "supports_design" in data
        assert "supports_custom_voice" in data
        assert isinstance(data["supports_cloning"], bool)
        assert isinstance(data["supports_design"], bool)
        assert isinstance(data["supports_custom_voice"], bool)


class TestWebUI:
    """Tests for Web UI endpoint."""

    def test_web_ui_returns_html(self, client):
        """Root endpoint returns HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "TTS Adapter" in response.text


class TestTTSDesignValidation:
    """Tests for /tts/design validation errors."""

    def test_design_missing_text_returns_422(self, client):
        """Missing text field returns 422."""
        response = client.post(
            "/tts/design",
            data={"instruct": "Female voice", "language": "Russian"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_design_missing_instruct_returns_422(self, client):
        """Missing instruct field returns 422."""
        response = client.post(
            "/tts/design",
            data={"text": "привет", "language": "Russian"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_design_422_error_is_parseable(self, client):
        """422 error detail can be parsed for user-friendly message."""
        response = client.post(
            "/tts/design",
            data={"text": "привет", "language": "Russian"},
        )
        assert response.status_code == 422
        data = response.json()
        detail = data["detail"]
        # FastAPI returns array for validation errors
        assert isinstance(detail, list)
        assert len(detail) > 0
        # Each error has msg field for user-friendly display
        assert "msg" in detail[0]
        # msg should be a human-readable string
        assert isinstance(detail[0]["msg"], str)
        assert len(detail[0]["msg"]) > 0

    def test_design_422_error_contains_field_location(self, client):
        """422 error includes location of missing field."""
        response = client.post(
            "/tts/design",
            data={"text": "привет", "language": "Russian"},
        )
        data = response.json()
        detail = data["detail"][0]
        # loc tells which field is missing
        assert "loc" in detail
        assert "instruct" in detail["loc"]


class TestTTSCloneValidation:
    """Tests for /tts/clone validation errors."""

    def test_clone_missing_audio_returns_422(self, client):
        """Missing reference_audio returns 422."""
        response = client.post(
            "/tts/clone",
            data={"text": "привет", "language": "Russian"},
        )
        assert response.status_code == 422


class TestTTSValidation:
    """Tests for /tts endpoint validation."""

    def test_tts_missing_text_returns_422(self, client):
        """Missing text field returns 422."""
        response = client.post(
            "/tts",
            json={"language": "Russian"},
        )
        assert response.status_code == 422


class TestTTSDesignGeneration:
    """Tests for /tts/design actual generation (requires VoiceDesign model)."""

    def test_design_generates_wav(self, client):
        """Voice design endpoint generates WAV audio."""
        # Check if design is supported
        health = client.get("/health").json()
        if not health.get("supports_design"):
            pytest.skip("VoiceDesign model not loaded")

        response = client.post(
            "/tts/design",
            data={
                "text": "привет",
                "instruct": "Adult female voice, warm and friendly",
                "language": "Russian",
            },
            timeout=120.0,  # TTS can be slow
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        # WAV files start with RIFF header
        assert response.content[:4] == b"RIFF"
