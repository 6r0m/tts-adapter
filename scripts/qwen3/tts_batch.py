#!/usr/bin/env python3
"""CLI batch runner for TTS generation.

Usage:
    uv run python scripts/tts_batch.py --in input.jsonl --outdir out/

Input JSONL format:
    {"id": "001", "text": "Hello world"}
    {"id": "002", "text": "Second phrase"}
"""

import argparse
import json
import os

from tts_adapter.engines import create_engine


def main():
    parser = argparse.ArgumentParser(description="Batch TTS generation")
    parser.add_argument("--in", dest="inp", required=True, help="Input JSONL file")
    parser.add_argument("--outdir", required=True, help="Output directory for WAV files")
    parser.add_argument("--language", default="Russian", help="Language (default: Russian)")
    parser.add_argument("--speaker", default="Ryan", help="Speaker (default: Ryan)")
    parser.add_argument("--instruct", default="", help="Style instruction")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size (default: 8)")
    args = parser.parse_args()

    # Read input
    items = []
    with open(args.inp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    if not items:
        print("No items found in input file")
        return

    print(f"Loaded {len(items)} items")

    # Initialize engine
    engine = create_engine()
    print("Warming up model...")
    engine.warmup()
    print("Model ready")

    # Create output directory
    os.makedirs(args.outdir, exist_ok=True)

    # Process in batches
    total = len(items)
    processed = 0

    for i in range(0, total, args.batch_size):
        batch = items[i : i + args.batch_size]
        texts = [item["text"] for item in batch]
        ids = [str(item.get("id", i + j)) for j, item in enumerate(batch)]

        print(f"Processing batch {i // args.batch_size + 1} ({len(batch)} items)...")

        wav_bytes_list = engine.synthesize_batch(
            texts=texts,
            language=args.language,
            speaker=args.speaker,
            instruct=args.instruct,
        )

        for item_id, wav_bytes in zip(ids, wav_bytes_list):
            out_path = os.path.join(args.outdir, f"{item_id}.wav")
            with open(out_path, "wb") as f:
                f.write(wav_bytes)
            processed += 1

        print(f"  Done: {processed}/{total}")

    print(f"Completed. Output in: {args.outdir}")


if __name__ == "__main__":
    main()
