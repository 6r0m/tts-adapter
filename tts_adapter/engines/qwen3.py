"""Qwen3-TTS engine implementation."""

import io
import threading
from typing import Literal

import soundfile as sf
import torch

from ..config import get_settings


class Qwen3Engine:
    """Qwen3-TTS engine implementation.

    Uses Qwen3-TTS CustomVoice model for text-to-speech generation.
    Thread-safe via lock for GPU serialization.
    """

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
        dtype: Literal["bfloat16", "float16", "float32"] | None = None,
    ):
        """Initialize engine with optional overrides.

        Args:
            model_id: HuggingFace model ID (default from env TTS_MODEL_ID)
            device: Device string like 'cuda:0' (default from env TTS_DEVICE)
            dtype: Data type (default from env TTS_DTYPE)
        """
        settings = get_settings()
        self._model_id = model_id or settings.model_id
        self._device = device or settings.device
        self._dtype_str = dtype or settings.dtype
        self._default_speaker = settings.default_speaker
        self._default_language = settings.default_language

        self._model = None
        self._lock = threading.Lock()

    def warmup(self) -> None:
        """Load model into memory."""
        if self._model is not None:
            return

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(self._dtype_str, torch.bfloat16)

        # Check for flash_attention_2 availability
        attn_impl: str | None = None
        try:
            import flash_attn  # noqa: F401

            attn_impl = "flash_attention_2"
        except ImportError:
            pass

        from qwen_tts import Qwen3TTSModel

        self._model = Qwen3TTSModel.from_pretrained(
            self._model_id,
            device_map=self._device,
            dtype=dtype,
            attn_implementation=attn_impl,
        )

    def synthesize(
        self,
        text: str,
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
    ) -> bytes:
        """Generate WAV audio bytes from text."""
        if self._model is None:
            self.warmup()

        actual_speaker = speaker if speaker != "default" else self._default_speaker
        actual_language = language if language != "Auto" else self._default_language

        with self._lock:
            wavs, sr = self._model.generate_custom_voice(
                text=text,
                language=actual_language,
                speaker=actual_speaker,
                instruct=instruct,
            )

        buf = io.BytesIO()
        sf.write(buf, wavs[0], sr, format="WAV")
        return buf.getvalue()

    def synthesize_batch(
        self,
        texts: list[str],
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
    ) -> list[bytes]:
        """Batch generation - multiple prompts in one forward pass."""
        if not texts:
            return []

        if self._model is None:
            self.warmup()

        actual_speaker = speaker if speaker != "default" else self._default_speaker
        actual_language = language if language != "Auto" else self._default_language

        with self._lock:
            wavs, sr = self._model.generate_custom_voice(
                text=texts,
                language=actual_language,
                speaker=actual_speaker,
                instruct=instruct,
            )

        results = []
        for wav in wavs:
            buf = io.BytesIO()
            sf.write(buf, wav, sr, format="WAV")
            results.append(buf.getvalue())

        return results

    @property
    def engine_name(self) -> str:
        """Return engine identifier."""
        return "qwen3"

    @property
    def model_id(self) -> str:
        """Return loaded model identifier."""
        return self._model_id

    @property
    def device(self) -> str:
        """Return device string."""
        return self._device
