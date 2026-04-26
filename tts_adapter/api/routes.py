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
    EngineInfo,
    EnginesResponse,
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


def _legacy_cache_env_vars() -> dict[str, str]:
    """Build the per-engine legacy-path env-var mapping dynamically.

    Each engine that uses a local model path follows the convention
    `TTS_<NAME>_MODEL_PATH` (qwen3) or `TTS_<NAME>_MODEL_DIR` (worker
    engines). We probe both per registered engine so adding a new engine
    doesn't require editing this function.
    """
    out: dict[str, str] = {}
    for name in _ENGINES.keys():
        prefix = f"TTS_{name.upper()}_"
        for suffix in ("MODEL_PATH", "MODEL_DIR"):
            var = prefix + suffix
            val = os.environ.get(var, "")
            if val:
                out[var] = val
    return out


def _warn_if_legacy_cache_path() -> None:
    """Emit ONE warning per startup if any engine's configured path lives under
    the legacy ~/.cache/tts-adapter/ tree. Never per-request.

    Removal target: next minor release.
    """
    legacy = str(_LEGACY_CACHE_DIR.expanduser().resolve())
    candidates = _legacy_cache_env_vars()
    for var, raw in candidates.items():
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
        emotion_modes=sorted(engine.emotion_modes),
        supports_emotion_strength=engine.supports_emotion_strength,
        supports_cyrillic_text=engine.supports_cyrillic_text,
        supported_languages=engine.supported_languages,
        generation_params=engine.generation_params,
    )


def _engine_info(name: str, engine_cls: type, *, active_name: str) -> EngineInfo:
    """Build an EngineInfo without warming up the engine.

    Constructs a lightweight instance just to query capability properties.
    Capability props don't touch GPU/network. is_installed is a classmethod
    (cheap filesystem stat). is_reachable pings the worker with a SHORT
    timeout (~500 ms) - the UI polls /engines every 3 s, so two unreachable
    workers must NOT add 4+ s of latency to every poll.

    is_loaded reads the worker's actual /health.model_loaded even when the
    engine isn't currently active - a worker can be loaded independently
    of which engine the main adapter has selected.
    """
    is_active = name == active_name
    instance = get_engine() if is_active else engine_cls()
    # Short timeout for /engines specifically: this endpoint is polled by the UI
    # so we can't pay the long generation timeout per inactive engine.
    short_health_timeout = 0.5
    if hasattr(instance, "_health_timeout"):
        try:
            instance._health_timeout = short_health_timeout  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        installed = engine_cls.is_installed()
    except Exception:
        installed = False
    try:
        reachable = instance.is_reachable()
    except Exception:
        reachable = False
    try:
        loaded = bool(instance.is_loaded)
    except Exception:
        loaded = False
    return EngineInfo(
        name=name,
        installed=installed,
        reachable=reachable,
        loaded=loaded,
        active=is_active,
        supports_cloning=instance.supports_cloning,
        supports_design=instance.supports_design,
        supports_custom_voice=instance.supports_custom_voice,
        supports_emotional_cloning=instance.supports_emotional_cloning,
        emotion_modes=sorted(instance.emotion_modes),
        supports_emotion_strength=instance.supports_emotion_strength,
        supports_cyrillic_text=instance.supports_cyrillic_text,
        supported_languages=instance.supported_languages,
    )


@app.get("/engines", response_model=EnginesResponse)
def list_engines() -> EnginesResponse:
    """List all registered engines + their installation/reachability/capability state.

    Drives the UI engine dropdown (only show installed AND reachable engines)
    and lets clients route around uninstalled engines without having to know
    their names a priori.
    """
    active = get_engine().engine_name
    engines = [_engine_info(name, cls, active_name=active) for name, cls in _ENGINES.items()]
    return EnginesResponse(active=active, engines=engines)


def _catalog_index() -> dict[str, str]:
    """Map model_id -> engine_name across ALL registered engines, using each
    engine's STATIC catalog (catalog_models()).

    Includes models whose backend is currently unreachable - that's what
    lets /model/switch route to a known engine and surface 503 from
    warmup() rather than rejecting as 400.
    """
    return {m.id: name for name, cls in _ENGINES.items() for m in cls().catalog_models()}


