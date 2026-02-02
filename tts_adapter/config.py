"""Configuration via environment variables (12-factor style)."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """TTS adapter settings loaded from environment."""

    # Model settings
    model_id: str = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    device: str = "cuda:0"
    dtype: str = "bfloat16"

    # Defaults
    default_speaker: str = "Ryan"
    default_language: str = "Russian"

    # Server
    host: str = "0.0.0.0"
    port: int = 9880

    class Config:
        env_prefix = "TTS_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
