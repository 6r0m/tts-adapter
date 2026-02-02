#!/usr/bin/env python3
"""Download Qwen3-TTS model for offline use.

Usage:
    uv run python scripts/download_model.py
    uv run python scripts/download_model.py --model Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

Downloads model to ~/.cache/tts-adapter/models/<model-name>/
After download, set TTS_QWEN3_MODEL_PATH in .env to the printed path.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
CACHE_DIR = Path.home() / ".cache" / "tts-adapter" / "models"


def main():
    parser = argparse.ArgumentParser(description="Download Qwen3-TTS model for offline use")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HuggingFace model ID (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    model_id = args.model
    # Convert "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice" to "Qwen3-TTS-12Hz-1.7B-CustomVoice"
    model_name = model_id.split("/")[-1]
    local_dir = CACHE_DIR / model_name

    print(f"Downloading: {model_id}")
    print(f"To: {local_dir}")
    print()

    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Use huggingface-cli download
    cmd = [
        "huggingface-cli",
        "download",
        model_id,
        "--local-dir",
        str(local_dir),
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("Error: huggingface-cli not found")
        print("Install with: pip install huggingface-hub")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: Download failed with code {e.returncode}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Download complete!")
    print()
    print("Add to your .env file:")
    print(f"  TTS_QWEN3_MODEL_PATH={local_dir}")
    print()
    print("Then set HF_HUB_OFFLINE=1 for fully offline operation:")
    print("  HF_HUB_OFFLINE=1")
    print("=" * 60)


if __name__ == "__main__":
    main()
