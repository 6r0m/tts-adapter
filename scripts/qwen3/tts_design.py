#!/usr/bin/env python3
"""Voice design TTS CLI - generate speech with designed voice from description.

Usage:
    uv run python scripts/qwen3/tts_design.py "Hello world" --instruct "Young female, warm, friendly"

Requires VoiceDesign model:
    TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
"""

import argparse
import os
import uuid

# Load .env before any HuggingFace imports
from dotenv import load_dotenv
load_dotenv()

from tts_adapter.engines import create_engine
from tts_adapter.engines.qwen3 import Qwen3Engine
from tts_adapter.config import get_settings


def main():
    settings = get_settings()
    run_id = str(uuid.uuid4())

    parser = argparse.ArgumentParser(description="Generate speech with designed voice")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--instruct", required=True, help="Voice description (e.g. 'Young female, warm, friendly')")
    parser.add_argument("-o", "--output", default=f"tmp/{run_id}/out.wav", help="Output WAV file")
    parser.add_argument("--language", default=settings.default_language or "Russian", help="Language")
    args = parser.parse_args()

    print(f"Text: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"Instruct: {args.instruct[:50]}{'...' if len(args.instruct) > 50 else ''}")
    print(f"Language: {args.language}")

    engine = create_engine()

    if not isinstance(engine, Qwen3Engine):
        print("Error: Voice design only supported by Qwen3 engine")
        return 1

    if not engine.supports_design:
        print("Error: Voice design requires VoiceDesign model")
        print("Set TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign in .env")
        return 1

    print("Loading model...")
    engine.warmup()

    print("Generating...")
    wav_bytes = engine.synthesize_design(
        text=args.text,
        instruct=args.instruct,
        language=args.language,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(wav_bytes)

    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
