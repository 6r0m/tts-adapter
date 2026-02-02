"""CLI entry point for TTS server."""

import uvicorn

from .config import get_settings


def main() -> None:
    """Run TTS server."""
    s = get_settings()
    uvicorn.run("tts_adapter.api:app", host=s.host, port=s.port, workers=1)


if __name__ == "__main__":
    main()
