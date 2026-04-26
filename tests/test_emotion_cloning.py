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

    def test_catalog_models_independent_of_health(self):
        """catalog_models() must return the IndexTTS-2 entry even when the
        worker is dead. That's what lets /model/switch route the request
        and surface 503 from warmup() instead of 400 unknown.
        """
        e = IndexTTS2RemoteEngine()
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("worker dead")
        e._client = mock_client

        # available is empty (worker unreachable)...
        assert e.available_models() == []
        # ...but catalog still has the entry (so switch can route to it)
        catalog = e.catalog_models()
        assert len(catalog) == 1
        assert catalog[0].id == "IndexTeam/IndexTTS-2"


class TestQwen3CatalogParity:
    def test_qwen3_catalog_equals_available(self):
        """Qwen3 is in-process - no separate availability concern, so the
        two methods return the same list."""
        from tts_adapter.engines.qwen3 import Qwen3Engine

        e = Qwen3Engine()
        catalog = e.catalog_models()
        available = e.available_models()
        assert [m.id for m in catalog] == [m.id for m in available]
        assert len(catalog) == 4


class TestSupportedLanguages:
    """Engine supported_languages property + API gating + Cyrillic guard.

    Mirrors the existing _validate_upload_size + emotion-mode rejection
    pattern: pure validators, raise HTTPException(400) with actionable
    detail.
    """

    def test_qwen3_includes_russian_and_auto(self):
        from tts_adapter.engines.qwen3 import Qwen3Engine

        langs = Qwen3Engine().supported_languages
        assert "Russian" in langs
        assert "Auto" in langs
        assert "Chinese" in langs
        assert len(langs) == 11  # Auto + 10 official langs

    def test_indextts2_excludes_russian_and_auto(self):
        """No 'Auto' for IndexTTS2 - upstream's auto-detect routes Russian
        through Chinese normalizer. Hard-gate at API instead."""
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        langs = IndexTTS2RemoteEngine().supported_languages
        assert langs == ["Chinese", "English", "Japanese"]
        assert "Russian" not in langs
        assert "Auto" not in langs

    def test_health_exposes_supported_languages(self):
        """HealthResponse contract carries supported_languages."""
        from tts_adapter.contract import HealthResponse

        r = HealthResponse(
            ok=True, engine="qwen3", model="x", device="cpu",
            supported_languages=["Auto", "Chinese", "English"],
        )
        assert r.supported_languages == ["Auto", "Chinese", "English"]

    def test_modelinfo_carries_supported_languages(self):
        """Each engine's catalog/available models carry the supported list,
        so /models clients can introspect per-model (not just per-engine)."""
        from tts_adapter.engines.qwen3 import Qwen3Engine
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        for m in Qwen3Engine().catalog_models():
            assert "Russian" in m.supported_languages
        for m in IndexTTS2RemoteEngine().catalog_models():
            assert "Russian" not in m.supported_languages
            assert "Auto" not in m.supported_languages


class TestValidateLanguage:
    """Cyrillic + supported-languages gating in routes.py."""

    def test_looks_cyrillic(self):
        from tts_adapter.api.routes import _looks_cyrillic

        assert _looks_cyrillic("Привет") is True
        assert _looks_cyrillic("Hello") is False
        assert _looks_cyrillic("") is False
        # Mixed: any Cyrillic anywhere counts
        assert _looks_cyrillic("Hello Привет!") is True
        # Non-Latin non-Cyrillic (Chinese) is NOT Cyrillic
        assert _looks_cyrillic("你好") is False

    def test_qwen3_russian_passes(self):
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.qwen3 import Qwen3Engine

        # Should not raise
        _validate_language(Qwen3Engine(), "Russian", text="Привет мир")
        _validate_language(Qwen3Engine(), "Auto", text="Hello")

    def test_indextts2_russian_rejected_400(self):
        from fastapi import HTTPException
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        with pytest.raises(HTTPException) as exc:
            _validate_language(IndexTTS2RemoteEngine(), "Russian", text="hi")
        assert exc.value.status_code == 400
        assert "not supported" in exc.value.detail
        assert "qwen3" in exc.value.detail
        assert "indextts2" in exc.value.detail

    def test_indextts2_auto_rejected_400(self):
        """'Auto' is deliberately removed from IndexTTS2 - if it were allowed,
        Russian text with language=Auto would still produce garbage."""
        from fastapi import HTTPException
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        with pytest.raises(HTTPException) as exc:
            _validate_language(IndexTTS2RemoteEngine(), "Auto", text="hello")
        assert exc.value.status_code == 400

    def test_indextts2_english_with_english_text_passes(self):
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        _validate_language(IndexTTS2RemoteEngine(), "English", text="Hello world")
        _validate_language(IndexTTS2RemoteEngine(), "Chinese", text="你好世界")

    def test_indextts2_english_with_cyrillic_text_rejected_400(self):
        """The bypass: API-savvy user sends language=English + text=Russian.
        Cyrillic regex catches it before upstream mangles."""
        from fastapi import HTTPException
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        with pytest.raises(HTTPException) as exc:
            _validate_language(IndexTTS2RemoteEngine(), "English", text="Привет мир")
        assert exc.value.status_code == 400
        assert "Cyrillic" in exc.value.detail or "Russian" in exc.value.detail
        assert "qwen3" in exc.value.detail

    def test_validate_with_no_text_skips_cyrillic_check(self):
        """Used internally by /tts/batch's first-item language check."""
        from tts_adapter.api.routes import _validate_language
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        # No text -> only language-name check runs
        _validate_language(IndexTTS2RemoteEngine(), "English", text=None)


