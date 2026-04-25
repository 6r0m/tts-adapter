"""IndexTTS2 engine implementation.

IndexTTS2 (Bilibili, Sept 2025) is a zero-shot TTS model with disentangled
timbre + emotion conditioning — the only adapter engine that combines voice
cloning with emotion control. See docs/engines/indextts2/README.md for
install, capabilities, and emotion modes.

The `indextts` package is NOT on PyPI. Install via the official `uv sync`
flow inside a cloned `index-tts` repo (see engine README) and either:
  - point `TTS_INDEXTTS2_REPO_DIR` at that clone (engine adds it to sys.path), OR
  - install into the same env as the adapter (verify no qwen-tts conflicts first).
"""

import io
import os
import sys
import threading
from functools import lru_cache
from pathlib import Path

import soundfile as sf
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..audio_utils import bytes_to_tempfile, trim_silence
from ..contract import ModelInfo
from ..gpu_utils import unload_gpu_model

_MODEL_ID = "IndexTeam/IndexTTS-2"
_DEFAULT_MODEL_DIR = str(Path.home() / ".cache" / "tts-adapter" / "models" / "IndexTTS-2")


class IndexTTS2Settings(BaseSettings):
    """IndexTTS2 engine settings.

    Env vars (with TTS_INDEXTTS2_ prefix):
        TTS_INDEXTTS2_MODEL_DIR: Local checkpoint directory
        TTS_INDEXTTS2_CFG_PATH: Path to config.yaml (default: {model_dir}/config.yaml)
        TTS_INDEXTTS2_REPO_DIR: Path to cloned index-tts repo (added to sys.path)
        TTS_INDEXTTS2_USE_FP16: FP16 inference (faster, lower VRAM, small quality loss)
        TTS_INDEXTTS2_USE_CUDA_KERNEL: Optional CUDA kernel speed path
        TTS_INDEXTTS2_USE_DEEPSPEED: Optional DeepSpeed inference (may help or hurt)
        TTS_INDEXTTS2_USE_RANDOM: Random sampling — disabled by default for clone fidelity
        TTS_INDEXTTS2_TRIM_SILENCE: Trim leading/trailing silence (off by default
            to preserve emotional breaths/pauses/expressive endings)
    """

    model_config = SettingsConfigDict(
        env_prefix="TTS_INDEXTTS2_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_dir: str = _DEFAULT_MODEL_DIR
    cfg_path: str | None = None
    repo_dir: str | None = None
    use_fp16: bool = True
    use_cuda_kernel: bool = False
    use_deepspeed: bool = False
    use_random: bool = False
    trim_silence: bool = False


@lru_cache
def get_indextts2_settings() -> IndexTTS2Settings:
    """Get cached IndexTTS2 settings instance."""
    return IndexTTS2Settings()


_INSTALL_HINT = (
    "IndexTTS2 (`indextts` package) not importable. Install via the official flow:\n"
    "  git clone https://github.com/index-tts/index-tts && cd index-tts && uv sync\n"
    "  hf download IndexTeam/IndexTTS-2 --local-dir ~/.cache/tts-adapter/models/IndexTTS-2\n"
    "Then either install indextts into the adapter env, or set\n"
    "  TTS_INDEXTTS2_REPO_DIR=/path/to/cloned/index-tts\n"
    "See docs/engines/indextts2/README.md."
)


class IndexTTS2Engine:
    """IndexTTS2 — voice cloning with disentangled emotion control.

    Supports `/tts/clone` only. Single text-to-speech (`synthesize`),
    batch (`synthesize_batch`), and voice design (`synthesize_design`)
    raise NotImplementedError — IndexTTS2 has no preset speakers.

    Thread-safe via a lock for GPU serialization (mirrors Qwen3 pattern).
    """

    def __init__(
        self,
        model_dir: str | None = None,
        cfg_path: str | None = None,
        repo_dir: str | None = None,
        use_fp16: bool | None = None,
        use_cuda_kernel: bool | None = None,
        use_deepspeed: bool | None = None,
        use_random: bool | None = None,
        trim_silence: bool | None = None,
    ):
        s = get_indextts2_settings()
        self._model_dir = model_dir or s.model_dir
        self._cfg_path = cfg_path or s.cfg_path or str(Path(self._model_dir) / "config.yaml")
        self._repo_dir = repo_dir if repo_dir is not None else s.repo_dir
        self._use_fp16 = s.use_fp16 if use_fp16 is None else use_fp16
        self._use_cuda_kernel = s.use_cuda_kernel if use_cuda_kernel is None else use_cuda_kernel
        self._use_deepspeed = s.use_deepspeed if use_deepspeed is None else use_deepspeed
        self._use_random = s.use_random if use_random is None else use_random
        self._trim_silence = s.trim_silence if trim_silence is None else trim_silence

        self._model = None
        self._lock = threading.Lock()

    def _import_indextts(self):
        """Lazy-import IndexTTS2, optionally adding repo_dir to sys.path."""
        if self._repo_dir and self._repo_dir not in sys.path:
            sys.path.insert(0, self._repo_dir)
        try:
            from indextts.infer_v2 import IndexTTS2
        except ImportError as e:
            raise RuntimeError(_INSTALL_HINT) from e
        return IndexTTS2

    def warmup(self) -> None:
        """Load model into memory.

        Constructs IndexTTS2 with explicit local paths — no HuggingFace Hub
        calls. Works fully offline once `make download-indextts2` has run.
        """
        if self._model is not None:
            return

        if not Path(self._cfg_path).exists():
            raise RuntimeError(
                f"IndexTTS2 config not found at {self._cfg_path}. "
                f"Run `make download-indextts2` and verify TTS_INDEXTTS2_MODEL_DIR."
            )

        IndexTTS2 = self._import_indextts()
        self._model = IndexTTS2(
            cfg_path=self._cfg_path,
            model_dir=self._model_dir,
            use_fp16=self._use_fp16,
            use_cuda_kernel=self._use_cuda_kernel,
            use_deepspeed=self._use_deepspeed,
        )

    def synthesize(self, text: str, language: str = "Auto", speaker: str = "default", instruct: str = "", **kwargs) -> bytes:
        raise NotImplementedError(
            "IndexTTS2 has no preset speakers. Use /tts/clone with a reference audio "
            "(optionally with emotion params), or switch to TTS_ENGINE=qwen3."
        )

    def synthesize_batch(self, texts: list[str], language: str = "Auto", speaker: str = "default", instruct: str = "", **kwargs) -> list[bytes]:
        raise NotImplementedError(
            "IndexTTS2 batch synthesis not supported. Use /tts/clone per item."
        )

    def synthesize_design(self, text: str, instruct: str, language: str = "Auto", **kwargs) -> bytes:
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
        """Clone voice and optionally apply emotion (audio / text / 8-dim vector)."""
        if self._model is None:
            self.warmup()

        # Speaker reference: bytes -> tempfile, or pass path through.
        # Emotion reference (if bytes): also via tempfile, otherwise None or path.
        # Use ExitStack-style nested context managers.
        from contextlib import ExitStack

        with ExitStack() as stack:
            if isinstance(reference_audio, bytes):
                spk_path = stack.enter_context(bytes_to_tempfile(reference_audio, suffix=".wav"))
            else:
                spk_path = reference_audio

            emo_path: str | None
            if isinstance(emotion_audio, bytes):
                emo_path = stack.enter_context(bytes_to_tempfile(emotion_audio, suffix=".wav"))
            elif isinstance(emotion_audio, str):
                emo_path = emotion_audio
            else:
                emo_path = None

            out_fd, out_path = _mkstemp_wav()
            os.close(out_fd)
            stack.callback(_silent_unlink, out_path)

            with self._lock:
                self._model.infer(
                    spk_audio_prompt=spk_path,
                    text=text,
                    output_path=out_path,
                    emo_audio_prompt=emo_path,
                    emo_text=emotion_text,
                    use_emo_text=emotion_text is not None,
                    emo_vector=emotion_vector,
                    emo_alpha=emotion_alpha,
                    use_random=self._use_random,
                )

            wav, sr = sf.read(out_path)

        if self._trim_silence:
            wav = trim_silence(wav, sr)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        return buf.getvalue()

    def reload(self, model_id: str) -> None:
        """Reload from a different model directory.

        For IndexTTS2 there's effectively one model — `model_id` is treated
        as a local checkpoint directory path here.
        """
        with self._lock:
            if self._model is not None:
                model_ref = self._model
                self._model = None
                unload_gpu_model(model_ref)

            self._model_dir = model_id
            self._cfg_path = str(Path(self._model_dir) / "config.yaml")

        self.warmup()

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

    def available_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id=_MODEL_ID,
                name="IndexTTS-2",
                variant="Base+Emotion",
                supports_cloning=True,
                supports_emotional_cloning=True,
                supports_design=False,
                supports_custom_voice=False,
            )
        ]

    @property
    def engine_name(self) -> str:
        return "indextts2"

    @property
    def model_id(self) -> str:
        return _MODEL_ID

    @property
    def device(self) -> str:
        """GPU is selected via CUDA_VISIBLE_DEVICES — upstream constructor takes no device arg."""
        return os.environ.get("CUDA_VISIBLE_DEVICES", "cuda:0")


def _mkstemp_wav():
    import tempfile
    return tempfile.mkstemp(suffix=".wav")


def _silent_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
