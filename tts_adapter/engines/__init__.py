"""TTS Engine implementations."""

from ..config import get_settings
from ..engine import TTSEngine
from .qwen3 import Qwen3Engine

__all__ = ["Qwen3Engine", "create_engine"]

_ENGINES: dict[str, type] = {
    "qwen3": Qwen3Engine,
}


def create_engine() -> TTSEngine:
    """Create engine instance based on TTS_ENGINE setting."""
    settings = get_settings()
    engine_cls = _ENGINES.get(settings.engine)
    if engine_cls is None:
        available = ", ".join(_ENGINES.keys())
        raise ValueError(f"Unknown engine: {settings.engine}. Available: {available}")
    return engine_cls()
