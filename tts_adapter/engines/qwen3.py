"""Qwen3-TTS engine implementation."""

import io
import os
import threading
from typing import Literal

import soundfile as sf
import torch

from ..config import get_settings

# Qwen3-specific defaults (owned by this engine, not global config)
_DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
_DEFAULT_DEVICE = "cuda:0"
_DEFAULT_DTYPE = "bfloat16"


class Qwen3Engine:
    """Qwen3-TTS engine implementation.

    Uses Qwen3-TTS CustomVoice model for text-to-speech generation.
    Thread-safe via lock for GPU serialization.

    Engine-specific env vars:
        TTS_QWEN3_MODEL_ID: Model ID (default: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)
        TTS_QWEN3_DEVICE: Device (default: cuda:0)
        TTS_QWEN3_DTYPE: Data type (default: bfloat16)
    """

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
        dtype: Literal["bfloat16", "float16", "float32"] | None = None,
    ):
        """Initialize engine with optional overrides.

        Args:
            model_id: HuggingFace model ID
            device: Device string like 'cuda:0'
            dtype: Data type
        """
        settings = get_settings()

        # Engine-specific config: constructor arg > env var > default
        self._model_id = (
            model_id
            or os.getenv("TTS_QWEN3_MODEL_ID")
            or _DEFAULT_MODEL_ID
        )
        self._device = (
            device
            or os.getenv("TTS_QWEN3_DEVICE")
            or _DEFAULT_DEVICE
        )
        self._dtype_str = (
            dtype
            or os.getenv("TTS_QWEN3_DTYPE")
            or _DEFAULT_DTYPE
        )

        # Shared config from global settings
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

    def _resolve_speaker(self, speaker: str) -> str:
        """Resolve speaker, error if 'default' requested but not configured."""
        if speaker != "default":
            return speaker
        if self._default_speaker is None:
            raise ValueError(
                "speaker='default' but TTS_DEFAULT_SPEAKER not set. "
                "Provide explicit speaker or set TTS_DEFAULT_SPEAKER env var."
            )
        return self._default_speaker

    def _resolve_language(self, language: str) -> str:
        """Resolve language, error if 'Auto' requested but not configured."""
        if language != "Auto":
            return language
        if self._default_language is None:
            raise ValueError(
                "language='Auto' but TTS_DEFAULT_LANGUAGE not set. "
                "Provide explicit language or set TTS_DEFAULT_LANGUAGE env var."
            )
        return self._default_language

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

        actual_speaker = self._resolve_speaker(speaker)
        actual_language = self._resolve_language(language)

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

        actual_speaker = self._resolve_speaker(speaker)
        actual_language = self._resolve_language(language)

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
