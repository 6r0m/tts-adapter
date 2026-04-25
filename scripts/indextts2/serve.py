#!/usr/bin/env python3
"""IndexTTS2 worker process - exposes /health + /load + /unload + /tts/clone over HTTP.

Runs in vendor/index-tts/.venv (separate Python env from the main adapter, so
upstream's transformers==4.52.1 / torch==2.8.* / deepspeed pins don't clash with
qwen-tts's transformers==4.57.3).

The main adapter's IndexTTS2RemoteEngine talks to this worker. There is no
shared Python state - everything goes over HTTP multipart.

Run:
    cd vendor/index-tts && uv run python ../../scripts/indextts2/serve.py

Required deps in the vendor venv (install once):
    uv pip install fastapi uvicorn 'python-multipart' soundfile
    # indextts itself + torch + transformers + ... come from `uv sync` in vendor/index-tts/

Worker-side env vars (TTS_INDEXTTS2_*):
    MODEL_DIR         Local checkpoint directory (default: ~/.cache/tts-adapter/models/IndexTTS-2)
    CFG_PATH          Path to config.yaml (default: {MODEL_DIR}/config.yaml)
    USE_FP16          true|false (default true)
    USE_CUDA_KERNEL   true|false (default false)
    USE_DEEPSPEED     true|false (default false)
    USE_RANDOM        true|false (default false - random sampling reduces clone fidelity)
    TRIM_SILENCE      true|false (default false - keeps emotional pauses)
    PORT              HTTP port (default 9881)

The worker comes up COLD - no model load on container start. The adapter's
warmup() POSTs /load when it switches to indextts2; first /tts/clone also
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
# These two modules have zero internal tts_adapter deps - safe to cross-venv.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import soundfile as sf  # noqa: E402
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

from tts_adapter.audio_utils import bytes_to_tempfile, trim_silence  # noqa: E402
from tts_adapter.gpu_utils import unload_gpu_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("indextts2.worker")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


_DEFAULT_MODEL_DIR = str(Path.home() / ".cache" / "tts-adapter" / "models" / "IndexTTS-2")
MODEL_DIR = _env_str("TTS_INDEXTTS2_MODEL_DIR", _DEFAULT_MODEL_DIR)
CFG_PATH = _env_str("TTS_INDEXTTS2_CFG_PATH", str(Path(MODEL_DIR) / "config.yaml"))
USE_FP16 = _env_bool("TTS_INDEXTTS2_USE_FP16", True)
USE_CUDA_KERNEL = _env_bool("TTS_INDEXTTS2_USE_CUDA_KERNEL", False)
USE_DEEPSPEED = _env_bool("TTS_INDEXTTS2_USE_DEEPSPEED", False)
USE_RANDOM = _env_bool("TTS_INDEXTTS2_USE_RANDOM", False)
TRIM_SILENCE = _env_bool("TTS_INDEXTTS2_TRIM_SILENCE", False)
PORT = int(os.environ.get("TTS_INDEXTTS2_PORT", "9881"))

_model = None
_lock = threading.Lock()  # serializes load/unload/inference


def _load_model():
    """Construct IndexTTS2 with explicit local paths - no HF Hub calls."""
    global _model
    if _model is not None:
        return

    if not Path(CFG_PATH).exists():
        raise RuntimeError(
            f"IndexTTS2 config not found at {CFG_PATH}. "
            f"Run `make install-indextts2` (Phase B) and verify TTS_INDEXTTS2_MODEL_DIR."
        )

    log.info("loading IndexTTS2 from %s (fp16=%s, cuda_kernel=%s, deepspeed=%s)",
             MODEL_DIR, USE_FP16, USE_CUDA_KERNEL, USE_DEEPSPEED)
    from indextts.infer_v2 import IndexTTS2
    _model = IndexTTS2(
        cfg_path=CFG_PATH,
        model_dir=MODEL_DIR,
        use_fp16=USE_FP16,
        use_cuda_kernel=USE_CUDA_KERNEL,
        use_deepspeed=USE_DEEPSPEED,
    )
    log.info("IndexTTS2 loaded")


def _unload_model():
    global _model
    if _model is None:
        return
    log.info("unloading IndexTTS2")
    ref = _model
    _model = None
    unload_gpu_model(ref)


def _parse_emotion_vector(raw: str) -> list[float] | None:
    """Mirror the main adapter's parser - 8 floats or 400."""
    if not raw:
        return None
    try:
        vec = [float(x) for x in raw.split(",")]
    except ValueError:
        raise HTTPException(400, "emotion_vector must be comma-separated floats")
    if len(vec) != 8:
        raise HTTPException(
            400,
            "emotion_vector must have exactly 8 floats: "
            "[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]",
        )
    return vec


app = FastAPI(title="IndexTTS2 Worker", version="0.1.0")


@app.get("/health")
def health():
    return {
        "ok": True,
        "model_loaded": _model is not None,
        "model_dir": MODEL_DIR,
        "supports_emotional_cloning": True,
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
    temperature: float | None = Form(default=None),
    top_k: int | None = Form(default=None),
    top_p: float | None = Form(default=None),
    repetition_penalty: float | None = Form(default=None),
    max_new_tokens: int | None = Form(default=None),
):
    if not 0.0 <= emotion_alpha <= 1.0:
        raise HTTPException(400, "emotion_alpha must be between 0.0 and 1.0")

    modes = sum([emotion_audio is not None, bool(emotion_text), bool(emotion_vector)])
    if modes > 1:
        raise HTTPException(
            400, "Use only one emotion mode: emotion_audio, emotion_text, OR emotion_vector"
        )

    vec = _parse_emotion_vector(emotion_vector)

    # Lazy load on first /tts/clone if /load wasn't called explicitly.
    if _model is None:
        with _lock:
            try:
                _load_model()
            except Exception as e:
                log.exception("lazy load failed")
                raise HTTPException(500, f"lazy load failed: {e}")

    ref_bytes = await reference_audio.read()
    emo_bytes = await emotion_audio.read() if emotion_audio is not None else None

    # Generation kwargs IndexTTS2 actually accepts. Pass through everything that's set.
    gen_kwargs = {
        k: v
        for k, v in {
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "max_new_tokens": max_new_tokens,
        }.items()
        if v is not None
    }

    with ExitStack() as stack:
        spk_path = stack.enter_context(bytes_to_tempfile(ref_bytes, suffix=".wav"))
        emo_path = stack.enter_context(bytes_to_tempfile(emo_bytes, suffix=".wav")) if emo_bytes else None

        out_fd, out_path = _mkstemp_wav()
        os.close(out_fd)
        stack.callback(_silent_unlink, out_path)

        with _lock:
            try:
                _model.infer(
                    spk_audio_prompt=spk_path,
                    text=text,
                    output_path=out_path,
                    emo_audio_prompt=emo_path,
                    emo_text=emotion_text or None,
                    use_emo_text=bool(emotion_text),
                    emo_vector=vec,
                    emo_alpha=emotion_alpha,
                    use_random=USE_RANDOM,
                    **gen_kwargs,
                )
            except Exception as e:
                log.exception("infer failed")
                raise HTTPException(500, f"infer failed: {e}")

        wav, sr = sf.read(out_path)

    if TRIM_SILENCE:
        wav = trim_silence(wav, sr)

    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


def _mkstemp_wav():
    import tempfile
    return tempfile.mkstemp(suffix=".wav")


def _silent_unlink(path: str):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, workers=1)
