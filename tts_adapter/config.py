"""Configuration via environment variables (12-factor style)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TTS adapter settings loaded from environment.

    Env vars (with TTS_ prefix):
        TTS_DEFAULT_SPEAKER: Default speaker (optional)
        TTS_DEFAULT_LANGUAGE: Default language (optional)
        TTS_HOST: Server host (default: 0.0.0.0)
        TTS_PORT: Server port (default: 9880)

    Engine selection (TTS_ENGINE) is handled by the factory.
    Engine-specific config is handled by each engine.
    """

    model_config = SettingsConfigDict(
        env_prefix="TTS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Optional - error at request time if needed but not set
    default_speaker: str | None = None
    default_language: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 9880


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
