#!/usr/bin/env python3
"""Voice cloning TTS CLI - generate speech from text using a reference voice.

Usage:
    uv run python scripts/qwen3/tts_clone.py "Hello world" --ref voice_sample.wav
    uv run python scripts/qwen3/tts_clone.py "Hello world" --ref voice_sample.wav --ref-text "Original text"

Requires Base model (not CustomVoice):
    TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base
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

    parser = argparse.ArgumentParser(description="Generate speech by cloning voice")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--ref", required=True, help="Reference audio WAV (3-10 sec)")
    parser.add_argument("--ref-text", default="", help="Transcript of reference audio (improves quality)")
    parser.add_argument("-o", "--output", default=f"tmp/{run_id}/out.wav", help="Output WAV file")
    parser.add_argument("--language", default=settings.default_language or "Russian", help="Language")
    args = parser.parse_args()

    if not os.path.exists(args.ref):
        print(f"Error: Reference audio not found: {args.ref}")
        return 1

    print(f"Text: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"Reference: {args.ref}")
    if args.ref_text:
        print(f"Ref text: {args.ref_text[:30]}{'...' if len(args.ref_text) > 30 else ''}")
    else:
        print("Ref text: (none - using x_vector_only mode)")
    print(f"Language: {args.language}")

    engine = create_engine()

    if not isinstance(engine, Qwen3Engine):
        print("Error: Voice cloning only supported by Qwen3 engine")
        return 1

    if not engine.supports_cloning:
        print("Error: Voice cloning requires Base model")
        print("Set TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base in .env")
        return 1

    print("Loading model...")
    engine.warmup()

    print("Generating...")
    wav_bytes = engine.synthesize_clone(
        text=args.text,
        reference_audio=args.ref,
        language=args.language,
        reference_text=args.ref_text if args.ref_text else None,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(wav_bytes)

    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
