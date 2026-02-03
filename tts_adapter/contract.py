"""Request and response models for TTS adapter."""

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """Single TTS generation request."""

    text: str = Field(..., description="Text to synthesize")
    language: str = Field(default="Auto", description="Language code or 'Auto'")
    speaker: str = Field(default="default", description="Speaker/voice name")
    instruct: str = Field(default="", description="Style instruction (tone, emotion, speed)")


class TTSBatchItem(BaseModel):
    """Single item in a batch request."""

    id: str = Field(..., description="Unique identifier for this item")
    text: str = Field(..., description="Text to synthesize")
    language: str = Field(default="Auto", description="Language code or 'Auto'")
    speaker: str = Field(default="default", description="Speaker/voice name")
    instruct: str = Field(default="", description="Style instruction")


class TTSBatchRequest(BaseModel):
    """Batch TTS generation request."""

    items: list[TTSBatchItem] = Field(..., description="List of texts to synthesize")


class TTSCloneRequest(BaseModel):
    """Voice cloning TTS request (used with form data, not JSON body)."""

    text: str = Field(..., description="Text to synthesize")
    language: str = Field(default="Auto", description="Language code or 'Auto'")


class HealthResponse(BaseModel):
    """Health check response."""

    ok: bool
    engine: str
    model: str
    device: str
    supports_cloning: bool = Field(default=False, description="Whether voice cloning is supported")
    supports_design: bool = Field(default=False, description="Whether voice design is supported")
