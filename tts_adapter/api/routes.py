"""FastAPI routes for TTS adapter."""

import io
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response

from ..config import get_settings
from ..contract import HealthResponse, TTSBatchRequest, TTSRequest
from ..engines.qwen3 import Qwen3Engine

# Global engine instance
_engine: Qwen3Engine | None = None


def get_engine() -> Qwen3Engine:
    """Get or create engine instance."""
    global _engine
    if _engine is None:
        _engine = Qwen3Engine()
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
    return HealthResponse(
        ok=True,
        engine=engine.engine_name,
        model=engine.model_id,
        device=engine.device,
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


@app.post("/tts/batch")
def tts_batch(req: TTSBatchRequest) -> Response:
    """Generate multiple WAV files as ZIP."""
    engine = get_engine()

    # Group by common params for efficient batching
    texts = [item.text for item in req.items]
    ids = [item.id for item in req.items]

    # Use first item's params for batch (all same in typical use)
    first = req.items[0]
    wav_bytes_list = engine.synthesize_batch(
        texts=texts,
        language=first.language,
        speaker=first.speaker,
        instruct=first.instruct,
    )

    # Create ZIP archive
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_id, wav_bytes in zip(ids, wav_bytes_list):
            zf.writestr(f"{item_id}.wav", wav_bytes)

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tts_batch.zip"},
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)