def _unload_engine(engine: TTSEngine) -> None:
    """Best-effort unload of either remote (worker /unload) or in-process (gpu_utils) engine."""
    try:
        unload_method = getattr(engine, "unload", None)
        if callable(unload_method):
            unload_method()
        elif hasattr(engine, "_model") and getattr(engine, "_model") is not None:
            model_ref = engine._model
            engine._model = None
            unload_gpu_model(model_ref)
    except Exception as e:
        log.warning("unload of engine %s failed (continuing): %s", engine.engine_name, e)


def _try_restore(engine: TTSEngine) -> str:
    """Best-effort re-warm of an engine after a failed cross-engine swap.

    Returns a short status string for the rollback message so the operator
    knows whether the previous engine is hot, cold, or in an unknown state.
    """
    try:
        engine.warmup()
        return "previous engine restored"
    except Exception as restore_err:
        log.warning("failed to restore engine %s: %s", engine.engine_name, restore_err)
        return f"restore attempt failed ({restore_err}); next generation request may lazy-reload"


def _switch_response(engine: TTSEngine, message: str) -> SwitchModelResponse:
    return SwitchModelResponse(
        success=True,
        model=engine.model_id,
        message=message,
        supports_cloning=engine.supports_cloning,
        supports_design=engine.supports_design,
        supports_custom_voice=engine.supports_custom_voice,
        supports_emotional_cloning=engine.supports_emotional_cloning,
        emotion_modes=sorted(engine.emotion_modes),
        supports_emotion_strength=engine.supports_emotion_strength,
        supports_cyrillic_text=engine.supports_cyrillic_text,
        supported_languages=engine.supported_languages,
    )


def _suggest_emotional_engine(
    *, exclude: str | None = None, requires_mode: str | None = None,
    requires_strength: bool = False, language: str | None = None,
    text: str | None = None,
) -> str | None:
    """Find the first installed engine that supports emotional cloning AND
    can actually handle the user's language/text - so we don't suggest
    IndexTTS2 for Russian (it can't), or any non-cyrillic-text engine for
    a Cyrillic body.

    Returns None when nothing fits. Caller renders no hint in that case
    (better than a wrong hint).
    """
    for name, cls in _ENGINES.items():
        if exclude and name == exclude:
            continue
        try:
            if not cls.is_installed():
                continue
            instance = cls()
            if not instance.supports_emotional_cloning:
                continue
            if requires_mode and requires_mode not in instance.emotion_modes:
                continue
            if requires_strength and not instance.supports_emotion_strength:
                continue
            if language and instance.supported_languages and language not in instance.supported_languages:
                continue
            if text and _looks_cyrillic(text) and not instance.supports_cyrillic_text:
                continue
            return name
        except Exception:
            continue
    return None


