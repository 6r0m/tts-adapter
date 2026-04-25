"""FastAPI routes for TTS adapter."""

import io
import logging
import os
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import get_settings
from ..contract import (
    HealthResponse,
    ModelsResponse,
    SwitchModelRequest,
    SwitchModelResponse,
    TTSBatchRequest,
    TTSRequest,
)
from ..engine import TTSEngine
from ..engines import _ENGINES, create_engine
from ..gpu_utils import unload_gpu_model
from ..web import router as web_router

log = logging.getLogger(__name__)

# Per-upload size cap (DoS protection on /tts/clone).
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

# Legacy model-cache path. Accepted as a fallback for one minor release,
# warned once at startup. See todo/engine_install_and_switch.md policy table.
_LEGACY_CACHE_DIR = Path.home() / ".cache" / "tts-adapter"

# Global engine instance
_engine: TTSEngine | None = None


def get_engine() -> TTSEngine:
    """Get or create engine instance."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def _warn_if_legacy_cache_path() -> None:
    """Emit ONE warning per startup if any engine's configured path lives under
    the legacy ~/.cache/tts-adapter/ tree. Never per-request.

    Removal target: next minor release.
    """
    legacy = str(_LEGACY_CACHE_DIR.expanduser().resolve())
    candidates = {
        "TTS_QWEN3_MODEL_PATH": os.environ.get("TTS_QWEN3_MODEL_PATH", ""),
        "TTS_INDEXTTS2_MODEL_DIR": os.environ.get("TTS_INDEXTTS2_MODEL_DIR", ""),
    }
    for var, raw in candidates.items():
        if not raw:
            continue
        try:
            resolved = str(Path(raw).expanduser().resolve())
        except OSError:
            continue
        if resolved.startswith(legacy):
            log.warning(
                "Using legacy model cache path under ~/.cache/tts-adapter via %s. "
                "Set %s to a repo-local ./models/<engine>/<name>/ path explicitly. "
                "This fallback will be removed in the next minor release.",
                var,
                var,
            )
            return  # one warning is enough


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warmup model on startup."""
    _warn_if_legacy_cache_path()
    engine = get_engine()
    engine.warmup()
    yield


