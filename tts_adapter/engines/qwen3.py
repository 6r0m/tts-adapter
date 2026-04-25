"""Qwen3-TTS engine implementation."""

import io
import threading
from functools import lru_cache
from typing import Literal

import soundfile as sf
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..audio_utils import bytes_to_tempfile, trim_silence
from ..config import get_settings
from ..contract import ModelInfo
from ..gpu_utils import unload_gpu_model

# Qwen3-specific defaults (owned by this engine)
_DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
_DEFAULT_DEVICE = "cuda:0"
_DEFAULT_DTYPE = "bfloat16"

# Models this engine can switch between at runtime (moved here from routes.py
# so engines own their own metadata — keeps routes free of engine-name branching).
_AVAILABLE_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        name="CustomVoice 1.7B",
        variant="CustomVoice",
        supports_custom_voice=True,
        supports_cloning=False,
        supports_design=False,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        name="VoiceDesign 1.7B",
        variant="VoiceDesign",
        supports_custom_voice=False,
        supports_cloning=False,
        supports_design=True,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        name="Base 1.7B (Clone)",
        variant="Base",
        supports_custom_voice=False,
        supports_cloning=True,
        supports_design=False,
    ),
    ModelInfo(
        id="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        name="Base 0.6B (Clone, Low VRAM)",
        variant="Base",
        supports_custom_voice=False,
        supports_cloning=True,
        supports_design=False,
    ),
]


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


_GEN_KWARG_KEYS = {"temperature", "top_k", "top_p", "repetition_penalty", "max_new_tokens"}


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

        import torch

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

    @staticmethod
    def _filter_gen_kwargs(**kwargs) -> dict:
        """Extract recognized generation kwargs, dropping None values."""
        return {k: v for k, v in kwargs.items() if k in _GEN_KWARG_KEYS and v is not None}

    def synthesize(
        self,
        text: str,
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs,
    ) -> bytes:
        """Generate WAV audio bytes from text."""
        if self._model is None:
            self.warmup()

        actual_speaker = self._resolve_speaker(speaker)
        actual_language = self._resolve_language(language)
        gen_kwargs = self._filter_gen_kwargs(**kwargs)

        with self._lock:
            wavs, sr = self._model.generate_custom_voice(
                text=text,
                language=actual_language,
                speaker=actual_speaker,
                instruct=instruct,
                **gen_kwargs,
            )

        wav = trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    def synthesize_batch(
        self,
        texts: list[str],
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs,
    ) -> list[bytes]:
        """Batch generation - multiple prompts in one forward pass."""
        if not texts:
            return []

        if self._model is None:
            self.warmup()

        actual_speaker = self._resolve_speaker(speaker)
        actual_language = self._resolve_language(language)
        gen_kwargs = self._filter_gen_kwargs(**kwargs)

        with self._lock:
            wavs, sr = self._model.generate_custom_voice(
                text=texts,
                language=actual_language,
                speaker=actual_speaker,
                instruct=instruct,
                **gen_kwargs,
            )

        results = []
        for wav in wavs:
            trimmed = trim_silence(wav, sr)
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
        **kwargs,
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

        # Use x_vector_only_mode when no transcript provided
        use_x_vector_only = not reference_text or reference_text.strip() == ""

        gen_kwargs = self._filter_gen_kwargs(**kwargs)

        def _generate(audio_path: str):
            with self._lock:
                return self._model.generate_voice_clone(
                    text=text,
                    language=actual_language,
                    ref_audio=audio_path,
                    ref_text=reference_text or "",
                    x_vector_only_mode=use_x_vector_only,
                    **gen_kwargs,
                )

        if isinstance(reference_audio, bytes):
            with bytes_to_tempfile(reference_audio, suffix=".wav") as audio_path:
                wavs, sr = _generate(audio_path)
        else:
            wavs, sr = _generate(reference_audio)

        wav = trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    def synthesize_design(
        self,
        text: str,
        instruct: str,
        language: str = "Auto",
        **kwargs,
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

        gen_kwargs = self._filter_gen_kwargs(**kwargs)

        with self._lock:
            wavs, sr = self._model.generate_voice_design(
                text=text,
                language=actual_language,
                instruct=instruct,
                **gen_kwargs,
            )

        wav = trim_silence(wavs[0], sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    @property
    def supports_cloning(self) -> bool:
        """Check if loaded model supports voice cloning."""
        return "Base" in self._model_id

    @property
    def supports_design(self) -> bool:
        """Check if loaded model supports voice design."""
        return "VoiceDesign" in self._model_id

    @property
    def supports_custom_voice(self) -> bool:
        """Check if loaded model supports preset speakers (CustomVoice)."""
        return "CustomVoice" in self._model_id

    @property
    def supports_emotional_cloning(self) -> bool:
        """Qwen3 cannot combine clone + emotion (model-architecture limitation).

        Base model accepts no `instruct` param; CustomVoice has no clone path.
        See docs/engines/qwen3/README.md for details.
        """
        return False

    def catalog_models(self) -> list[ModelInfo]:
        """Static list of all Qwen3 variants we know about.

        For Qwen3 this equals available_models() - the engine is in-process
        so there's no separate "is the backend reachable" question.
        """
        return _AVAILABLE_MODELS

    def available_models(self) -> list[ModelInfo]:
        """Models this engine can switch between via /model/switch."""
        return _AVAILABLE_MODELS

    @property
    def engine_name(self) -> str:
        """Return engine identifier."""
        return "qwen3"

    @property
    def model_id(self) -> str:
        """Return loaded model identifier (HF ID)."""
        return self._model_id

    @property
    def device(self) -> str:
        """Return device string."""
        return self._device

    @staticmethod
    def _resolve_cache_path(model_id: str) -> str | None:
        """Resolve HF model ID to local cache snapshot path.

        Works around transformers 4.57.3 _patch_mistral_regex bug that
        makes a network call even for cached models. Returning a local
        path makes from_pretrained treat it as local and skip the call.
        """
        try:
            from huggingface_hub import snapshot_download

            return snapshot_download(model_id, local_files_only=True)
        except Exception:
            return None

    def reload(self, model_id: str) -> None:
        """Reload engine with a different model.

        Unloads current model from GPU memory and loads the new model.

        Args:
            model_id: New model ID (e.g., 'Qwen/Qwen3-TTS-12Hz-1.7B-Base')
        """
        with self._lock:
            if self._model is not None:
                model_ref = self._model
                self._model = None
                unload_gpu_model(model_ref)

            # Update model ID and resolve local cache path for offline mode
            self._model_id = model_id
            self._model_path = self._resolve_cache_path(model_id)

        # Load new model
        self.warmup()
