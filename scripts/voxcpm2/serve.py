#!/usr/bin/env python3
"""VoxCPM2 worker process - exposes /health + /load + /unload + /tts/clone over HTTP.

Runs in vendor/voxcpm/.venv (separate Python env from the main adapter, so
upstream's gradio>=6 / modelscope / funasr / datasets<4 pins don't clash with
qwen-tts and the main adapter).

The main adapter's VoxCPM2RemoteEngine talks to this worker. There is no
shared Python state - everything goes over HTTP multipart.

Run:
    cd vendor/voxcpm && uv run python ../../scripts/voxcpm2/serve.py

VoxCPM2 vs IndexTTS2 differences (read before editing):
  - emotion is an inline `(...)` text prefix in `text`, not a kwarg
  - reference audio is a path string only (no bytes/numpy overload upstream)
  - 48 kHz output sample rate (not 22050/24000)
  - load_denoiser=False prevents surprise ModelScope download of zipenhancer
  - `optimize=True` (default) runs torch.compile at constructor (~30s cold start)

Worker-side env vars (TTS_VOXCPM2_*):
    MODEL_DIR         Local checkpoint directory (default: vendor/voxcpm/checkpoints/VoxCPM2)
    OPTIMIZE          true|false (default true - torch.compile)
    LOAD_DENOISER     true|false (default false - avoids ModelScope dep)
    PORT              HTTP port (default 9882)

The worker comes up COLD - no model load on container start. The adapter's
warmup() POSTs /load when it switches to voxcpm2; first /tts/clone also
auto-loads if /load was never called.
"""

import io
import logging
import os
import sys
import threading
from contextlib import ExitStack
from pathlib import Path

# Make tts_adapter.audio_utils + gpu_utils importable from this worker's venv
# WITHOUT installing the whole adapter package (which would drag qwen-tts in).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("voxcpm2.worker")

# Load repo .env so worker-side TTS_VOXCPM2_* vars take effect. `uv run` does
# NOT auto-load .env. Soft-import: python-dotenv may not be in vendor venv yet.
try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(_REPO_ROOT / ".env")
except ImportError as e:
    log.debug("python-dotenv not installed; relying on os.environ only: %s", e)
except Exception as e:
    log.warning("dotenv load failed (continuing with os.environ): %s", e)

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import Response  # noqa: E402

from tts_adapter.audio_utils import bytes_to_tempfile  # noqa: E402
from tts_adapter.gpu_utils import unload_gpu_model  # noqa: E402


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


_DEFAULT_MODEL_DIR = str(_REPO_ROOT / "vendor" / "voxcpm" / "checkpoints" / "VoxCPM2")


def _resolve_model_dir(raw: str) -> str:
    """Resolve TTS_VOXCPM2_MODEL_DIR. Relative paths anchor at _REPO_ROOT, NOT
    process cwd - because `make run-voxcpm2` runs the worker after `cd vendor/voxcpm`,
    so a relative path from .env would otherwise mean `vendor/voxcpm/<that>`.
    """
    p = Path(raw)
    return str(p.resolve()) if p.is_absolute() else str((_REPO_ROOT / p).resolve())


MODEL_DIR = _resolve_model_dir(_env_str("TTS_VOXCPM2_MODEL_DIR", _DEFAULT_MODEL_DIR))
OPTIMIZE = _env_bool("TTS_VOXCPM2_OPTIMIZE", True)
LOAD_DENOISER = _env_bool("TTS_VOXCPM2_LOAD_DENOISER", False)
PORT = int(os.environ.get("TTS_VOXCPM2_PORT", "9882"))

# Symmetric with the main adapter's /tts/clone cap (20 MB per upload).
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_model = None
_sample_rate: int | None = None
_lock = threading.Lock()


def _load_model():
    """Construct VoxCPM with explicit local model_dir - no HF Hub calls."""
    global _model, _sample_rate
    if _model is not None:
        return

    if not Path(MODEL_DIR).exists():
        raise RuntimeError(
            f"VoxCPM2 checkpoint dir not found at {MODEL_DIR}. "
            f"Run `make install-voxcpm2` and verify TTS_VOXCPM2_MODEL_DIR."
        )

    log.info(
        "loading VoxCPM2 from %s (optimize=%s, denoiser=%s)",
        MODEL_DIR, OPTIMIZE, LOAD_DENOISER,
    )
    from voxcpm import VoxCPM
    # Pass local path as hf_model_id - constructor branches on os.path.isdir.
    _model = VoxCPM.from_pretrained(
        hf_model_id=MODEL_DIR,
        load_denoiser=LOAD_DENOISER,
        optimize=OPTIMIZE,
    )
    _sample_rate = int(_model.tts_model.sample_rate)
    log.info("VoxCPM2 loaded; sample_rate=%d Hz", _sample_rate)