app = FastAPI(
    title="TTS Adapter",
    description="Universal text-to-speech adapter with pluggable engines",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount web UI
app.include_router(web_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check with model info."""
    engine = get_engine()
    return HealthResponse(
        ok=True,
        engine=engine.engine_name,
        model=engine.model_id,
        device=engine.device,
        supports_cloning=engine.supports_cloning,
        supports_design=engine.supports_design,
        supports_custom_voice=engine.supports_custom_voice,
        supports_emotional_cloning=engine.supports_emotional_cloning,
    )


def _models_index() -> dict[str, str]:
    """Map model_id -> engine_name across ALL registered engines.

    Engines whose backend isn't available right now (e.g. IndexTTS2 worker
    is down) return [] from available_models(), so they're naturally
    excluded from the index without route-level engine-name branching.
    """
    return {m.id: name for name, cls in _ENGINES.items() for m in cls().available_models()}


def _switch_response(engine: TTSEngine, message: str) -> SwitchModelResponse:
    return SwitchModelResponse(
        success=True,
        model=engine.model_id,
        message=message,
        supports_cloning=engine.supports_cloning,
        supports_design=engine.supports_design,
        supports_custom_voice=engine.supports_custom_voice,
        supports_emotional_cloning=engine.supports_emotional_cloning,
    )


@app.get("/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    """List models from ALL registered engines whose backend is reachable.

    For Qwen3 this is its 4 variants; for IndexTTS2 it's the single
    IndexTTS-2 entry IF the worker is up (otherwise it's filtered out).
    """
    engine = get_engine()
    available = [m for cls in _ENGINES.values() for m in cls().available_models()]
    return ModelsResponse(current=engine.model_id, available=available)


@app.post("/model/switch", response_model=SwitchModelResponse)
def switch_model(req: SwitchModelRequest) -> SwitchModelResponse:
    """Switch to a different model.

    Same "unload current, load new" pattern as the previous Qwen3-only
    variant switch, just extended to work across engines:

    - Same engine + different model -> existing engine.reload(new_id) path.
    - Different engine -> unload current (in-process gpu_utils for Qwen3,
      worker /unload for IndexTTS2RemoteEngine), then construct + warmup
      the target engine.

    Server is briefly unavailable during reload (~30-120 s).
    Cross-engine switch to indextts2 returns 503 if the worker is down.
    """
    global _engine

    idx = _models_index()
    if req.model_id not in idx:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model ID. Available now: {', '.join(sorted(idx))}",
        )
    target_engine_name = idx[req.model_id]
    current = get_engine()

    # No-op fast path
    if current.engine_name == target_engine_name and current.model_id == req.model_id:
        return _switch_response(current, "Model already loaded")

    if current.engine_name == target_engine_name:
        # Same-engine variant switch (existing Qwen3 path).
        try:
            current.reload(req.model_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to switch model: {e}")
        return _switch_response(current, f"Switched to {req.model_id}")

    # Cross-engine swap.
    # Step 1: unload current. Strict VRAM rule - only ONE model loaded at a time.
    try:
        unload_method = getattr(current, "unload", None)
        if callable(unload_method):
            # Remote engines (IndexTTS2RemoteEngine) hand off to the worker.
            unload_method()
        elif hasattr(current, "_model") and getattr(current, "_model") is not None:
            # In-process engines (Qwen3) release VRAM directly.
            model_ref = current._model
            current._model = None
            unload_gpu_model(model_ref)
    except Exception as e:
        log.warning("unload of current engine %s failed (continuing): %s", current.engine_name, e)

    # Step 2: load new. For remote engine, warmup() does /health + /load.
    os.environ["TTS_ENGINE"] = target_engine_name
    get_settings.cache_clear()
    try:
        _engine = _ENGINES[target_engine_name]()
        _engine.warmup()
    except RuntimeError as e:
        # IndexTTS2RemoteEngine raises this when the worker is unreachable.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load {target_engine_name}: {e}")

    return _switch_response(_engine, f"Switched to {target_engine_name}: {req.model_id}")


@app.post("/tts")
def tts(req: TTSRequest) -> Response:
    """Generate WAV audio from text."""
    engine = get_engine()
    wav_bytes = engine.synthesize(
        text=req.text,
        language=req.language,
        speaker=req.speaker,
        instruct=req.instruct,
        **req.generation.to_kwargs(),
    )
    return Response(content=wav_bytes, media_type="audio/wav")


def _sanitize_id(item_id: str) -> str:
    """Sanitize item ID for safe filename (prevent zip slip)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", item_id)


@app.post("/tts/batch")
def tts_batch(req: TTSBatchRequest) -> Response:
    """Generate multiple WAV files as ZIP.

    All items must share the same language/speaker/instruct params.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="items must be non-empty")

    engine = get_engine()

    first = req.items[0]
    for item in req.items[1:]:
        if (item.language, item.speaker, item.instruct) != (
            first.language,
            first.speaker,
            first.instruct,
        ):
            raise HTTPException(
                status_code=400,
                detail="all items must share language/speaker/instruct (batch params are global)",
            )

    texts = [item.text for item in req.items]
    ids = [_sanitize_id(item.id) for item in req.items]

    wav_bytes_list = engine.synthesize_batch(
        texts=texts,
        language=first.language,
        speaker=first.speaker,
        instruct=first.instruct,
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_id, wav_bytes in zip(ids, wav_bytes_list):
            zf.writestr(f"{item_id}.wav", wav_bytes)

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tts_batch.zip"},
    )


def _collect_gen_kwargs(
    temperature: float | None,
    top_k: int | None,
    top_p: float | None,
    repetition_penalty: float | None,
    max_new_tokens: int | None,
) -> dict:
    """Collect non-None generation kwargs from Form params."""
    return {
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


def _validate_upload_size(upload: UploadFile | None, field: str) -> None:
    """Reject uploads larger than _MAX_UPLOAD_BYTES (DoS protection)."""
    if upload is None or upload.size is None:
        return
    if upload.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{field} exceeds {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )


def _parse_emotion_vector(raw: str) -> list[float] | None:
    """Parse 'h,a,s,af,d,m,su,c' string -> list[float] of length 8.

    Returns None for empty input. Raises HTTPException(400) on bad format.
    """
    if not raw:
        return None
    try:
        vec = [float(x) for x in raw.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="emotion_vector must be comma-separated floats")
    if len(vec) != 8:
        raise HTTPException(
            status_code=400,
            detail="emotion_vector must have exactly 8 floats: "
            "[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]",
        )
    return vec


@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(..., description="Text to synthesize"),
    language: str = Form(default="Auto", description="Language code"),
    reference_text: str = Form(default="", description="Transcript of reference audio (improves quality)"),
    reference_audio: UploadFile = File(..., description="Reference audio WAV (3-10 sec)"),
    emotion_audio: UploadFile | None = File(default=None, description="Emotion reference WAV (IndexTTS2 only)"),
    emotion_text: str = Form(default="", description="Free-form emotion description (IndexTTS2 only)"),
    emotion_vector: str = Form(default="", description="8 comma-sep floats: [happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]"),
    emotion_alpha: float = Form(default=1.0, description="Emotion blend strength in [0.0, 1.0]"),
    temperature: float | None = Form(default=None, ge=0.01, le=2.0),
    top_k: int | None = Form(default=None, ge=1, le=200),
    top_p: float | None = Form(default=None, ge=0.1, le=1.0),
    repetition_penalty: float | None = Form(default=None, ge=1.0, le=2.0),
    max_new_tokens: int | None = Form(default=None, ge=256, le=4096),
) -> Response:
    """Generate speech by cloning voice from reference audio.

    Requires a model that supports voice cloning. Optional emotion params
    (audio / text / 8-dim vector) require an engine with
    supports_emotional_cloning=True (e.g. IndexTTS2). Use exactly one
    emotion mode per request.
    """
    engine = get_engine()

    if not engine.supports_cloning:
        raise HTTPException(
            status_code=400,
            detail="Voice cloning not supported by current model configuration",
        )

    _validate_upload_size(reference_audio, "reference_audio")
    _validate_upload_size(emotion_audio, "emotion_audio")

    has_emotion = (emotion_audio is not None) or bool(emotion_text) or bool(emotion_vector)
    if has_emotion and not engine.supports_emotional_cloning:
        raise HTTPException(
            status_code=400,
            detail="Current engine does not support emotional cloning. "
            "Switch to TTS_ENGINE=indextts2.",
        )

    modes = sum([emotion_audio is not None, bool(emotion_text), bool(emotion_vector)])
    if modes > 1:
        raise HTTPException(
            status_code=400,
            detail="Use only one emotion mode: emotion_audio, emotion_text, OR emotion_vector",
        )

    if not 0.0 <= emotion_alpha <= 1.0:
        raise HTTPException(status_code=400, detail="emotion_alpha must be between 0.0 and 1.0")

    vec = _parse_emotion_vector(emotion_vector)

    audio_bytes = await reference_audio.read()
    emotion_audio_bytes = await emotion_audio.read() if emotion_audio is not None else None

    gen_kwargs = _collect_gen_kwargs(temperature, top_k, top_p, repetition_penalty, max_new_tokens)
    wav_bytes = engine.synthesize_clone(
        text=text,
        reference_audio=audio_bytes,
        language=language,
        reference_text=reference_text if reference_text else None,
        emotion_audio=emotion_audio_bytes,
        emotion_text=emotion_text or None,
        emotion_vector=vec,
        emotion_alpha=emotion_alpha,
        **gen_kwargs,
    )
    return Response(content=wav_bytes, media_type="audio/wav")


@app.post("/tts/design")
def tts_design(
    text: str = Form(..., description="Text to synthesize"),
    instruct: str = Form(..., description="Natural language description of the voice"),
    language: str = Form(default="Auto", description="Language code"),
    temperature: float | None = Form(default=None, ge=0.01, le=2.0),
    top_k: int | None = Form(default=None, ge=1, le=200),
    top_p: float | None = Form(default=None, ge=0.1, le=1.0),
    repetition_penalty: float | None = Form(default=None, ge=1.0, le=2.0),
    max_new_tokens: int | None = Form(default=None, ge=256, le=4096),
) -> Response:
    """Generate speech with a designed voice from natural language description.

    Requires a model that supports voice design (e.g., VoiceDesign model).
    """
    engine = get_engine()

    if not engine.supports_design:
        raise HTTPException(
            status_code=400,
            detail="Voice design not supported by current model configuration",
        )

    gen_kwargs = _collect_gen_kwargs(temperature, top_k, top_p, repetition_penalty, max_new_tokens)
    wav_bytes = engine.synthesize_design(
        text=text,
        instruct=instruct,
        language=language,
        **gen_kwargs,
    )
    return Response(content=wav_bytes, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)
