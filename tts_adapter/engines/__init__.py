"""TTS Engine implementations."""

import os

from ..engine import TTSEngine
from .qwen3 import Qwen3Engine

__all__ = ["Qwen3Engine", "create_engine"]

_DEFAULT_ENGINE = "qwen3"

_ENGINES: dict[str, type] = {
    "qwen3": Qwen3Engine,
}


def create_engine() -> TTSEngine:
    """Create engine instance based on TTS_ENGINE env var."""
    engine_name = os.getenv("TTS_ENGINE", _DEFAULT_ENGINE)
    engine_cls = _ENGINES.get(engine_name)
    if engine_cls is None:
        available = ", ".join(_ENGINES.keys())
        raise ValueError(f"Unknown engine: {engine_name}. Available: {available}")
    return engine_cls()
