#!/usr/bin/env python3
"""Simple TTS CLI - generate speech from text.

Usage:
    uv run python scripts/tts.py "Hello world"
    uv run python scripts/tts.py "Hello world" -o output.wav
    uv run python scripts/tts.py "Hello world" --speaker Ryan --language English
"""

import argparse
import os
import uuid

# Load .env before any HuggingFace imports
from dotenv import load_dotenv
load_dotenv()

from tts_adapter.engines import create_engine
from tts_adapter.config import get_settings


def main():
    settings = get_settings()
    run_id = str(uuid.uuid4())

    parser = argparse.ArgumentParser(description="Generate speech from text")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("-o", "--output", default=f"tmp/{run_id}/out.wav", help="Output WAV file")
    parser.add_argument("--speaker", default=settings.default_speaker or "Serena", help="Speaker")
    parser.add_argument("--language", default=settings.default_language or "Russian", help="Language")
    parser.add_argument("--instruct", default="", help="Style instruction")
    args = parser.parse_args()

    print(f"Text: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"Speaker: {args.speaker}, Language: {args.language}")
    if args.instruct:
        print(f"Instruct: {args.instruct}")

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

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(wav_bytes)

    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
