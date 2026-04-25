"""Tests for emotional voice cloning (clone + emotion combined).

Run with: uv run pytest tests/test_emotion_cloning.py -v

Three layers:
  - Unit tests for routes.py helpers (no server needed).
  - Unit tests for IndexTTS2RemoteEngine with mocked httpx (no worker needed).
  - Integration tests against a running server (use the live_client fixture
    from conftest.py - they auto-skip when the server is absent).

Mirrors the patterns in tests/test_api.py.
"""

import io
import struct
from unittest.mock import MagicMock

import httpx
import pytest

from tts_adapter.api.routes import _MAX_UPLOAD_BYTES, _parse_emotion_vector, _validate_upload_size
from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine


def _minimal_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Build a minimal silent WAV file for upload tests."""
    num_samples = int(sample_rate * seconds)
    header = struct.pack("<4sI4s", b"RIFF", 36 + num_samples * 2, b"WAVE")
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data = struct.pack("<4sI", b"data", num_samples * 2) + b"\x00" * (num_samples * 2)
    return header + fmt + data


# ---------- Routes-helper unit tests (no server, no engine) ----------


class TestEmotionVectorParsingUnit:
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
    """Real rejection - not just a constant assertion."""

    def test_max_upload_bytes_is_20mb(self):
        assert _MAX_UPLOAD_BYTES == 20 * 1024 * 1024

    def test_oversized_upload_rejected_413(self):
        from fastapi import HTTPException

        fake = MagicMock(size=_MAX_UPLOAD_BYTES + 1)
        with pytest.raises(HTTPException) as exc:
            _validate_upload_size(fake, "reference_audio")
        assert exc.value.status_code == 413
        assert "reference_audio" in exc.value.detail

    def test_at_limit_passes(self):
        fake = MagicMock(size=_MAX_UPLOAD_BYTES)
        _validate_upload_size(fake, "reference_audio")  # no raise

    def test_unknown_size_passes(self):
        fake = MagicMock(size=None)
        _validate_upload_size(fake, "reference_audio")  # no raise

    def test_none_upload_passes(self):
        _validate_upload_size(None, "emotion_audio")  # no raise


# ---------- IndexTTS2RemoteEngine unit tests (mock httpx, no worker) ----------


def _stub_response(status_code: int = 200, content: bytes = b"WAV", json_body=None):
    """Build a duck-typed httpx Response stand-in."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if json_body is not None:
        resp.json.return_value = json_body
    if status_code >= 400:
        resp.text = (json_body or {}).get("detail", "error") if json_body else "error"
    return resp


