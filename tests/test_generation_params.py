"""Tests for generation parameters passthrough.

Run with: uv run pytest tests/test_generation_params.py -v
Integration tests (TestGenerationSettings*) skip cleanly via the `live_client`
fixture (conftest.py) when no server is running at localhost:9880.
Unit tests (TestGenerationSettingsUnit) run without a server.
"""

import pytest
from pydantic import ValidationError

from tts_adapter.contract import GenerationSettings, TTSRequest


# Backwards-compatible alias for existing tests that reference `client`.
@pytest.fixture
def client(live_client):
    return live_client


class TestGenerationSettingsContract:
    """Tests that generation params are accepted by API without errors."""

    def test_tts_accepts_generation_settings(self, client):
        """POST /tts accepts generation settings in request body."""
        health = client.get("/health").json()
        if not health.get("supports_custom_voice"):
            pytest.skip("CustomVoice model not loaded")

        response = client.post(
            "/tts",
            json={
                "text": "тест",
                "language": "Russian",
                "speaker": "Serena",
                "generation": {
                    "temperature": 0.7,
                    "top_k": 30,
                    "top_p": 0.9,
                    "repetition_penalty": 1.1,
                    "max_new_tokens": 1024,
                },
            },
            timeout=120.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    def test_tts_works_without_generation_settings(self, client):
        """POST /tts works when generation settings are omitted (defaults)."""
        health = client.get("/health").json()
        if not health.get("supports_custom_voice"):
            pytest.skip("CustomVoice model not loaded")

        response = client.post(
            "/tts",
            json={
                "text": "тест",
                "language": "Russian",
                "speaker": "Serena",
            },
            timeout=120.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    def test_tts_partial_generation_settings(self, client):
        """POST /tts accepts partial generation settings (only some fields)."""
        health = client.get("/health").json()
        if not health.get("supports_custom_voice"):
            pytest.skip("CustomVoice model not loaded")

        response = client.post(
            "/tts",
            json={
                "text": "тест",
                "language": "Russian",
                "speaker": "Serena",
                "generation": {"temperature": 0.5},
            },
            timeout=120.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    def test_design_accepts_generation_params(self, client):
        """POST /tts/design accepts generation params as form fields."""
        health = client.get("/health").json()
        if not health.get("supports_design"):
            pytest.skip("VoiceDesign model not loaded")

        response = client.post(
            "/tts/design",
            data={
                "text": "тест",
                "instruct": "Adult female voice, warm",
                "language": "Russian",
                "temperature": "0.7",
                "top_k": "30",
                "top_p": "0.9",
                "repetition_penalty": "1.1",
                "max_new_tokens": "1024",
            },
            timeout=120.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    def test_clone_accepts_generation_params(self, client):
        """POST /tts/clone accepts generation params as form fields."""
        health = client.get("/health").json()
        if not health.get("supports_cloning"):
            pytest.skip("Base model not loaded")

        # Create a minimal WAV file for testing
        import struct

        sample_rate = 16000
        duration = 1
        num_samples = sample_rate * duration
        wav_data = struct.pack("<4sI4s", b"RIFF", 36 + num_samples * 2, b"WAVE")
        wav_data += struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        wav_data += struct.pack("<4sI", b"data", num_samples * 2)
        wav_data += b"\x00" * (num_samples * 2)

        response = client.post(
            "/tts/clone",
            data={
                "text": "тест",
                "language": "Russian",
                "temperature": "0.7",
                "top_k": "30",
            },
            files={"reference_audio": ("ref.wav", wav_data, "audio/wav")},
            timeout=120.0,
        )
        # 200 = success, 400 = bad audio (too short/silent). Never 422 (validation) or 500 (crash).
        assert response.status_code in {200, 400}, f"Unexpected status: {response.status_code}"


class TestGenerationSettingsUnit:
    """Unit tests for GenerationSettings validation (no server needed)."""

    def test_valid_settings(self):
        """Valid settings are accepted."""
        s = GenerationSettings(temperature=0.7, top_k=30, top_p=0.9, repetition_penalty=1.1, max_new_tokens=1024)
        assert s.temperature == 0.7
        assert s.top_k == 30

    def test_defaults_are_none(self):
        """All defaults are None (use library defaults)."""
        s = GenerationSettings()
        assert s.temperature is None
        assert s.top_k is None
        assert s.top_p is None
        assert s.repetition_penalty is None
        assert s.max_new_tokens is None

    def test_to_kwargs_excludes_none(self):
        """to_kwargs() returns only non-None values."""
        s = GenerationSettings(temperature=0.5)
        kwargs = s.to_kwargs()
        assert kwargs == {"temperature": 0.5}

    def test_to_kwargs_empty_when_all_defaults(self):
        """to_kwargs() returns empty dict when all None."""
        s = GenerationSettings()
        assert s.to_kwargs() == {}

    def test_temperature_too_high(self):
        """Temperature above 2.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(temperature=5.0)

    def test_temperature_too_low(self):
        """Temperature below 0.01 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(temperature=0.0)

    def test_top_k_too_low(self):
        """Top-k below 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(top_k=0)

    def test_top_p_too_high(self):
        """Top-p above 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(top_p=1.5)

    def test_repetition_penalty_too_low(self):
        """Repetition penalty below 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(repetition_penalty=0.5)

    def test_max_new_tokens_too_low(self):
        """Max new tokens below 256 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(max_new_tokens=10)

    def test_max_new_tokens_too_high(self):
        """Max new tokens above 4096 raises ValidationError."""
        with pytest.raises(ValidationError):
            GenerationSettings(max_new_tokens=10000)

    def test_tts_request_with_generation(self):
        """TTSRequest accepts generation settings."""
        req = TTSRequest(
            text="test",
            language="Russian",
            speaker="Serena",
            generation={"temperature": 0.5, "top_k": 30},
        )
        assert req.generation.temperature == 0.5
        assert req.generation.top_k == 30
        assert req.generation.top_p is None

    def test_tts_request_without_generation(self):
        """TTSRequest works without generation (defaults)."""
        req = TTSRequest(text="test")
        assert req.generation.to_kwargs() == {}

    def test_tts_request_invalid_generation_raises(self):
        """TTSRequest with invalid generation raises ValidationError."""
        with pytest.raises(ValidationError):
            TTSRequest(text="test", generation={"temperature": 99.0})