def _unload_model():
    global _model, _sample_rate
    if _model is None:
        return
    log.info("unloading VoxCPM2")
    ref = _model
    _model = None
    _sample_rate = None
    unload_gpu_model(ref)


def _validate_upload_size(upload: UploadFile | None, field: str) -> None:
    if upload is None or upload.size is None:
        return
    if upload.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            413, f"{field} exceeds {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit"
        )


app = FastAPI(title="VoxCPM2 Worker", version="0.1.0")


@app.get("/health")
def health():
    return {
        "ok": True,
        "model_loaded": _model is not None,
        "model_dir": MODEL_DIR,
        "supports_emotional_cloning": True,
        "emotion_modes": ["text"],
        "sample_rate": _sample_rate,
    }


@app.post("/load")
def load():
    """Idempotent: no-op if model is already loaded."""
    with _lock:
        try:
            _load_model()
        except Exception as e:
            log.exception("load failed")
            raise HTTPException(500, f"load failed: {e}")
    return {"ok": True, "model_loaded": True}


@app.post("/unload")
def unload():
    """Idempotent: no-op if model is not loaded."""
    with _lock:
        _unload_model()
    return {"ok": True, "model_loaded": False}


@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(...),
    language: str = Form(default="Auto"),
    reference_text: str = Form(default=""),
    reference_audio: UploadFile = File(...),
    emotion_audio: UploadFile | None = File(default=None),
    emotion_text: str = Form(default=""),
    emotion_vector: str = Form(default=""),
    emotion_alpha: float = Form(default=1.0),
    cfg_value: float | None = Form(default=None),
    inference_timesteps: int | None = Form(default=None),
):
    """Clone voice from reference + optional inline-text emotion control.

    Defense-in-depth rejection of unsupported emotion modes - the API layer
    rejects these too, but the worker is exposed on its own port so it must
    enforce independently.
    """
    _validate_upload_size(reference_audio, "reference_audio")

    if emotion_audio is not None:
        raise HTTPException(
            400,
            'VoxCPM2 does not support emotion_audio. Use emotion_text or switch to indextts2.',
        )
    if emotion_vector:
        raise HTTPException(
            400,
            'VoxCPM2 does not support emotion_vector. Use emotion_text or switch to indextts2.',
        )
    # VoxCPM2 has no emo_alpha equivalent. Reject non-default values explicitly
    # rather than silently ignoring them (mirrors the main adapter's gate).
    if emotion_alpha != 1.0:
        raise HTTPException(
            400,
            'VoxCPM2 does not expose emotion_alpha. Omit it (default 1.0) or switch to indextts2.',
        )

    # `language` is informational only here - VoxCPM2's tokenizer is multilingual
    # and doesn't take a language hint at the API level. The main adapter already
    # validated that language is in supported_languages.
    del language, reference_text  # unused; signature kept for parity

    ref_bytes = await reference_audio.read()

    # Inline-text emotion: prepend "(style)" to the text.
    full_text = f"({emotion_text}){text}" if emotion_text else text

    gen_kwargs: dict = {}
    if cfg_value is not None:
        gen_kwargs["cfg_value"] = cfg_value
    if inference_timesteps is not None:
        gen_kwargs["inference_timesteps"] = inference_timesteps

    with ExitStack() as stack:
        ref_path = stack.enter_context(bytes_to_tempfile(ref_bytes, suffix=".wav"))

        with _lock:
            try:
                _load_model()
                if _model is None:
                    raise HTTPException(500, "model failed to load")
                wav = _model.generate(
                    text=full_text,
                    reference_wav_path=ref_path,
                    **gen_kwargs,
                )
            except HTTPException:
                raise
            except Exception as e:
                log.exception("infer failed")
                raise HTTPException(500, f"infer failed: {e}")

    buf = io.BytesIO()
    sf.write(buf, np.asarray(wav, dtype=np.float32), _sample_rate, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, workers=1)
