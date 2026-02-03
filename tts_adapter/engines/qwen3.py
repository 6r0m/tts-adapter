"""Qwen3-TTS engine implementation."""

import io
import threading
from functools import lru_cache
from typing import Literal

import soundfile as sf
import torch
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..config import get_settings

# Qwen3-specific defaults (owned by this engine)
_DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
_DEFAULT_DEVICE = "cuda:0"
_DEFAULT_DTYPE = "bfloat16"


class Qwen3Settings(BaseSettings):
    """Qwen3 engine settings from environment.

    Env vars (with TTS_QWEN3_ prefix):
        TTS_QWEN3_MODEL_ID: HuggingFace model ID (used when MODEL_PATH not set)
        TTS_QWEN3_MODEL_PATH: Local directory path (for offline mode)
        TTS_QWEN3_DEVICE: Device
        TTS_QWEN3_DTYPE: Data type
    """

    # Ignore other TTS_* vars from .env (handled by main config)
    model_config = SettingsConfigDict(
        env_prefix="TTS_QWEN3_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_id: str = _DEFAULT_MODEL_ID
    # Local path for offline mode - takes priority over model_id
    model_path: str | None = None
    device: str = _DEFAULT_DEVICE
    dtype: str = _DEFAULT_DTYPE


@lru_cache
def get_qwen3_settings() -> Qwen3Settings:
    """Get cached Qwen3 settings instance."""
    return Qwen3Settings()


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
        model_path: str | None = None,
        device: str | None = None,
        dtype: Literal["bfloat16", "float16", "float32"] | None = None,
    ):
        """Initialize engine with optional overrides.

        Args:
            model_id: HuggingFace model ID (ignored if model_path set)
            model_path: Local directory path for offline mode
            device: Device string like 'cuda:0'
            dtype: Data type
        """
        settings = get_settings()
        qwen3 = get_qwen3_settings()

        # Local path takes priority over model_id (for offline mode)
        self._model_path = model_path or qwen3.model_path
        self._model_id = model_id or qwen3.model_id
        self._device = device or qwen3.device
        self._dtype_str = dtype or qwen3.dtype

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

        # Use local path if set (offline mode), otherwise HF model ID
        model_source = self._model_path or self._model_id

        self._model = Qwen3TTSModel.from_pretrained(
            model_source,
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

        wav = self._trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
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
            trimmed = self._trim_silence(wav, sr)
            buf = io.BytesIO()
            sf.write(buf, trimmed, sr, format="WAV")
            results.append(buf.getvalue())

        return results

    def synthesize_clone(
        self,
        text: str,
        reference_audio: str | bytes,
        language: str = "Auto",
        reference_text: str | None = None,
    ) -> bytes:
        """Generate speech by cloning voice from reference audio.

        Requires Base model (not CustomVoice).

        Args:
            text: Text to synthesize
            reference_audio: Path to reference WAV file or WAV bytes (3-10 sec)
            language: Target language
            reference_text: Transcript of reference audio (improves quality)
        """
        if self._model is None:
            self.warmup()

        actual_language = self._resolve_language(language)

        # Handle bytes input - write to temp file
        temp_path = None
        if isinstance(reference_audio, bytes):
            import tempfile
            temp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path.write(reference_audio)
            temp_path.close()
            audio_path = temp_path.name
        else:
            audio_path = reference_audio

        # Use x_vector_only_mode when no transcript provided
        use_x_vector_only = not reference_text or reference_text.strip() == ""

        try:
            with self._lock:
                wavs, sr = self._model.generate_voice_clone(
                    text=text,
                    language=actual_language,
                    ref_audio=audio_path,
                    ref_text=reference_text or "",
                    x_vector_only_mode=use_x_vector_only,
                )
        finally:
            if temp_path:
                import os
                os.unlink(temp_path.name)

        wav = self._trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    def synthesize_design(
        self,
        text: str,
        instruct: str,
        language: str = "Auto",
    ) -> bytes:
        """Generate speech with designed voice from natural language description.

        Requires VoiceDesign model.

        Args:
            text: Text to synthesize
            instruct: Natural language description of the voice
            language: Target language
        """
        if self._model is None:
            self.warmup()

        actual_language = self._resolve_language(language)

        with self._lock:
            wavs, sr = self._model.generate_voice_design(
                text=text,
                language=actual_language,
                instruct=instruct,
            )

        wav = self._trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    def _trim_silence(self, wav, sr: int, pad_seconds: float = 0.05):
        """Trim leading/trailing near-silence to avoid padded output."""
        try:
            import numpy as np
        except ImportError:
            return wav

        wav_arr = np.asarray(wav)
        if wav_arr.size == 0:
            return wav_arr

        if wav_arr.ndim == 2:
            signal = np.max(np.abs(wav_arr), axis=1)
        else:
            signal = np.abs(wav_arr)

        max_amp = float(signal.max()) if signal.size else 0.0
        if max_amp <= 0:
            return wav_arr

        threshold = max(max_amp * 0.01, 1e-4)
        indices = np.where(signal > threshold)[0]
        if indices.size == 0:
            return wav_arr

        pad = int(sr * pad_seconds)
        start = max(int(indices[0]) - pad, 0)
        end = min(int(indices[-1]) + pad + 1, wav_arr.shape[0])
        return wav_arr[start:end]

    @property
    def supports_cloning(self) -> bool:
        """Check if loaded model supports voice cloning."""
        model_id = str(self._model_path or self._model_id or "")
        return "Base" in model_id

    @property
    def supports_design(self) -> bool:
        """Check if loaded model supports voice design."""
        model_id = str(self._model_path or self._model_id or "")
        return "VoiceDesign" in model_id

    @property
    def supports_custom_voice(self) -> bool:
        """Check if loaded model supports preset speakers (CustomVoice)."""
        model_id = str(self._model_path or self._model_id or "")
        return "CustomVoice" in model_id

    @property
    def engine_name(self) -> str:
        """Return engine identifier."""
        return "qwen3"

    @property
    def model_id(self) -> str:
        """Return loaded model identifier (path or HF ID)."""
        return self._model_path or self._model_id

    @property
    def device(self) -> str:
        """Return device string."""
        return self._device

    def reload(self, model_id: str) -> None:
        """Reload engine with a different model.

        Unloads current model from GPU memory and loads the new model.

        Args:
            model_id: New model ID (e.g., 'Qwen/Qwen3-TTS-12Hz-1.7B-Base')
        """
        with self._lock:
            # Unload current model
            if self._model is not None:
                del self._model
                self._model = None
                # Force garbage collection to free GPU memory
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Update model ID
            self._model_id = model_id
            self._model_path = None  # Clear local path, use HF ID

        # Load new model
        self.warmup()
