"""IndexTTS2 remote engine - HTTP client for the isolated worker process.

The worker runs in vendor/index-tts/.venv (separate Python env, no shared deps with
the main adapter) and exposes /health, /load, /unload, /tts/clone. This engine
just forwards requests over HTTP. See docs/engines/indextts2/README.md for why
the two-process architecture is required (transformers/torch pin conflicts with
qwen-tts).
"""

import io
import logging
import threading
from functools import lru_cache

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..contract import GenerationParam, ModelInfo

# IndexTTS2's worker (scripts/indextts2/serve.py) accepts the same HF-transformers-style
# kwargs as qwen3 and forwards them to upstream.infer(...). Keep the list aligned with
# qwen3's so the UI feels consistent for users who switch between them.
_GENERATION_PARAMS: list[GenerationParam] = [
    GenerationParam(key="temperature", label="Temperature", type="number",
                    default=0.9, min=0.01, max=2.0, step=0.05,
                    help="Sampling randomness. Default: 0.9"),
    GenerationParam(key="top_k", label="Top-K", type="integer",
                    default=30, min=1, max=200, step=1,
                    help="Restrict sampling to top K tokens. Default: 30 (IndexTTS2 prefers tighter sampling)"),
    GenerationParam(key="top_p", label="Top-P", type="number",
                    default=0.8, min=0.1, max=1.0, step=0.05,
                    help="Nucleus sampling cutoff. Default: 0.8 (tighter than qwen3)"),
    GenerationParam(key="repetition_penalty", label="Repetition Penalty", type="number",
                    default=10.0, min=1.0, max=20.0, step=0.5,
                    help="Penalize repeated tokens. Default: 10.0 (much stronger than qwen3 - upstream IndexTTS2 default)"),
    GenerationParam(key="max_new_tokens", label="Max Tokens", type="integer",
                    default=1500, min=256, max=4096, step=256,
                    help="Cap on generated codec tokens. Default: 1500 (upstream IndexTTS2 default)"),
]

log = logging.getLogger(__name__)

_MODEL_ID = "IndexTeam/IndexTTS-2"

# IndexTTS2 upstream supports CN/EN/JP only. NO "Auto" - upstream's text
# normalizer routes any non-Latin text to the Chinese path (front.py:105),
# producing garbled output for Russian/Cyrillic. We hard-gate at the API
# boundary instead. See docs/engines/indextts2/README.md and
# vendor/index-tts/indextts/utils/front.py:use_chinese().
_SUPPORTED_LANGUAGES = ["Chinese", "English", "Japanese"]

_MODEL_INFO = ModelInfo(
    id=_MODEL_ID,
    name="IndexTTS-2",
    variant="Base+Emotion",
    supports_cloning=True,
    supports_emotional_cloning=True,
    supports_design=False,
    supports_custom_voice=False,
    emotion_modes=["audio", "text", "vector"],
    supports_emotion_strength=True,
    supports_cyrillic_text=False,
    supported_languages=_SUPPORTED_LANGUAGES,
)


