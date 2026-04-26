"""TTS Engine implementations."""

from ..config import get_settings
from ..engine import TTSEngine
from .indextts2 import IndexTTS2RemoteEngine
from .qwen3 import Qwen3Engine
from .voxcpm2 import VoxCPM2RemoteEngine

__all__ = ["IndexTTS2RemoteEngine", "Qwen3Engine", "VoxCPM2RemoteEngine", "create_engine"]

_ENGINES: dict[str, type] = {
    "qwen3": Qwen3Engine,
    "voxcpm2": VoxCPM2RemoteEngine,
    "indextts2": IndexTTS2RemoteEngine,
}


def create_engine() -> TTSEngine:
    """Create engine instance based on TTS_ENGINE setting."""
    engine_name = get_settings().engine
    engine_cls = _ENGINES.get(engine_name)
    if engine_cls is None:
        available = ", ".join(_ENGINES.keys())
        raise ValueError(f"Unknown engine: {engine_name}. Available: {available}")
    return engine_cls()