def _suggest_engine_for_language(language: str, *, exclude: str | None = None) -> str | None:
    """Find the first installed engine whose supported_languages includes `language`.

    Excludes `exclude` (typically the current engine).
    """
    for name, cls in _ENGINES.items():
        if exclude and name == exclude:
            continue
        try:
            if not cls.is_installed():
                continue
            if language in cls().supported_languages:
                return name
        except Exception:
            continue
    return None


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
    variant switch, extended across engines:

    - Same engine + different model -> existing engine.reload(new_id) path.
    - Different engine -> unload current (in-process gpu_utils for Qwen3,
      worker /unload for remote), then construct + warmup the target.

    Validation uses the STATIC catalog (catalog_models()) so we can route
    to engines whose backend is temporarily down and let warmup() surface
    503 with an actionable hint, rather than rejecting as 400.

    Cross-engine swap is atomic: if the target's warmup fails, _engine is
    rolled back to the previous engine reference (which has been unloaded -
    a subsequent request will trigger lazy reload via warmup).

    Server is briefly unavailable during reload (~30-120 s).
    """
    global _engine

    idx = _catalog_index()
    if req.model_id not in idx:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model ID. Known: {', '.join(sorted(idx))}",
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

    # Cross-engine swap. Two-phase to keep _engine consistent on failure.
    # Step 0: gate on installation state. If the target engine isn't installed,
    # return 400 with the exact install command - no point unloading the
    # current engine just to fail the next step with a confusing error.
    target_cls = _ENGINES[target_engine_name]
    try:
        if not target_cls.is_installed():
            raise HTTPException(
                status_code=400,
                detail=(
                    f'Engine "{target_engine_name}" is not installed. '
                    f'Run: make install-{target_engine_name}'
                ),
            )
    except HTTPException:
        raise
    except Exception:
        # is_installed() should never raise, but be defensive.
        pass

    # Step 1: build the target engine (cheap - no model load happens in __init__).
    try:
        target_engine = target_cls()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to construct {target_engine_name}: {e}")

    # Step 2: unload current. Strict VRAM rule - only ONE model loaded at a time.
    _unload_engine(current)

    # Step 3: warmup target. If this fails, rollback _engine to the previous
    # reference AND proactively try to re-warm it (the previous engine was
    # unloaded for VRAM in step 2, so without this the next request would
    # have to wait for lazy reload - that's fine for Qwen3 which lazy-loads
    # in synthesize(), but proactive warm is better operator UX).
    try:
        target_engine.warmup()
    except Exception as e:
        is_runtime = isinstance(e, RuntimeError)
        log.warning("target warmup failed; rolling back _engine to %s", current.engine_name)
        _engine = current
        restore_note = _try_restore(current)
        status = 503 if is_runtime else 500
        prefix = str(e) if is_runtime else f"Failed to load {target_engine_name}: {e}"
        raise HTTPException(
            status_code=status,
            detail=f"{prefix} (rolled back to '{current.engine_name}'; {restore_note})",
        )

    # Step 4: success - commit globals.
    os.environ["TTS_ENGINE"] = target_engine_name
    get_settings.cache_clear()
    _engine = target_engine

    return _switch_response(_engine, f"Switched to {target_engine_name}: {req.model_id}")


@app.post("/tts")
def tts(req: TTSRequest) -> Response:
    """Generate WAV audio from text."""
    engine = get_engine()
    _validate_language(engine, req.language, text=req.text)
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

    # Validate language ONCE (batch shares it) and Cyrillic per-item.
    _validate_language(engine, first.language)
    for item in req.items:
        _validate_language(engine, item.language, text=item.text)

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


def _filter_gen_kwargs_for_engine(engine: TTSEngine, raw: dict) -> dict:
    """Drop kwargs the active engine doesn't actually use.

    The route accepts the union of all engines' tuning knobs (so a single
    HTTP API surface works for any engine), but each engine declares its
    own list via `generation_params`. Filtering here means a direct API
    call that passes `temperature` to VoxCPM2 or `cfg_value` to Qwen3 just
    drops the irrelevant key instead of letting it leak into the engine's
    inference call as an unknown kwarg.
    """
    allowed = {p.key for p in engine.generation_params}
    return {k: v for k, v in raw.items() if k in allowed}


def _collect_gen_kwargs(
    temperature: float | None,
    top_k: int | None,
    top_p: float | None,
    repetition_penalty: float | None,
    max_new_tokens: int | None,
    cfg_value: float | None = None,
    inference_timesteps: int | None = None,
) -> dict:
    """Collect non-None generation kwargs from Form params.

    Includes the union of all engines' tuning knobs - each engine's
    synthesize_*() filters to what it actually accepts. Engines that don't
    use a knob silently ignore it; the UI hides irrelevant controls based
    on engine.generation_params, so users don't see uneffective fields.
    """
    return {
        k: v
        for k, v in {
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "max_new_tokens": max_new_tokens,
            "cfg_value": cfg_value,
            "inference_timesteps": inference_timesteps,
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


# Cyrillic Unicode block (basic Cyrillic + Cyrillic Supplement). Used by the
# IndexTTS2 text-script guard below: upstream's normalizer routes any non-Latin
# text to the Chinese path (vendor/index-tts/indextts/utils/front.py:105),
# producing garbled output. We hard-gate Russian/Cyrillic at the API boundary.
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def _looks_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


def _switch_hint(target_engine: str | None) -> str:
    """Render an actionable hint pointing at a switchable model on `target_engine`.

    Returns empty string if no engine is suggested (caller can omit the hint).
    """
    if not target_engine:
        return ""
    # Pick any model id this engine knows about - first catalog entry is fine.
    try:
        cls = _ENGINES[target_engine]
        models = cls().catalog_models()
        if models:
            mid = models[0].id
            return (
                f' Switch to {target_engine}: POST /model/switch with model_id="{mid}".'
            )
    except Exception:
        pass
    return f" Switch to TTS_ENGINE={target_engine}."


def _validate_language(engine: TTSEngine, language: str, *, text: str | None = None) -> None:
    """Reject unsupported language for the active engine. Two-layer check:

    1. `language` must be in `engine.supported_languages` (hard gate).
    2. For engines whose tokenizer can't handle Cyrillic (`supports_cyrillic_text=False`):
       reject if the text body contains Cyrillic, even if `language=English`.
       Closes the bypass where a user/UI sends `language=English + text="Привет"`
       and gets garbled output.

    The actionable suggestion in the 400 message is computed dynamically -
    no hardcoded engine names.
    """
    supported = engine.supported_languages
    if supported and language not in supported:
        suggestion = _suggest_engine_for_language(language, exclude=engine.engine_name)
        raise HTTPException(
            status_code=400,
            detail=(
                f'Language "{language}" is not supported by engine "{engine.engine_name}". '
                f'Supported: {", ".join(supported)}.' + _switch_hint(suggestion)
            ),
        )
    if not engine.supports_cyrillic_text and text and _looks_cyrillic(text):
        suggestion = _suggest_engine_for_language("Russian", exclude=engine.engine_name)
        raise HTTPException(
            status_code=400,
            detail=(
                f'Engine "{engine.engine_name}" does not support Cyrillic/Russian text '
                "(its tokenizer mangles non-Latin scripts into garbage)."
                + _switch_hint(suggestion)
            ),
        )


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
    repetition_penalty: float | None = Form(default=None, ge=1.0, le=20.0),
    max_new_tokens: int | None = Form(default=None, ge=256, le=4096),
    cfg_value: float | None = Form(default=None, ge=1.0, le=4.0),
    inference_timesteps: int | None = Form(default=None, ge=4, le=30),
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

    _validate_language(engine, language, text=text)
    _validate_upload_size(reference_audio, "reference_audio")
    _validate_upload_size(emotion_audio, "emotion_audio")

    has_emotion = (emotion_audio is not None) or bool(emotion_text) or bool(emotion_vector)
    if has_emotion and not engine.supports_emotional_cloning:
        suggestion = _suggest_emotional_engine(
            exclude=engine.engine_name, language=language, text=text,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f'Engine "{engine.engine_name}" does not support emotional cloning.'
                + _switch_hint(suggestion)
            ),
        )

    modes = sum([emotion_audio is not None, bool(emotion_text), bool(emotion_vector)])
    if modes > 1:
        raise HTTPException(
            status_code=400,
            detail="Use only one emotion mode: emotion_audio, emotion_text, OR emotion_vector",
        )

    # Per-mode capability check: a "text-only" engine like VoxCPM2 must reject
    # emotion_audio / emotion_vector with a clear message, NOT silently drop them.
    engine_modes = engine.emotion_modes
    requested_mode: str | None = None
    if emotion_audio is not None:
        requested_mode = "audio"
    elif emotion_text:
        requested_mode = "text"
    elif emotion_vector:
        requested_mode = "vector"
    if requested_mode and engine_modes and requested_mode not in engine_modes:
        suggestion = _suggest_emotional_engine(
            exclude=engine.engine_name, requires_mode=requested_mode,
            language=language, text=text,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f'Engine "{engine.engine_name}" does not support emotion_{requested_mode}. '
                f"Supported modes: {', '.join(sorted(engine_modes)) or 'none'}."
                + _switch_hint(suggestion)
            ),
        )

    if not 0.0 <= emotion_alpha <= 1.0:
        raise HTTPException(status_code=400, detail="emotion_alpha must be between 0.0 and 1.0")

    # emotion_alpha is meaningful only on engines that expose intensity. If the
    # engine doesn't (VoxCPM2 has no emo_alpha equivalent), reject non-default
    # values rather than silently ignoring them.
    if has_emotion and emotion_alpha != 1.0 and not engine.supports_emotion_strength:
        suggestion = _suggest_emotional_engine(
            exclude=engine.engine_name, requires_strength=True,
            language=language, text=text,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f'Engine "{engine.engine_name}" does not expose emotion intensity '
                "(emotion_alpha). Omit the parameter or leave it at 1.0."
                + _switch_hint(suggestion)
            ),
        )

    vec = _parse_emotion_vector(emotion_vector)

    audio_bytes = await reference_audio.read()
    emotion_audio_bytes = await emotion_audio.read() if emotion_audio is not None else None

    gen_kwargs = _filter_gen_kwargs_for_engine(
        engine,
        _collect_gen_kwargs(
            temperature, top_k, top_p, repetition_penalty, max_new_tokens,
            cfg_value=cfg_value, inference_timesteps=inference_timesteps,
        ),
    )
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

    _validate_language(engine, language, text=text)

    gen_kwargs = _filter_gen_kwargs_for_engine(
        engine,
        _collect_gen_kwargs(temperature, top_k, top_p, repetition_penalty, max_new_tokens),
    )
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
