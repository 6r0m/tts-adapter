"""VoxCPM2 remote engine - HTTP client for the isolated worker process.

The worker runs in vendor/voxcpm/.venv (separate Python env, no shared deps with
the main adapter) and exposes /health, /load, /unload, /tts/clone. This engine
just forwards requests over HTTP. See docs/engines/voxcpm2/README.md for why
the two-process architecture is required (gradio 6 + modelscope + funasr +
datasets <4 from upstream conflict with the main adapter's deps).

VoxCPM2 differs from IndexTTS2 in three important ways:
  1. Emotion is an inline `(...)` text prefix, not a separate kwarg.
     The worker prepends `f"({emotion_text}){text}"` before calling generate().
  2. emotion_modes = {"text"} only - no audio-reference or 8-vector emotion modes.
     Routes 400-reject emotion_audio / emotion_vector for VoxCPM2.
  3. supports_emotion_strength=False - upstream has no emo_alpha equivalent
     (cfg_value isn't a clean intensity knob). Routes reject non-default
     emotion_alpha to avoid silently ignoring user intent.
"""

import logging
import threading
from functools import lru_cache

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..contract import GenerationParam, ModelInfo

# VoxCPM2 has its OWN tuning knobs - cfg_value (classifier-free guidance) and
# inference_timesteps (denoising steps). It does NOT use temperature/top_k/top_p
# /repetition_penalty/max_new_tokens like qwen3/indextts2. Defaults from upstream
# voxcpm.core.VoxCPM._generate (cfg_value=2.0, inference_timesteps=10).
_GENERATION_PARAMS: list[GenerationParam] = [
    GenerationParam(key="cfg_value", label="CFG Guidance", type="number",
                    default=2.0, min=1.0, max=4.0, step=0.1,
                    help="Classifier-free guidance scale. Higher = more faithful to text/style, less natural. Default: 2.0"),
    GenerationParam(key="inference_timesteps", label="Inference Steps", type="integer",
                    default=10, min=4, max=30, step=1,
                    help="Denoising steps. More = better quality, slower. Default: 10 (upstream sweet spot)"),
]

log = logging.getLogger(__name__)

_MODEL_ID = "openbmb/VoxCPM2"

# VoxCPM2 official supported languages (HF card cardData.language).
# 30-ish ISO codes; we expose them as language NAMES matching qwen3 spelling
# where they overlap, so the UI dropdown stays consistent across engines.
# "Auto" included - VoxCPM2 doesn't have a tokenizer that mangles Cyrillic
# the way IndexTTS2 does, so an Auto request is safe.
_SUPPORTED_LANGUAGES = [
    "Auto",
    "Arabic",
    "Chinese",
    "Danish",
    "Dutch",
    "English",
    "Finnish",
    "French",
    "German",
    "Greek",
    "Hebrew",
    "Hindi",
    "Italian",
    "Japanese",
    "Korean",
    "Malay",
    "Norwegian",
    "Polish",
    "Portuguese",
    "Russian",
    "Spanish",
    "Swahili",
    "Swedish",
    "Turkish",
]

_MODEL_INFO = ModelInfo(
    id=_MODEL_ID,
    name="VoxCPM2",
    variant="Base+EmotionText",
    supports_cloning=True,
    supports_emotional_cloning=True,
    supports_design=False,  # upstream supports it (text-only) but out-of-scope for this todo
    supports_custom_voice=False,
    emotion_modes=["text"],
    supports_emotion_strength=False,
    supports_cyrillic_text=True,
    supported_languages=_SUPPORTED_LANGUAGES,
)


