#!/usr/bin/env python3
"""Test different generation parameters for voice cloning quality."""

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import torch
from qwen_tts import Qwen3TTSModel

TEXT = "Знаете, что общего между модным барбершопом и парижским кафе? Русские казаки!"
REF_AUDIO = "tmp/test_clone.wav"
REF_TEXT = "Да, это радует. А то, что уже третий день чего-то вроде как бы, как бы тут непонятно, что получится или нет, непонятно, в чем проблем."
LANGUAGE = "Russian"
OUTPUT_DIR = Path("tmp/clone_params_test")

# Different parameter combinations to test
PARAMS = {
    "default": {},
    "temp_07": {"temperature": 0.7},
    "temp_05": {"temperature": 0.5},
    "rep_11": {"repetition_penalty": 1.1},
    "rep_12": {"repetition_penalty": 1.2},
    "temp_07_rep_11": {"temperature": 0.7, "repetition_penalty": 1.1},
    "top_p_08": {"top_p": 0.8},
    "combo": {"temperature": 0.7, "top_p": 0.85, "repetition_penalty": 1.1},
}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading model...")
    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )

    print(f"Text: {TEXT[:50]}...")
    print(f"Reference: {REF_AUDIO}")
    print(f"Output dir: {OUTPUT_DIR}")
    print()

    for name, params in PARAMS.items():
        print(f"Generating: {name} {params or '(defaults)'}")

        wav, sr = model.generate_voice_clone(
            text=TEXT,
            language=LANGUAGE,
            ref_audio=REF_AUDIO,
            ref_text=REF_TEXT,
            **params,
        )

        output_path = OUTPUT_DIR / f"{name}.wav"
        import soundfile as sf
        import numpy as np
        # Ensure numpy array and correct shape
        if hasattr(wav, 'cpu'):
            wav = wav.cpu().numpy()
        wav = np.asarray(wav).flatten()
        sf.write(str(output_path), wav, sr, format='WAV', subtype='PCM_16')
        print(f"  Saved: {output_path}")

    print()
    print("Done! Compare files in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