class TestRemoteEngineForwarding:
    """Verify the engine builds the right HTTP request without a real worker."""

    def test_protocol_conformance(self):
        from tts_adapter.engine import TTSEngine

        e = IndexTTS2RemoteEngine()
        assert isinstance(e, TTSEngine)
        assert e.engine_name == "indextts2"
        assert e.supports_cloning is True
        assert e.supports_emotional_cloning is True
        assert e.supports_design is False

    def test_synthesize_clone_wires_form_fields(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.return_value = _stub_response(200, b"WAV-BYTES")
        e._client = mock_client  # bypass lazy construction

        out = e.synthesize_clone(
            text="hi",
            reference_audio=b"refbytes",
            language="Russian",
            reference_text="prior text",
            emotion_text="excited",
            emotion_alpha=0.6,
            temperature=0.7,
            top_k=30,
        )
        assert out == b"WAV-BYTES"

        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        url = call.args[0] if call.args else call.kwargs.get("url")
        assert url.endswith("/tts/clone")

        data = call.kwargs["data"]
        assert data["text"] == "hi"
        assert data["language"] == "Russian"
        assert data["reference_text"] == "prior text"
        assert data["emotion_text"] == "excited"
        assert data["emotion_alpha"] == "0.6"
        assert data["temperature"] == "0.7"
        assert data["top_k"] == "30"
        # Modes not used must be absent (not empty strings).
        assert "emotion_audio" not in data
        assert "emotion_vector" not in data

        files = call.kwargs["files"]
        names = [f[0] for f in files]
        assert names == ["reference_audio"]  # no emotion_audio attached

    def test_synthesize_clone_attaches_emotion_audio(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.return_value = _stub_response(200, b"WAV")
        e._client = mock_client

        e.synthesize_clone(
            text="t",
            reference_audio=b"ref",
            emotion_audio=b"emo",
            emotion_alpha=0.9,
        )
        files = mock_client.post.call_args.kwargs["files"]
        names = [f[0] for f in files]
        assert names == ["reference_audio", "emotion_audio"]

    def test_synthesize_clone_serializes_emotion_vector(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.return_value = _stub_response(200, b"WAV")
        e._client = mock_client

        e.synthesize_clone(
            text="t",
            reference_audio=b"ref",
            emotion_vector=[0, 0, 0.8, 0, 0, 0, 0, 0],
            emotion_alpha=0.7,
        )
        data = mock_client.post.call_args.kwargs["data"]
        assert data["emotion_vector"] == "0,0,0.8,0,0,0,0,0"

    def test_synthesize_clone_surfaces_worker_error(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.return_value = _stub_response(500, b"", {"detail": "infer failed: oom"})
        e._client = mock_client

        with pytest.raises(RuntimeError) as exc:
            e.synthesize_clone(text="t", reference_audio=b"ref")
        assert "500" in str(exc.value) and "infer failed" in str(exc.value)

    def test_synthesize_clone_connect_error_gives_actionable_hint(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("boom")
        e._client = mock_client

        with pytest.raises(RuntimeError) as exc:
            e.synthesize_clone(text="t", reference_audio=b"ref")
        assert "not reachable" in str(exc.value) and "make" in str(exc.value)

    def test_warmup_calls_health_then_load(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.get.return_value = _stub_response(200)
        mock_client.post.return_value = _stub_response(200)
        e._client = mock_client

        e.warmup()
        # GET /health then POST /load
        assert mock_client.get.called
        assert mock_client.post.called
        assert mock_client.post.call_args.args[0].endswith("/load")

    def test_warmup_raises_when_health_unreachable(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("boom")
        e._client = mock_client

        with pytest.raises(RuntimeError) as exc:
            e.warmup()
        assert "not reachable" in str(exc.value)

    def test_unload_is_best_effort(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("worker dead")
        e._client = mock_client

        e.unload()  # must not raise

    def test_available_models_empty_when_unhealthy(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("boom")
        e._client = mock_client

        assert e.available_models() == []

    def test_available_models_returns_entry_when_healthy(self):
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.get.return_value = _stub_response(200)
        e._client = mock_client

        models = e.available_models()
        assert len(models) == 1
        assert models[0].id == "IndexTeam/IndexTTS-2"
        assert models[0].supports_emotional_cloning is True


# ---------- Integration tests (need a live main adapter) ----------


class TestEmotionRejectionOnNonSupportingEngine:
    """When TTS_ENGINE=qwen3, emotion params must be rejected (400)."""

    def test_emotion_text_rejected_on_qwen3(self, live_client):
        health = live_client.get("/health").json()
        if health.get("supports_emotional_cloning"):
            pytest.skip("Engine supports emotional cloning - see TestEmotionalClone")
        if not health.get("supports_cloning"):
            pytest.skip("Cloning not supported by current model")

        wav = _minimal_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "language": "Russian", "emotion_text": "angry"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "emotional cloning" in response.json()["detail"].lower()


class TestEmotionalCloneValidation:
    """Validation paths - silent WAV is enough (no real generation needed)."""

    def _ensure_capable(self, live_client):
        health = live_client.get("/health").json()
        if not health.get("supports_emotional_cloning"):
            pytest.skip("Current engine does not support emotional cloning")

    def test_multiple_emotion_modes_rejected(self, live_client):
        self._ensure_capable(live_client)
        wav = _minimal_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "emotion_text": "angry", "emotion_vector": "0,0,0.8,0,0,0,0,0"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "only one emotion mode" in response.json()["detail"].lower()

    def test_alpha_out_of_range_rejected(self, live_client):
        self._ensure_capable(live_client)
        wav = _minimal_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "emotion_text": "angry", "emotion_alpha": "1.5"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "0.0 and 1.0" in response.json()["detail"]

    def test_vector_wrong_length_rejected(self, live_client):
        self._ensure_capable(live_client)
        wav = _minimal_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "emotion_vector": "1,2,3"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
        )
        assert response.status_code == 400
        assert "8 floats" in response.json()["detail"]


class TestEmotionalCloneHappyPath:
    """Real generation - requires a real reference WAV. Only expects 200,
    never accepts 400 as success (which would let broken generation pass).

    Skipped unless tests/fixtures/voice_3s.wav is present. Add the fixture
    once and these become live integration coverage on /tts/clone with
    emotion params.
    """

    def _real_wav(self):
        from pathlib import Path

        path = Path(__file__).parent / "fixtures" / "voice_3s.wav"
        if not path.exists():
            pytest.skip(f"Real reference WAV not found at {path}")
        return path.read_bytes()

    def _ensure_capable(self, live_client):
        health = live_client.get("/health").json()
        if not health.get("supports_emotional_cloning"):
            pytest.skip("Current engine does not support emotional cloning")

    def test_clone_with_emotion_text(self, live_client):
        self._ensure_capable(live_client)
        wav = self._real_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "emotion_text": "very excited", "emotion_alpha": "0.6"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
            timeout=180.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content[:4] == b"RIFF"

    def test_clone_with_emotion_vector(self, live_client):
        self._ensure_capable(live_client)
        wav = self._real_wav()
        response = live_client.post(
            "/tts/clone",
            data={"text": "test", "emotion_vector": "0,0,0.8,0,0,0,0,0", "emotion_alpha": "0.7"},
            files={"reference_audio": ("ref.wav", wav, "audio/wav")},
            timeout=180.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"


class TestHealthExposesEmotionalFlag:
    def test_health_contains_supports_emotional_cloning(self, live_client):
        response = live_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "supports_emotional_cloning" in data
        assert isinstance(data["supports_emotional_cloning"], bool)