class VoxCPM2Settings(BaseSettings):
    """VoxCPM2 remote-engine settings (main-adapter side only).

    Worker-side env vars (MODEL_DIR, OPTIMIZE, LOAD_DENOISER, ...) belong to
    the worker process - documented in docs/engines/voxcpm2/README.md, NOT here.

    Env vars (with TTS_VOXCPM2_ prefix):
        TTS_VOXCPM2_URL: Worker URL (default http://localhost:9882)
        TTS_VOXCPM2_TIMEOUT: HTTP timeout for /tts/clone in seconds (default 180)
        TTS_VOXCPM2_LOAD_TIMEOUT: HTTP timeout for /load in seconds (default 120)
        TTS_VOXCPM2_HEALTH_TIMEOUT: HTTP timeout for /health in seconds (default 2)
    """

    model_config = SettingsConfigDict(
        env_prefix="TTS_VOXCPM2_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "http://localhost:9882"
    # 300 s tolerates: cold torch.compile on first call (~30 s) + upstream's
    # retry_badcase loop (up to 3x infer time) + long inputs. Override via
    # TTS_VOXCPM2_TIMEOUT once you've seen steady-state RTF on your hardware.
    timeout: float = 300.0
    load_timeout: float = 240.0
    health_timeout: float = 2.0


@lru_cache
def get_voxcpm2_settings() -> VoxCPM2Settings:
    return VoxCPM2Settings()


_NOT_RUNNING_HINT = (
    "VoxCPM2 worker not reachable at {url}. Start it with one of:\n"
    "  make up                # if compose service adapter-tts-voxcpm2 is enabled\n"
    "  make run-voxcpm2       # local two-terminal dev\n"
    "See docs/engines/voxcpm2/README.md."
)


class VoxCPM2RemoteEngine:
    """VoxCPM2 engine that forwards requests to a separate worker process.

    Holds zero model state in this Python process - the worker owns everything
    GPU-related. Switching engines via /model/switch calls .unload() on the
    outgoing engine and .warmup() on the incoming one (which for this engine
    means POST /unload and POST /load on the worker respectively).

    Thread-safe via internal httpx.Client (which is already thread-safe).
    """

    def __init__(self, url: str | None = None, timeout: float | None = None):
        s = get_voxcpm2_settings()
        self._url = (url or s.url).rstrip("/")
        self._timeout = timeout if timeout is not None else s.timeout
        self._load_timeout = s.load_timeout
        self._health_timeout = s.health_timeout
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout, trust_env=False)
        return self._client

    # ----- lifecycle -----

    def warmup(self) -> None:
        if not self._is_healthy(timeout=self._health_timeout):
            raise RuntimeError(_NOT_RUNNING_HINT.format(url=self._url))

        with self._lock:
            try:
                resp = self._get_client().post(f"{self._url}/load", timeout=self._load_timeout)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise RuntimeError(f"VoxCPM2 worker /load failed: {e}") from e

    def unload(self) -> None:
        with self._lock:
            try:
                self._get_client().post(f"{self._url}/unload", timeout=self._load_timeout)
            except httpx.HTTPError as e:
                log.warning("VoxCPM2 worker /unload failed (continuing): %s", e)

    def reload(self, model_id: str) -> None:
        del model_id
        self.warmup()

    # ----- inference -----

    def synthesize(self, *args, **kwargs) -> bytes:
        raise NotImplementedError(
            "VoxCPM2 has no preset speakers. Use /tts/clone with a reference "
            "audio (optionally with emotion_text), or switch to TTS_ENGINE=qwen3."
        )

    def synthesize_batch(self, *args, **kwargs) -> list[bytes]:
        raise NotImplementedError("VoxCPM2 batch synthesis not supported. Use /tts/clone per item.")

    def synthesize_design(self, *args, **kwargs) -> bytes:
        raise NotImplementedError(
            "VoxCPM2 voice design is supported upstream but not exposed yet. "
            "Use TTS_ENGINE=qwen3 + VoiceDesign model."
        )

    def synthesize_clone(
        self,
        text: str,
        reference_audio: str | bytes,
        language: str = "Auto",
        reference_text: str | None = None,
        *,
        emotion_audio: bytes | str | None = None,
        emotion_text: str | None = None,
        emotion_vector: list[float] | None = None,
        emotion_alpha: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Forward /tts/clone to the worker as multipart form.

        emotion_audio + emotion_vector are silently dropped (API rejects them
        with 400 before they reach here; declared in signature for protocol parity).
        emotion_alpha IS forwarded so the worker's defense-in-depth gate rejects
        non-default values - a direct CLI call that passes alpha shouldn't
        silently get an alpha-less generation.
        """
        del emotion_audio, emotion_vector
        ref_bytes = _coerce_to_bytes(reference_audio)

        data: dict[str, str] = {
            "text": text,
            "language": language,
            "emotion_alpha": str(emotion_alpha),
        }
        if reference_text:
            data["reference_text"] = reference_text
        if emotion_text:
            data["emotion_text"] = emotion_text
        # Pass-through of generation tuning kwargs (cfg_value, inference_timesteps).
        for k in ("cfg_value", "inference_timesteps"):
            if k in kwargs and kwargs[k] is not None:
                data[k] = str(kwargs[k])

        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("reference_audio", ("ref.wav", ref_bytes, "audio/wav")),
        ]

        try:
            resp = self._get_client().post(
                f"{self._url}/tts/clone",
                data=data,
                files=files,
                timeout=self._timeout,
            )
        except httpx.ConnectError as e:
            raise RuntimeError(_NOT_RUNNING_HINT.format(url=self._url)) from e

        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"VoxCPM2 worker returned {resp.status_code}: {detail}")

        return resp.content

    # ----- protocol metadata -----

    def _is_healthy(self, timeout: float | None = None) -> bool:
        try:
            resp = self._get_client().get(f"{self._url}/health", timeout=timeout or self._health_timeout)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    @property
    def supports_cloning(self) -> bool:
        return True

    @property
    def supports_design(self) -> bool:
        return False

    @property
    def supports_custom_voice(self) -> bool:
        return False

    @property
    def supports_emotional_cloning(self) -> bool:
        return True

    @property
    def emotion_modes(self) -> set[str]:
        """Text-only - upstream has no audio-reference or vector mode."""
        return {"text"}

    @property
    def supports_emotion_strength(self) -> bool:
        """No emo_alpha equivalent. Routes 400-reject non-default emotion_alpha."""
        return False

    @property
    def supports_cyrillic_text(self) -> bool:
        """VoxCPM2 was trained on multilingual data including Russian (ru)."""
        return True

    @classmethod
    def is_installed(cls) -> bool:
        """Vendor venv DIR + checkpoint dir present. No worker ping (that's is_reachable).

        We check the .venv DIRECTORY (not its bin/python symlink) because the
        main adapter container bind-mounts vendor/ from the host, and the host
        venv's python symlink points at /usr/local/bin/python which only exists
        in the worker's image, not the main adapter's image. The directory
        existence is what `is_installed` actually means: the install ran on
        the host and the files are present.
        """
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent.parent
        venv_dir = repo_root / "vendor" / "voxcpm" / ".venv"
        if not venv_dir.is_dir():
            return False
        import os
        model_dir = os.environ.get("TTS_VOXCPM2_MODEL_DIR") or str(
            repo_root / "vendor" / "voxcpm" / "checkpoints" / "VoxCPM2"
        )
        return Path(model_dir).is_dir()

    def is_reachable(self) -> bool:
        return self._is_healthy()

    @property
    def is_loaded(self) -> bool:
        try:
            resp = self._get_client().get(f"{self._url}/health", timeout=self._health_timeout)
            return resp.status_code == 200 and bool(resp.json().get("model_loaded"))
        except Exception:
            return False

    @property
    def supported_languages(self) -> list[str]:
        return _SUPPORTED_LANGUAGES

    @property
    def generation_params(self) -> list[GenerationParam]:
        return _GENERATION_PARAMS

    def catalog_models(self) -> list[ModelInfo]:
        return [_MODEL_INFO]

    def available_models(self) -> list[ModelInfo]:
        return [_MODEL_INFO] if self._is_healthy() else []

    @property
    def engine_name(self) -> str:
        return "voxcpm2"

    @property
    def model_id(self) -> str:
        return _MODEL_ID

    @property
    def device(self) -> str:
        """Worker owns the GPU; surface its URL as a stand-in."""
        return self._url


def _coerce_to_bytes(audio: str | bytes) -> bytes:
    if isinstance(audio, bytes):
        return audio
    with open(audio, "rb") as f:
        return f.read()
