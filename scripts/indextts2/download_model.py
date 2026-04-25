#!/usr/bin/env python3
"""Download IndexTTS-2 checkpoints for offline use.

Usage:
    uv run python scripts/indextts2/download_model.py
    uv run python scripts/indextts2/download_model.py --dir /custom/path

Mirrors scripts/qwen3/download_model.py - same destination convention
(~/.cache/tts-adapter/models/<name>/) so .env paths stay symmetric.
After download, set TTS_INDEXTTS2_MODEL_DIR in .env to the printed path.
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "IndexTeam/IndexTTS-2"
CACHE_DIR = Path.home() / ".cache" / "tts-adapter" / "models"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download IndexTTS-2 checkpoints for offline use")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HuggingFace model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help=f"Local directory (default: {CACHE_DIR}/<model-name>)",
    )
    args = parser.parse_args()

    model_id = args.model
    model_name = model_id.split("/")[-1]
    local_dir = Path(args.dir) if args.dir else CACHE_DIR / model_name

    print(f"Downloading: {model_id}")
    print(f"To:          {local_dir}")
    print()

    local_dir.parent.mkdir(parents=True, exist_ok=True)

    # Prefer `hf` (huggingface_hub >= 0.20) but fall back to legacy `huggingface-cli`.
    for binary, subcmd in (("hf", ["download"]), ("huggingface-cli", ["download"])):
        try:
            cmd = [binary, *subcmd, model_id, "--local-dir", str(local_dir)]
            subprocess.run(cmd, check=True)
            break
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as e:
            print(f"Error: download failed with code {e.returncode}", file=sys.stderr)
            return 1
    else:
        print("Error: neither `hf` nor `huggingface-cli` found", file=sys.stderr)
        print("Install with: uv pip install 'huggingface-hub[cli]'", file=sys.stderr)
        return 1

    print()
    print("=" * 60)
    print("Download complete!")
    print()
    print("Add to your .env:")
    print(f"  TTS_INDEXTTS2_MODEL_DIR={local_dir}")
    print("  TTS_ENGINE=indextts2")
    print()
    print("Then set HF_HUB_OFFLINE=1 for fully offline operation:")
    print("  HF_HUB_OFFLINE=1")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
