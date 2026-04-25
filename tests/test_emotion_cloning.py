"""Tests for emotional voice cloning (clone + emotion combined).

Run with: uv run pytest tests/test_emotion_cloning.py -v

Mix of:
  - Unit tests (no server needed) — validate routes.py helper logic.
  - Integration tests — require a running server at localhost:9880.
    Skipped automatically if the current engine doesn't expose
    `supports_emotional_cloning=True`.

Mirrors the patterns in tests/test_api.py (httpx + capability skip).
"""

import struct

import httpx
import pytest

from tts_adapter.api.routes import _MAX_UPLOAD_BYTES, _parse_emotion_vector

BASE_URL = "http://localhost:9880"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


def _minimal_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Build a minimal silent WAV file for upload tests."""
    num_samples = int(sample_rate * seconds)
    header = struct.pack("<4sI4s", b"RIFF", 36 + num_samples * 2, b"WAVE")
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data = struct.pack("<4sI", b"data", num_samples * 2) + b"\x00" * (num_samples * 2)
    return header + fmt + data


class TestEmotionVectorParsingUnit:
    """Unit tests for _parse_emotion_vector — no server needed."""

    def test_empty_returns_none(self):
        assert _parse_emotion_vector("") is None

    def test_eight_floats_parsed(self):
        assert _parse_emotion_vector("0,0,0.8,0,0,0,0,0") == [0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0]

    def test_wrong_length_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _parse_emotion_vector("1,2,3")
        assert exc.value.status_code == 400
        assert "8 floats" in exc.value.detail

    def test_non_numeric_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _parse_emotion_vector("a,b,c,d,e,f,g,h")
        assert exc.value.status_code == 400
        assert "comma-separated floats" in exc.value.detail


class TestUploadSizeUnit:
    def test_max_upload_bytes_is_20mb(self):
        assert _MAX_UPLOAD_BYTES == 20 * 1024 * 1024


class TestEmotionRejectionOnNonSupportingEngine:
    """Integration: emotion params should be rejected (400) when engine
    does not support emotional cloning. Skips if the live engine DOES
    support it (so this is the "Qwen3 mode" test).
    """

    def test_emotion_text_rejected_on_qwen3(self, client):
        health = client.get("/health").json()
        if health.get("supports_emotional_cloning"):
            pytest.skip("Engine supports emotional cloning — see TestEmotionalClone")
        if not health.get("supports_cloning"):
            pytest.skip("Cloning not supported by current model")

        wav = _minimal_wav()
        response = client.post(
            "/tts/clone",
            data={"text": "test", "language": "Russian", "emotion_text": "angry"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "emotional cloning" in response.json()["detail"].lower()


class TestEmotionalClone:
    """Integration: full clone+emotion happy path. Skips when engine
    is not emotional-cloning capable.
    """

    def _ensure_capable(self, client):
        health = client.get("/health").json()
        if not health.get("supports_emotional_cloning"):
            pytest.skip("Current engine does not support emotional cloning")
        return health

    def test_clone_with_emotion_text(self, client):
        self._ensure_capable(client)
        wav = _minimal_wav(seconds=2.0)
        response = client.post(
            "/tts/clone",
            data={
                "text": "test",
                "emotion_text": "very excited",
                "emotion_alpha": "0.6",
            },
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
            timeout=120.0,
        )
        # 200 = generated. 400 = bad audio (silent). Never 422/500.
        assert response.status_code in {200, 400}, response.text

    def test_clone_with_emotion_vector(self, client):
        self._ensure_capable(client)
        wav = _minimal_wav(seconds=2.0)
        response = client.post(
            "/tts/clone",
            data={
                "text": "test",
                "emotion_vector": "0,0,0.8,0,0,0,0,0",
                "emotion_alpha": "0.7",
            },
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
            timeout=120.0,
        )
        assert response.status_code in {200, 400}, response.text

    def test_clone_no_emotion_still_works(self, client):
        """Plain clone path must remain functional alongside emotion params."""
        health = client.get("/health").json()
        if not health.get("supports_cloning"):
            pytest.skip("Cloning not supported by current model")
        wav = _minimal_wav(seconds=2.0)
        response = client.post(
            "/tts/clone",
            data={"text": "test"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
            timeout=120.0,
        )
        assert response.status_code in {200, 400}, response.text

    def test_multiple_emotion_modes_rejected(self, client):
        self._ensure_capable(client)
        wav = _minimal_wav()
        response = client.post(
            "/tts/clone",
            data={
                "text": "test",
                "emotion_text": "angry",
                "emotion_vector": "0,0,0.8,0,0,0,0,0",
            },
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "only one emotion mode" in response.json()["detail"].lower()

    def test_alpha_out_of_range_rejected(self, client):
        self._ensure_capable(client)
        wav = _minimal_wav()
        response = client.post(
            "/tts/clone",
            data={"text": "test", "emotion_text": "angry", "emotion_alpha": "1.5"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "0.0 and 1.0" in response.json()["detail"]

    def test_vector_wrong_length_rejected(self, client):
        self._ensure_capable(client)
        wav = _minimal_wav()
        response = client.post(
            "/tts/clone",
            data={"text": "test", "emotion_vector": "1,2,3"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "8 floats" in response.json()["detail"]


class TestHealthExposesEmotionalFlag:
    """Health endpoint must report supports_emotional_cloning."""

    def test_health_contains_supports_emotional_cloning(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "supports_emotional_cloning" in data
        assert isinstance(data["supports_emotional_cloning"], bool)
