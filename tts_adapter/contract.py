"""Request and response models for TTS adapter."""

from pydantic import BaseModel, Field


class GenerationSettings(BaseModel):
    """Optional generation kwargs passed to the model.

    All fields default to None, meaning library defaults are used.
    """

    temperature: float | None = Field(default=None, ge=0.01, le=2.0, description="Sampling temperature (default: 0.9)")
    top_k: int | None = Field(default=None, ge=1, le=200, description="Top-k sampling (default: 50)")
    top_p: float | None = Field(default=None, ge=0.1, le=1.0, description="Nucleus sampling (default: 1.0)")
    repetition_penalty: float | None = Field(default=None, ge=1.0, le=2.0, description="Repetition penalty (default: 1.05)")
    max_new_tokens: int | None = Field(default=None, ge=256, le=4096, description="Max codec tokens (default: 2048)")

    def to_kwargs(self) -> dict:
        """Return only non-None values as a dict for **kwargs passthrough."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class TTSRequest(BaseModel):
    """Single TTS generation request."""

    text: str = Field(..., description="Text to synthesize")
    language: str = Field(default="Auto", description="Language code or 'Auto'")
    speaker: str = Field(default="default", description="Speaker/voice name")
    instruct: str = Field(default="", description="Style instruction (tone, emotion, speed)")
    generation: GenerationSettings = Field(default_factory=GenerationSettings, description="Generation parameters")


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
