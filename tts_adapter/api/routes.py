"""FastAPI routes for TTS adapter."""

import io
import re
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import get_settings
from ..contract import (
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    SwitchModelRequest,
    SwitchModelResponse,
    TTSBatchRequest,
    TTSRequest,
)
from ..engine import TTSEngine
from ..engines import create_engine
from ..web import router as web_router

# Global engine instance
_engine: TTSEngine | None = None


def get_engine() -> TTSEngine:
    """Get or create engine instance."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warmup model on startup."""
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
    )


# Available Qwen3-TTS models
AVAILABLE_MODELS = [
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        name="CustomVoice 1.7B",
        variant="CustomVoice",
        supports_custom_voice=True,
        supports_cloning=False,
        supports_design=False,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        name="VoiceDesign 1.7B",
        variant="VoiceDesign",
        supports_custom_voice=False,
        supports_cloning=False,
        supports_design=True,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        name="Base 1.7B (Clone)",
        variant="Base",
        supports_custom_voice=False,
        supports_cloning=True,
        supports_design=False,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        name="Base 0.6B (Clone, Low VRAM)",
        variant="Base",
        supports_custom_voice=False,
        supports_cloning=True,
        supports_design=False,
    ),
]


@app.get("/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    """List available models and current model."""
    engine = get_engine()
    return ModelsResponse(
        current=engine.model_id,
        available=AVAILABLE_MODELS,
    )


@app.post("/model/switch", response_model=SwitchModelResponse)
def switch_model(req: SwitchModelRequest) -> SwitchModelResponse:
    """Switch to a different model.

    Warning: This unloads the current model and loads the new one.
    Takes ~2 minutes and server is unavailable during reload.
    """
    # Validate model ID
    valid_ids = {m.id for m in AVAILABLE_MODELS}
    if req.model_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model ID. Available: {', '.join(valid_ids)}",
        )

    engine = get_engine()

    # Check if already loaded
    if engine.model_id == req.model_id:
        return SwitchModelResponse(
            success=True,
            model=engine.model_id,
            message="Model already loaded",
            supports_cloning=engine.supports_cloning,
            supports_design=engine.supports_design,
            supports_custom_voice=engine.supports_custom_voice,
        )

    # Reload with new model
    try:
        engine.reload(req.model_id)
        return SwitchModelResponse(
            success=True,
            model=engine.model_id,
            message=f"Switched to {req.model_id}",
            supports_cloning=engine.supports_cloning,
            supports_design=engine.supports_design,
            supports_custom_voice=engine.supports_custom_voice,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch model: {e}",
        )


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


@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(..., description="Text to synthesize"),
    language: str = Form(default="Auto", description="Language code"),
    reference_text: str = Form(default="", description="Transcript of reference audio (improves quality)"),
    reference_audio: UploadFile = File(..., description="Reference audio WAV (3-10 sec)"),
    temperature: float | None = Form(default=None, ge=0.01, le=2.0),
    top_k: int | None = Form(default=None, ge=1, le=200),
    top_p: float | None = Form(default=None, ge=0.1, le=1.0),
    repetition_penalty: float | None = Form(default=None, ge=1.0, le=2.0),
    max_new_tokens: int | None = Form(default=None, ge=256, le=4096),
) -> Response:
    """Generate speech by cloning voice from reference audio.

    Requires a model that supports voice cloning (e.g., Base model).
    Provide reference_text (transcript) for better quality.
    """
    engine = get_engine()

    if not engine.supports_cloning:
        raise HTTPException(
            status_code=400,
            detail="Voice cloning not supported by current model configuration",
        )

    audio_bytes = await reference_audio.read()
    gen_kwargs = _collect_gen_kwargs(temperature, top_k, top_p, repetition_penalty, max_new_tokens)
    wav_bytes = engine.synthesize_clone(
        text=text,
        reference_audio=audio_bytes,
        language=language,
        reference_text=reference_text if reference_text else None,
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
