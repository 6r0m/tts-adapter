#!/usr/bin/env python3
"""IndexTTS2 voice cloning + emotion CLI.

Pick exactly ONE emotion mode (or none for plain clone):
  --emotion-audio EMO.wav         clone reference's voice, copy emo.wav's emotion
  --emotion-text "very excited"   clone voice + free-form emotion description
  --emotion-vector "0,0,0.8,0,0,0,0,0"
                                  8 floats: [happy,angry,sad,afraid,disgusted,
                                             melancholic,surprised,calm]

Usage:
    uv run python scripts/indextts2/tts_clone_emotion.py "Hello world" \\
        --ref voice.wav --emotion-text "excited and warm" --alpha 0.6 --bench

Requires TTS_ENGINE=indextts2 and a downloaded model
(see scripts/indextts2/download_model.py).
"""

import argparse
import json
import os
import sys
import time
import uuid

from dotenv import load_dotenv

load_dotenv()

from tts_adapter.engines import create_engine  # noqa: E402
from tts_adapter.engines.indextts2 import IndexTTS2Engine  # noqa: E402


def _parse_vector(raw: str) -> list[float]:
    parts = [float(x) for x in raw.split(",")]
    if len(parts) != 8:
        raise argparse.ArgumentTypeError(
            "emotion-vector must have exactly 8 floats: "
            "[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]"
        )
    return parts


def main() -> int:
    run_id = str(uuid.uuid4())

    parser = argparse.ArgumentParser(description="IndexTTS2 voice cloning + emotion")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--ref", required=True, help="Reference audio WAV (3-10 sec)")
    parser.add_argument("--ref-text", default="", help="Transcript of reference audio")
    parser.add_argument("-o", "--output", default=f"tmp/{run_id}/out.wav", help="Output WAV file")
    parser.add_argument("--language", default=os.environ.get("TTS_DEFAULT_LANGUAGE", "Auto"))

    emo = parser.add_mutually_exclusive_group()
    emo.add_argument("--emotion-audio", default=None, help="Emotion reference WAV")
    emo.add_argument("--emotion-text", default=None, help="Free-form emotion description")
    emo.add_argument("--emotion-vector", type=_parse_vector, default=None, help="8 comma-sep floats")

    parser.add_argument("--alpha", type=float, default=1.0, help="Emotion blend strength [0.0-1.0]")
    parser.add_argument("--bench", action="store_true", help="Print one-line JSON bench result")
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0:
        print("Error: --alpha must be in [0.0, 1.0]", file=sys.stderr)
        return 1
    if not os.path.exists(args.ref):
        print(f"Error: reference audio not found: {args.ref}", file=sys.stderr)
        return 1
    if args.emotion_audio and not os.path.exists(args.emotion_audio):
        print(f"Error: emotion audio not found: {args.emotion_audio}", file=sys.stderr)
        return 1

    engine = create_engine()
    if not isinstance(engine, IndexTTS2Engine):
        print(
            f"Error: expected IndexTTS2 engine, got {engine.engine_name}. "
            "Set TTS_ENGINE=indextts2 in .env.",
            file=sys.stderr,
        )
        return 1

    print(f"Text: {args.text[:50]}{'...' if len(args.text) > 50 else ''}")
    print(f"Ref:  {args.ref}" + (f" (transcript: {args.ref_text[:30]}...)" if args.ref_text else ""))
    if args.emotion_audio:
        print(f"Emo:  audio={args.emotion_audio}, alpha={args.alpha}")
    elif args.emotion_text:
        print(f"Emo:  text='{args.emotion_text}', alpha={args.alpha}")
    elif args.emotion_vector:
        print(f"Emo:  vector={args.emotion_vector}, alpha={args.alpha}")
    else:
        print("Emo:  (none — plain clone)")

    print("Loading model...")
    engine.warmup()

    print("Generating...")
    with open(args.ref, "rb") as f:
        ref_bytes = f.read()
    emo_bytes = None
    if args.emotion_audio:
        with open(args.emotion_audio, "rb") as f:
            emo_bytes = f.read()

    t0 = time.perf_counter()
    wav_bytes = engine.synthesize_clone(
        text=args.text,
        reference_audio=ref_bytes,
        language=args.language,
        reference_text=args.ref_text or None,
        emotion_audio=emo_bytes,
        emotion_text=args.emotion_text,
        emotion_vector=args.emotion_vector,
        emotion_alpha=args.alpha,
    )
    elapsed = time.perf_counter() - t0

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(wav_bytes)
    print(f"Saved: {args.output}")

    if args.bench:
        try:
            import io

            import soundfile as sf

            wav, sr = sf.read(io.BytesIO(wav_bytes))
            audio_seconds = len(wav) / sr
        except Exception:
            audio_seconds = 0.0

        cuda_max_mb = 0
        try:
            import torch

            if torch.cuda.is_available():
                cuda_max_mb = int(torch.cuda.max_memory_allocated() / (1024 * 1024))
        except Exception:
            pass

        bench = {
            "engine": "indextts2",
            "text_chars": len(args.text),
            "audio_seconds": round(audio_seconds, 2),
            "elapsed_seconds": round(elapsed, 2),
            "rtf": round(elapsed / audio_seconds, 2) if audio_seconds > 0 else None,
            "cuda_max_memory_mb": cuda_max_mb,
        }
        print(json.dumps(bench))

    return 0


if __name__ == "__main__":
    sys.exit(main())
