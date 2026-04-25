"""TTS Engine protocol - the universal interface for all TTS backends."""

from typing import Any, Protocol, runtime_checkable

from .contract import ModelInfo


@runtime_checkable
class TTSEngine(Protocol):
    """Universal TTS engine interface.

    All engine implementations must satisfy this protocol.
    """

    def warmup(self) -> None:
        """Load model into memory and prepare for inference.

        Called once at startup. Should handle model download if needed.
        """
        ...

    def synthesize(
        self,
        text: str,
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs: Any,
    ) -> bytes:
        """Generate WAV audio bytes from text.

        Args:
            text: Text to synthesize
            language: Language code or 'Auto' for auto-detection
            speaker: Speaker/voice identifier
            instruct: Style instruction (tone, emotion, pace)

        Returns:
            WAV audio bytes
        """
        ...

    def synthesize_batch(
        self,
        texts: list[str],
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs: Any,
    ) -> list[bytes]:
        """Batch generation - multiple prompts in one forward pass.

        Args:
            texts: List of texts to synthesize
            language: Language code (same for all)
            speaker: Speaker/voice identifier (same for all)
            instruct: Style instruction (same for all)

        Returns:
            List of WAV audio bytes, one per input text
        """
        ...

    @property
    def engine_name(self) -> str:
        """Return engine identifier (e.g., 'qwen3')."""
        ...

    @property
    def model_id(self) -> str:
        """Return loaded model identifier."""
        ...

    @property
    def device(self) -> str:
        """Return device string (e.g., 'cuda:0', 'cpu')."""
        ...

    @property
    def supports_cloning(self) -> bool:
        """Whether this engine/model supports voice cloning."""
        ...

    @property
    def supports_design(self) -> bool:
        """Whether this engine/model supports voice design from description."""
        ...

    @property
    def supports_custom_voice(self) -> bool:
        """Whether this engine/model supports preset speakers (Simple TTS)."""
        ...

    @property
    def supports_emotional_cloning(self) -> bool:
        """Whether this engine can combine voice cloning with emotion control.

        Engines that return False MUST be rejected at the API layer when
        emotion params are present — never silently ignored.
        """
        ...

    def available_models(self) -> list[ModelInfo]:
        """Return models this engine can switch between.

        Engines own their own metadata so routes don't branch on engine_name.
        Single-model engines (e.g. IndexTTS2) return a one-entry list.
        """
        ...

    def synthesize_clone(
        self,
        text: str,
        reference_audio: bytes,
        language: str = "Auto",
        reference_text: str | None = None,
        *,
        emotion_audio: bytes | str | None = None,
        emotion_text: str | None = None,
        emotion_vector: list[float] | None = None,
        emotion_alpha: float = 1.0,
        **kwargs: Any,
    ) -> bytes:
        """Clone voice from reference audio, optionally with emotion control.

        Args:
            text: Text to synthesize
            reference_audio: WAV bytes of reference voice (3-10 sec)
            language: Language code
            reference_text: Optional transcript of reference audio
            emotion_audio: WAV bytes/path for emotion reference
                (engines without supports_emotional_cloning ignore this)
            emotion_text: Free-form emotion description
            emotion_vector: 8-dim vector ordered as
                [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
            emotion_alpha: Emotion blend strength in [0.0, 1.0]

        Returns:
            WAV audio bytes

        Raises:
            NotImplementedError: If engine doesn't support cloning
        """
        ...

    def synthesize_design(
        self,
        text: str,
        instruct: str,
        language: str = "Auto",
        **kwargs: Any,
    ) -> bytes:
        """Generate speech with voice designed from description.

        Args:
            text: Text to synthesize
            instruct: Natural language voice description
            language: Language code

        Returns:
            WAV audio bytes

        Raises:
            NotImplementedError: If engine doesn't support voice design
        """
        ...

    def reload(self, model_id: str) -> None:
        """Reload engine with a different model.

        Unloads current model and loads the specified model.

        Args:
            model_id: New model ID to load
        """
        ...
