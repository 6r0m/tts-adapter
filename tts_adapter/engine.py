"""TTS Engine protocol - the universal interface for all TTS backends."""

from typing import Protocol, runtime_checkable


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
