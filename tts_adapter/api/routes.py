"""FastAPI routes for TTS adapter."""

import io
import re
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import get_settings
from ..contract import HealthResponse, TTSBatchRequest, TTSRequest
from ..engines.qwen3 import Qwen3Engine
from ..engine import TTSEngine
from ..engines import create_engine

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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check with model info."""
    engine = get_engine()
    supports_cloning = False
    if isinstance(engine, Qwen3Engine):
        supports_cloning = engine.supports_cloning
    return HealthResponse(
        ok=True,
        engine=engine.engine_name,
        model=engine.model_id,
        device=engine.device,
        supports_cloning=supports_cloning,
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


@app.post("/tts/clone")
async def tts_clone(
    text: str = Form(..., description="Text to synthesize"),
    language: str = Form(default="Auto", description="Language code"),
    reference_audio: UploadFile = File(..., description="Reference audio WAV (3-10 sec)"),
) -> Response:
    """Generate speech by cloning voice from reference audio.

    Requires Base model (not CustomVoice). Set TTS_QWEN3_MODEL_ID to a Base model.
    """
    engine = get_engine()

    if not isinstance(engine, Qwen3Engine):
        raise HTTPException(status_code=400, detail="Voice cloning only supported by Qwen3 engine")

    if not engine.supports_cloning:
        raise HTTPException(
            status_code=400,
            detail="Voice cloning requires Base model. Set TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        )

    audio_bytes = await reference_audio.read()
    wav_bytes = engine.synthesize_clone(
        text=text,
        reference_audio=audio_bytes,
        language=language,
    )
    return Response(content=wav_bytes, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)