class IndexTTS2Settings(BaseSettings):
    """IndexTTS2 remote-engine settings (main-adapter side only).

    Worker-side env vars (MODEL_DIR, USE_FP16, USE_CUDA_KERNEL, ...) belong to
    the worker process - documented in docs/engines/indextts2/README.md, NOT here.

    Env vars (with TTS_INDEXTTS2_ prefix):
        TTS_INDEXTTS2_URL: Worker URL (default http://localhost:9881)
        TTS_INDEXTTS2_TIMEOUT: HTTP timeout for /tts/clone in seconds (default 180)
        TTS_INDEXTTS2_LOAD_TIMEOUT: HTTP timeout for /load in seconds (default 120)
        TTS_INDEXTTS2_HEALTH_TIMEOUT: HTTP timeout for /health in seconds (default 2)
    """

    model_config = SettingsConfigDict(
        env_prefix="TTS_INDEXTTS2_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "http://localhost:9881"
    timeout: float = 180.0
    load_timeout: float = 120.0
    health_timeout: float = 2.0


@lru_cache
def get_indextts2_settings() -> IndexTTS2Settings:
    return IndexTTS2Settings()


_NOT_RUNNING_HINT = (
    "IndexTTS2 worker not reachable at {url}. Start it with one of:\n"
    "  make up                # if compose service adapter-tts-indextts2 is enabled\n"
    "  make run-indextts2     # local two-terminal dev (lands in Phase A.1/B)\n"
    "See docs/engines/indextts2/README.md."
)


class IndexTTS2RemoteEngine:
    """IndexTTS2 engine that forwards requests to a separate worker process.

    Holds zero model state in this Python process - the worker owns everything
    GPU-related. Switching engines via /model/switch calls .unload() on the
    outgoing engine and .warmup() on the incoming one (which for this engine
    means POST /unload and POST /load on the worker respectively).

    Thread-safe via internal httpx.Client (which is already thread-safe).
    """

    def __init__(self, url: str | None = None, timeout: float | None = None):
        s = get_indextts2_settings()
        self._url = (url or s.url).rstrip("/")
        self._timeout = timeout if timeout is not None else s.timeout
        self._load_timeout = s.load_timeout
        self._health_timeout = s.health_timeout
        # trust_env=False: worker is localhost by default, so don't honor
        # HTTP_PROXY / HTTPS_PROXY / SOCKS env vars (avoids needing socksio
        # just to talk to a process on the same machine).
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()  # serializes warmup/unload state changes

    def _get_client(self) -> httpx.Client:
        """Lazy client construction so tests can swap it before first use."""
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout, trust_env=False)
        return self._client

    # ----- lifecycle -----

    def warmup(self) -> None:
        """Verify worker is reachable, then ask it to load the model.

        Both /health and /load are idempotent on the worker side, so this is
        safe to call multiple times.
        """
        if not self._is_healthy(timeout=self._health_timeout):
            raise RuntimeError(_NOT_RUNNING_HINT.format(url=self._url))

        with self._lock:
            try:
                resp = self._get_client().post(f"{self._url}/load", timeout=self._load_timeout)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise RuntimeError(f"IndexTTS2 worker /load failed: {e}") from e

    def unload(self) -> None:
        """Best-effort: tell the worker to release VRAM.

        Used by cross-engine /model/switch before swapping to another engine.
        Failures are logged and swallowed - if the worker is already gone we're
        tearing down anyway.
        """
        with self._lock:
            try:
                self._get_client().post(f"{self._url}/unload", timeout=self._load_timeout)
            except httpx.HTTPError as e:
                log.warning("IndexTTS2 worker /unload failed (continuing): %s", e)

    def reload(self, model_id: str) -> None:
        """No-op alias to warmup() for protocol parity.

        IndexTTS2 has only one model, so model_id is ignored. Variant switching
        between Qwen3 sub-models doesn't apply here.
        """
        del model_id
        self.warmup()

    # ----- inference -----

    def synthesize(self, *args, **kwargs) -> bytes:
        raise NotImplementedError(
            "IndexTTS2 has no preset speakers. Use /tts/clone with a reference "
            "audio (optionally with emotion params), or switch to TTS_ENGINE=qwen3."
        )

    def synthesize_batch(self, *args, **kwargs) -> list[bytes]:
        raise NotImplementedError("IndexTTS2 batch synthesis not supported. Use /tts/clone per item.")

    def synthesize_design(self, *args, **kwargs) -> bytes:
        raise NotImplementedError(
            "IndexTTS2 does not support voice design. Use TTS_ENGINE=qwen3 + VoiceDesign model."
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
        """Forward /tts/clone to the worker as multipart form."""
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
        if emotion_vector is not None:
            data["emotion_vector"] = ",".join(str(x) for x in emotion_vector)
        # Generation kwargs that the route already filtered through _collect_gen_kwargs.
        for k in ("temperature", "top_k", "top_p", "repetition_penalty", "max_new_tokens"):
            if k in kwargs and kwargs[k] is not None:
                data[k] = str(kwargs[k])

        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("reference_audio", ("ref.wav", ref_bytes, "audio/wav")),
        ]
        if emotion_audio is not None:
            emo_bytes = _coerce_to_bytes(emotion_audio)
            files.append(("emotion_audio", ("emo.wav", emo_bytes, "audio/wav")))

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
            # Surface the worker's error verbatim so the user sees the real cause.
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"IndexTTS2 worker returned {resp.status_code}: {detail}")

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
        """Audio + text + 8-dim vector - upstream IndexTTS2 supports all 3."""
        return {"audio", "text", "vector"}

    @property
    def supports_emotion_strength(self) -> bool:
        """Upstream `emo_alpha` is real and meaningful in [0, 1]."""
        return True

    @property
    def supports_cyrillic_text(self) -> bool:
        """IndexTTS2 cannot. Upstream's normalizer routes any non-Latin text
        to the Chinese tokenizer (vendor/index-tts/indextts/utils/front.py:105),
        garbling Cyrillic. The /tts/clone route uses this flag to gate the
        text-script bypass (e.g. language=English + Cyrillic body)."""
        return False

    @classmethod
    def is_installed(cls) -> bool:
        """Vendor venv DIR + checkpoint dir present. No worker ping (that's is_reachable).

        Checks the .venv DIRECTORY (not its bin/python symlink) - same reason
        as VoxCPM2RemoteEngine.is_installed: the main adapter container bind-mounts
        vendor/ but doesn't have the host's symlink target /usr/local/bin/python.
        Directory presence is the actual signal that `make install-indextts2` ran.
        """
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent.parent
        venv_dir = repo_root / "vendor" / "index-tts" / ".venv"
        if not venv_dir.is_dir():
            return False
        import os
        model_dir = os.environ.get("TTS_INDEXTTS2_MODEL_DIR") or str(
            repo_root / "models" / "indextts2" / "IndexTTS-2"
        )
        return Path(model_dir).is_dir()

    def is_reachable(self) -> bool:
        """Worker /health responds within ~2 s."""
        return self._is_healthy()

    @property
    def is_loaded(self) -> bool:
        """Worker reports model_loaded=True. Best-effort - returns False on any error."""
        try:
            resp = self._get_client().get(f"{self._url}/health", timeout=self._health_timeout)
            return resp.status_code == 200 and bool(resp.json().get("model_loaded"))
        except Exception:
            return False

    @property
    def generation_params(self) -> list[GenerationParam]:
        return _GENERATION_PARAMS

    @property
    def supported_languages(self) -> list[str]:
        """Chinese, English, Japanese - what upstream actually supports.

        Russian/Cyrillic and other languages are silently mangled by upstream's
        normalizer + tokenizer + CN/EN/JP-trained acoustic model. The API gate
        rejects unsupported languages with 400 + hint to switch to qwen3.
        Notably NO 'Auto' - text-script-based auto-detect would still let
        Russian through because upstream's auto path itself is broken.
        """
        return _SUPPORTED_LANGUAGES

    def catalog_models(self) -> list[ModelInfo]:
        """Static IndexTTS-2 entry - always returned, regardless of worker health.

        Lets /model/switch route to indextts2 even when the worker is down,
        so warmup() can fail with 503 + actionable hint (rather than the
        request being rejected as 400 unknown model).
        """
        return [_MODEL_INFO]

    def available_models(self) -> list[ModelInfo]:
        """Return the single IndexTTS-2 entry, but only if the worker is reachable.

        That way GET /models naturally filters out a dead worker without any
        engine-name branching in the route.
        """
        return [_MODEL_INFO] if self._is_healthy() else []

    @property
    def engine_name(self) -> str:
        return "indextts2"

    @property
    def model_id(self) -> str:
        return _MODEL_ID

    @property
    def device(self) -> str:
        """Worker owns the GPU; surface its URL as a stand-in."""
        return self._url


def _coerce_to_bytes(audio: str | bytes) -> bytes:
    """Accept either raw WAV bytes or a path to a WAV file."""
    if isinstance(audio, bytes):
        return audio
    with open(audio, "rb") as f:
        return f.read()
