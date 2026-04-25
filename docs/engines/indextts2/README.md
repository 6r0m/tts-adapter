# IndexTTS2 Engine

## Overview

[IndexTTS2](https://github.com/index-tts/index-tts) (Bilibili, Sept 2025) is a zero-shot TTS model with **disentangled timbre and emotion conditioning** — the only adapter engine that combines voice cloning with emotion control. Use it when you need a specific cloned voice expressing a specific emotion (Qwen3-TTS cannot do both at once — see [qwen3 limitation](../qwen3/README.md#L33)).

| Feature | Supported |
|---------|:---------:|
| Voice cloning from reference audio | ✅ |
| Emotion control via reference audio | ✅ |
| Emotion control via text description | ✅ |
| Emotion control via 8-dim vector | ✅ |
| Preset speakers | ❌ — use Qwen3 CustomVoice |
| Voice design from description | ❌ — use Qwen3 VoiceDesign |
| Batch generation | ❌ |

## Install

The `indextts` package is **not on PyPI**. Install via the official `uv sync` flow:

```bash
# 1. Clone the official repo (use uv sync — pip install git+ is not supported upstream)
git clone https://github.com/index-tts/index-tts
cd index-tts && uv sync

# 2. Download checkpoints (~6 GB)
hf download IndexTeam/IndexTTS-2 --local-dir ~/.cache/tts-adapter/models/IndexTTS-2

# 3a. Either install indextts into the adapter env (verify no qwen-tts conflicts), OR
# 3b. Point the adapter at the cloned repo via TTS_INDEXTTS2_REPO_DIR (sys.path injection)
```

A `make download-indextts2` shortcut wraps step 2.

## Configuration

Set in `.env`:

```env
TTS_ENGINE=indextts2

TTS_INDEXTTS2_MODEL_DIR=~/.cache/tts-adapter/models/IndexTTS-2
# TTS_INDEXTTS2_REPO_DIR=/path/to/cloned/index-tts   # only if not pip-installed

TTS_INDEXTTS2_USE_FP16=true              # required on RTX 4070 12 GB
TTS_INDEXTTS2_USE_CUDA_KERNEL=false      # benchmark before enabling
TTS_INDEXTTS2_USE_DEEPSPEED=false        # may help or hurt depending on hardware
TTS_INDEXTTS2_USE_RANDOM=false           # random sampling reduces clone fidelity
TTS_INDEXTTS2_TRIM_SILENCE=false         # off by default to preserve emotional pauses

HF_HUB_OFFLINE=1                         # global, fully offline once checkpoints downloaded
```

GPU is selected via `CUDA_VISIBLE_DEVICES` — the upstream `IndexTTS2(...)` constructor takes no `device` argument.

## Emotion Input Modes

Pick **exactly one** per request. Mixing modes returns 400.

### 1. Emotion via reference audio

Copy timbre from `reference_audio` and emotion from `emotion_audio`:

```bash
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_audio=@happy_sample.wav' \
  -F 'emotion_alpha=0.9' \
  --output out.wav
```

### 2. Emotion via free-form text

```bash
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_text=very excited and warm' \
  -F 'emotion_alpha=0.6' \
  --output out.wav
```

### 3. Emotion via 8-dim vector

Order is fixed: `[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]`.

```bash
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_vector=0,0,0.8,0,0,0,0,0' \
  -F 'emotion_alpha=0.7' \
  --output sad.wav
```

### Recommended `emotion_alpha` ranges

| Mode | Recommended alpha | Note |
|---|---|---|
| `emotion_audio` | 0.8 – 1.0 | Strong emotion transfer |
| `emotion_text` | 0.4 – 0.7 | ~0.6 keeps speech natural (upstream guidance) |
| `emotion_vector` | 0.6 – 1.0 | Higher = more expressive |

## CLI

```bash
make tts-clone-emotion text="Привет мир" ref=voice.wav emotion-text="excited" alpha=0.6
```

Or directly:

```bash
PYTHONPATH=. uv run python scripts/indextts2/tts_clone_emotion.py \
    "Привет мир" --ref voice.wav --emotion-text "excited and warm" --alpha 0.6 --bench
```

`--bench` emits one-line JSON with VRAM / RTF for hardware benchmarking.

## Caveats

- **Russian is not guaranteed.** Upstream training is CN/EN/JP-focused. Run a few samples before committing to Russian production work.
- **Not a real-time target.** Expect RTF > 1× on consumer GPUs. Use Qwen3 if you need streaming-ish latency.
- **RTX 4070 12 GB:** start with `TTS_INDEXTTS2_USE_FP16=true`, `USE_CUDA_KERNEL=false`, `USE_DEEPSPEED=false`. Benchmark with `--bench` before enabling kernels/deepspeed.
- **No preset speakers.** `/tts` and `/tts/batch` and `/tts/design` raise `NotImplementedError` — use `/tts/clone`.
- **Emotion params on Qwen3 are rejected.** The API returns 400 if you send `emotion_*` while `TTS_ENGINE=qwen3` — never silently ignored.

## Offline Operation

Once `make download-indextts2` finishes, the engine constructs `IndexTTS2(cfg_path=<local>, model_dir=<local>)` with explicit local paths — no HuggingFace Hub calls. Combined with the global `HF_HUB_OFFLINE=1` in `.env.example`, this works fully offline.

The Docker compose mount (`~/.cache/huggingface`) plus the adapter's own `~/.cache/tts-adapter/models/` cover both engines without extra config.
