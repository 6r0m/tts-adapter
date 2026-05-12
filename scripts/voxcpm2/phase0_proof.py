"""Phase 0 proof: Russian voice clone + emotion control on VoxCPM2.

Run with the vendor voxcpm venv (has the `voxcpm` package):
  cd vendor/voxcpm && env -u VIRTUAL_ENV .venv/bin/python \
      ../../scripts/voxcpm2/phase0_proof.py --ref <wav>

Generates:
  - 3 user-acceptance deliverables at tmp/output/test_clone_very_{afraid,happy,angry}.wav
  - Optional: full proof matrix (5 emotions x 2 style-langs x 3 repeats) when --full

Pass-criteria scoring is manual (listen to outputs); this script logs metrics only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from voxcpm import VoxCPM


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / "vendor" / "voxcpm" / "checkpoints" / "VoxCPM2"

REFERENCE_TEXT = "Привет, я очень рад тебя видеть."

DELIVERABLES = [
    ("very_afraid", "very afraid, trembling, scared"),
    ("very_happy",  "very happy, cheerful, smiling tone"),
    ("very_angry",  "very angry, sharp, irritated, high energy"),
]

# Full proof matrix: 5 emotions x 2 style-langs (EN/RU)
EMOTIONS_EN = [
    ("neutral", "natural, neutral tone"),
    ("happy",   "very happy, cheerful, warm tone"),
    ("angry",   "very angry, sharp, irritated tone"),
    ("sad",     "very sad, tired, restrained tone"),
    ("calm",    "calm, warm, reassuring, slow pace"),
]
EMOTIONS_RU = [
    ("neutral", "естественный, нейтральный тон"),
    ("happy",   "очень радостный, тёплый тон"),
    ("angry",   "очень злой, резкий, раздражённый"),
    ("sad",     "очень грустный, усталый, сдержанный"),
    ("calm",    "спокойный, тёплый, уверенный, медленный темп"),
]


def env_info() -> dict:
    return {
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_total_mb": torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            if torch.cuda.is_available() else None,
    }


def gen_one(model: VoxCPM, sample_rate: int, *, ref_path: str, style: str, text: str,
            out_path: Path, cfg_value: float = 2.0) -> dict:
    """Generate one clip; return metrics dict."""
    full_text = f"({style}){text}"
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    wav = model.generate(
        text=full_text,
        reference_wav_path=ref_path,
        cfg_value=cfg_value,
        inference_timesteps=10,
        normalize=False,
    )
    elapsed = time.perf_counter() - t0
    audio_seconds = len(wav) / sample_rate if hasattr(wav, "__len__") else None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), np.asarray(wav, dtype=np.float32), sample_rate)
    peak_mb = torch.cuda.max_memory_allocated() // (1024 * 1024) if torch.cuda.is_available() else None
    rtf = (elapsed / audio_seconds) if audio_seconds else None
    return {
        "out": str(out_path),
        "style_prompt": style,
        "text": text,
        "elapsed_s": round(elapsed, 3),
        "audio_s": round(audio_seconds, 3) if audio_seconds else None,
        "rtf": round(rtf, 3) if rtf else None,
        "peak_vram_mb": peak_mb,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="Reference WAV path")
    ap.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR),
                    help=f"Local VoxCPM2 checkpoint dir (default: {DEFAULT_MODEL_DIR})")
    ap.add_argument("--out-deliverables", default="tmp/output", help="3-file deliverable dir")
    ap.add_argument("--out-matrix", default="tmp/output/proof_matrix",
                    help="Full matrix output dir (used with --full)")
    ap.add_argument("--full", action="store_true", help="Also run 5x2x3 proof matrix")
    ap.add_argument("--repeat", type=int, default=3, help="Repeats per matrix cell")
    args = ap.parse_args()

    ref = Path(args.ref).resolve()
    if not ref.exists():
        print(f"FATAL: reference WAV not found: {ref}", file=sys.stderr)
        return 1

    print("=== ENV ===")
    info = env_info()
    print(json.dumps(info, indent=2))

    print(f"\n=== LOAD VoxCPM2 from {args.model_dir} ===")
    t0 = time.perf_counter()
    # Pass local path directly as hf_model_id (constructor handles os.path.isdir branch)
    model = VoxCPM.from_pretrained(
        hf_model_id=str(Path(args.model_dir).resolve()),
        load_denoiser=False,   # avoid surprise ModelScope download
        optimize=False,        # skip ~30s torch.compile during proof
    )
    sample_rate = model.tts_model.sample_rate
    print(f"loaded in {time.perf_counter()-t0:.1f}s; sample_rate={sample_rate} Hz")

    print(f"\n=== USER DELIVERABLES (3 files at {args.out_deliverables}) ===")
    deliverables_dir = Path(args.out_deliverables)
    runs = []
    for tag, style in DELIVERABLES:
        out = deliverables_dir / f"test_clone_{tag}.wav"
        m = gen_one(model, sample_rate, ref_path=str(ref), style=style,
                    text=REFERENCE_TEXT, out_path=out)
        print(f"  {tag:14s} -> {m['out']}  ({m['elapsed_s']}s, {m['audio_s']}s audio, "
              f"RTF={m['rtf']}, VRAM={m['peak_vram_mb']} MB)")
        runs.append({"phase": "deliverable", "tag": tag, **m})

    if args.full:
        print(f"\n=== FULL PROOF MATRIX (5 emotions x 2 langs x {args.repeat} repeats) "
              f"into {args.out_matrix} ===")
        matrix_dir = Path(args.out_matrix)
        for lang, emo_list in (("EN", EMOTIONS_EN), ("RU", EMOTIONS_RU)):
            for tag, style in emo_list:
                for r in range(args.repeat):
                    out = matrix_dir / f"{tag}_{lang}_r{r+1}.wav"
                    m = gen_one(model, sample_rate, ref_path=str(ref), style=style,
                                text=REFERENCE_TEXT, out_path=out)
                    print(f"  {tag:8s} {lang} r{r+1} -> {out.name}  "
                          f"({m['elapsed_s']}s, RTF={m['rtf']}, VRAM={m['peak_vram_mb']} MB)")
                    runs.append({"phase": "matrix", "lang": lang, "tag": tag, "repeat": r + 1, **m})

    # Summary
    metrics_path = Path(args.out_deliverables) / "phase0_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps({"env": info, "runs": runs}, indent=2))
    rtfs = [r["rtf"] for r in runs if r["rtf"]]
    vrams = [r["peak_vram_mb"] for r in runs if r["peak_vram_mb"]]
    print(f"\n=== SUMMARY ===")
    print(f"runs:        {len(runs)}")
    if rtfs:
        print(f"RTF min/avg/max:  {min(rtfs):.2f} / {sum(rtfs)/len(rtfs):.2f} / {max(rtfs):.2f}")
    if vrams:
        print(f"VRAM peak (MB):   {max(vrams)}  (gate: < 11000 on 4070 12GB)")
    print(f"metrics:     {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
