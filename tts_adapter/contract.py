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
    supports_custom_voice: bool = Field(default=False, description="Whether preset speakers are supported")


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Human-readable model name")
    variant: str = Field(..., description="Model variant: Base, CustomVoice, or VoiceDesign")
    supports_cloning: bool = Field(default=False)
    supports_design: bool = Field(default=False)
    supports_custom_voice: bool = Field(default=False)


class ModelsResponse(BaseModel):
    """Response listing available models."""

    current: str = Field(..., description="Currently loaded model ID")
    available: list[ModelInfo] = Field(..., description="List of available models")


class SwitchModelRequest(BaseModel):
    """Request to switch to a different model."""

    model_id: str = Field(..., description="Model ID to switch to")


class SwitchModelResponse(BaseModel):
    """Response after model switch."""

    success: bool
    model: str = Field(..., description="New model ID")
    message: str = Field(..., description="Status message")
    supports_cloning: bool = Field(default=False)
    supports_design: bool = Field(default=False)
    supports_custom_voice: bool = Field(default=False)
