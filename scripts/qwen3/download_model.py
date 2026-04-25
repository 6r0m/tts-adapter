#!/usr/bin/env python3
"""Download Qwen3-TTS model for offline use.

Usage:
    uv run python scripts/qwen3/download_model.py
    uv run python scripts/qwen3/download_model.py --model Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

Downloads to ./models/qwen3/<name>/ (repo-local convention, gitignored).
Override with --dir if you prefer ~/.cache/tts-adapter/models/<name>/ (still
accepted by the engine settings - see docs).

After download, set TTS_QWEN3_MODEL_PATH in .env to the printed path.
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
# Repo-local default (mirrors A1111/ComfyUI/llama.cpp). The legacy
# ~/.cache/tts-adapter/models/ is still accepted via --dir or by setting
# TTS_QWEN3_MODEL_PATH directly; it triggers a one-shot legacy warning at
# server startup (Phase A.2d).
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "qwen3"


def main():
    parser = argparse.ArgumentParser(description="Download Qwen3-TTS model for offline use")
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

    # Prefer `hf` (modern huggingface_hub) but fall back to legacy `huggingface-cli`.
    for binary, subcmd in (("hf", ["download"]), ("huggingface-cli", ["download"])):
        try:
            cmd = [binary, *subcmd, model_id, "--local-dir", str(local_dir)]
            subprocess.run(cmd, check=True)
            break
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as e:
            print(f"Error: download failed with code {e.returncode}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: neither `hf` nor `huggingface-cli` found", file=sys.stderr)
        print("Install with: uv pip install 'huggingface-hub[cli]'", file=sys.stderr)
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
