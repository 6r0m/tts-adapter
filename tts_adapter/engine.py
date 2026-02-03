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

    @property
    def supports_cloning(self) -> bool:
        """Whether this engine/model supports voice cloning."""
        ...

    @property
    def supports_design(self) -> bool:
        """Whether this engine/model supports voice design from description."""
        ...

    def synthesize_clone(
        self,
        text: str,
        reference_audio: bytes,
        language: str = "Auto",
        reference_text: str | None = None,
    ) -> bytes:
        """Clone voice from reference audio.

        Args:
            text: Text to synthesize
            reference_audio: WAV bytes of reference voice (3-10 sec)
            language: Language code
            reference_text: Optional transcript of reference audio

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
