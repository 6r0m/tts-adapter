#!/usr/bin/env python3
"""Simple TTS CLI - generate speech from text.

Usage:
    uv run python scripts/tts.py "Hello world"
    uv run python scripts/tts.py "Hello world" -o output.wav
    uv run python scripts/tts.py "Hello world" --speaker Ryan --language English
"""

import argparse
import os

# Load .env before any HuggingFace imports
from dotenv import load_dotenv
load_dotenv()

from tts_adapter.engines import create_engine
from tts_adapter.config import get_settings


def main():
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Generate speech from text")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("-o", "--output", default="/tmp/tts_out.wav", help="Output WAV file")
    parser.add_argument("--speaker", default=settings.default_speaker or "Serena", help="Speaker")
    parser.add_argument("--language", default=settings.default_language or "Russian", help="Language")
    parser.add_argument("--instruct", default="", help="Style instruction")
    args = parser.parse_args()

    print(f"Text: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"Speaker: {args.speaker}, Language: {args.language}")

    engine = create_engine()
    print("Loading model...")
    engine.warmup()

    print("Generating...")
    wav_bytes = engine.synthesize(
        text=args.text,
        language=args.language,
        speaker=args.speaker,
        instruct=args.instruct,
    )

    with open(args.output, "wb") as f:
        f.write(wav_bytes)

    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