class TestRoutesIndex:
    """_catalog_index must include IndexTTS2 even when the worker is down,
    so /model/switch can route to it for the 503 path.
    """

    def test_catalog_index_includes_indextts2_when_worker_down(self, monkeypatch):
        # Force IndexTTS2RemoteEngine.available_models() to return [] (worker
        # unhealthy). catalog_models() should still expose the entry, and
        # _catalog_index() should pick it up.
        from tts_adapter.api import routes
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine

        monkeypatch.setattr(IndexTTS2RemoteEngine, "available_models", lambda self: [])

        idx = routes._catalog_index()
        assert "IndexTeam/IndexTTS-2" in idx
        assert idx["IndexTeam/IndexTTS-2"] == "indextts2"


class TestCrossEngineSwitchRollback:
    """Failed warmup on a cross-engine swap must roll back _engine AND
    attempt to re-warm the previous engine (so it isn't left cold)."""

    def _setup_qwen3_current(self, monkeypatch):
        from tts_adapter.api import routes
        from tts_adapter.engines.qwen3 import Qwen3Engine

        fake_current = Qwen3Engine()
        fake_current._model = None  # don't trigger real GPU unload
        monkeypatch.setattr(routes, "_engine", fake_current)
        return fake_current

    def test_failed_switch_rolls_back_and_attempts_restore(self, monkeypatch):
        from tts_adapter.api import routes
        from tts_adapter.contract import SwitchModelRequest
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine
        from tts_adapter.engines.qwen3 import Qwen3Engine
        from fastapi import HTTPException

        fake_current = self._setup_qwen3_current(monkeypatch)

        # Target's warmup raises (worker dead).
        monkeypatch.setattr(
            IndexTTS2RemoteEngine,
            "warmup",
            lambda self: (_ for _ in ()).throw(
                RuntimeError("IndexTTS2 worker not reachable at http://localhost:9881")
            ),
        )

        # Track whether current.warmup was called for restore.
        restore_calls = []
        monkeypatch.setattr(
            Qwen3Engine, "warmup", lambda self: restore_calls.append(True)
        )

        with pytest.raises(HTTPException) as exc:
            routes.switch_model(SwitchModelRequest(model_id="IndexTeam/IndexTTS-2"))

        assert exc.value.status_code == 503
        assert "not reachable" in exc.value.detail
        assert "rolled back" in exc.value.detail.lower()
        assert "previous engine restored" in exc.value.detail.lower()
        # Critical: _engine must be back to the previous reference.
        assert routes._engine is fake_current
        # Restore was attempted.
        assert len(restore_calls) == 1

    def test_rollback_when_restore_also_fails(self, monkeypatch):
        """Restore is best-effort - if it also fails, the response message
        must say so (not falsely claim restoration)."""
        from tts_adapter.api import routes
        from tts_adapter.contract import SwitchModelRequest
        from tts_adapter.engines.indextts2 import IndexTTS2RemoteEngine
        from tts_adapter.engines.qwen3 import Qwen3Engine
        from fastapi import HTTPException

        fake_current = self._setup_qwen3_current(monkeypatch)

        monkeypatch.setattr(
            IndexTTS2RemoteEngine,
            "warmup",
            lambda self: (_ for _ in ()).throw(RuntimeError("worker dead")),
        )

        def _restore_boom(self):
            raise RuntimeError("OOM during restore")

        monkeypatch.setattr(Qwen3Engine, "warmup", _restore_boom)

        with pytest.raises(HTTPException) as exc:
            routes.switch_model(SwitchModelRequest(model_id="IndexTeam/IndexTTS-2"))

        assert exc.value.status_code == 503
        assert "rolled back" in exc.value.detail.lower()
        assert "restore attempt failed" in exc.value.detail.lower()
        assert "lazy-reload" in exc.value.detail.lower()
        assert "generation request" in exc.value.detail.lower()
        # _engine must still be the previous reference even when restore fails.
        assert routes._engine is fake_current


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
