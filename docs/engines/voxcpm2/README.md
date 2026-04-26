# VoxCPM2 Engine

> **Russian + 23 other languages, voice clone + text-tag emotion control, Apache-2.0.**
> This is the recommended engine for **Russian emotional cloning** - the gap that
> Qwen3 (no clone+emotion in one call) and IndexTTS2 (no Russian) cannot fill.

## Overview

[VoxCPM2](https://github.com/OpenBMB/VoxCPM) (OpenBMB, April 2026) is a 2B-parameter
tokenizer-free TTS model with multilingual voice cloning + style/emotion control
via inline text tags. License is straight Apache-2.0 (code + weights), suitable
for commercial use.

| Feature | Supported |
|---|:-:|
| Voice cloning from reference audio | yes |
| Emotion control via text description | **yes** (inline `(...)` prefix) |
| Emotion control via reference audio | no - use IndexTTS2 |
| Emotion control via 8-dim vector | no - use IndexTTS2 |
| Emotion intensity (`emotion_alpha`) | no - upstream has no equivalent |
| Preset speakers | no - use Qwen3 CustomVoice |
| Voice design (no reference) | yes upstream, NOT YET exposed in adapter |
| Batch generation | no |
| Cyrillic / Russian | **yes** (CV3-eval Russian WER 5.21) |

## Why a separate worker process

VoxCPM2 upstream pins `gradio>=6,<7`, `datasets>=3,<4`, `modelscope>=1.22.0`,
`funasr`, plus `torch>=2.5.0`. Our main adapter pins `qwen-tts` which depends on
`transformers==4.57.3` and a different torch line. **They cannot coexist in one
Python environment.** So VoxCPM2 runs in `vendor/voxcpm/.venv/` as its own
process, and the main adapter forwards requests over HTTP via `VoxCPM2RemoteEngine`.

```
client
  |
  v
main adapter (qwen-tts env, port 9880)
  |
  +--> Qwen3Engine (in-process)
  +--> IndexTTS2RemoteEngine -- HTTP --> IndexTTS2 worker (port 9881)
  +--> VoxCPM2RemoteEngine   -- HTTP --> VoxCPM2 worker (port 9882)
                                          (vendor/voxcpm/.venv)
                                          uses voxcpm.VoxCPM directly
```

## Install

```
make install-voxcpm2     # clones upstream, isolated venv, downloads checkpoints (~10 GB)
```

This will:
1. `git clone https://github.com/OpenBMB/VoxCPM vendor/voxcpm` (idempotent)
2. Create `vendor/voxcpm/.venv` with python 3.10 and `uv pip install -e .` plus
   worker deps (fastapi, uvicorn, python-multipart, soundfile, python-dotenv)
3. Download `openbmb/VoxCPM2` checkpoints to `vendor/voxcpm/checkpoints/VoxCPM2/`
   (model.safetensors ~5 GB + audiovae.pth + tokenizer)
4. Verify the host venv import works

Then in two terminals:

```
make run-voxcpm2     # terminal 1 - VoxCPM2 worker on :9882
make serve           # terminal 2 - main adapter on :9880
```

Switch engines at runtime via the API (or set `TTS_ENGINE=voxcpm2` in `.env` at boot):

```
curl -X POST http://localhost:9880/model/switch \
     -H 'content-type: application/json' \
     -d '{"model_id":"openbmb/VoxCPM2"}'
```

## Configuration

### Main adapter (TTS_VOXCPM2_*)

```
TTS_ENGINE=voxcpm2
TTS_VOXCPM2_URL=http://localhost:9882
TTS_VOXCPM2_TIMEOUT=180
```

### Worker process (TTS_VOXCPM2_*)

These vars belong to the worker process. The worker reads them from the same
`.env` (auto-loaded via python-dotenv).

| Var | Default | Description |
|---|---|---|
| `TTS_VOXCPM2_MODEL_DIR` | `vendor/voxcpm/checkpoints/VoxCPM2` | Local checkpoint directory |
| `TTS_VOXCPM2_OPTIMIZE` | `true` | Run `torch.compile` at constructor (~30 s cold start, faster steady-state) |
| `TTS_VOXCPM2_LOAD_DENOISER` | `false` | Load `iic/speech_zipenhancer_ans_multiloss_16k_base` denoiser. Default OFF to avoid surprise ModelScope download |
| `TTS_VOXCPM2_PORT` | `9882` | HTTP port the worker listens on |

GPU is selected by torch (default `cuda:0`). Override with `CUDA_VISIBLE_DEVICES`
if multi-GPU.

## Emotion control - inline text prefix

VoxCPM2 has only ONE emotion-control mode: a parenthesized natural-language tag
prefixed to the text. The worker prepends it for you.

```
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет, я очень рад тебя видеть' \
  -F 'language=Russian' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_text=very happy, cheerful, smiling tone' \
  --output happy.wav
```

The worker constructs `text = f"({emotion_text}){text}"` before calling
`model.generate(...)`.

### Style-tag language: English recommended

Phase 0 testing on Russian text + Russian reference voice confirmed **English
style tags work reliably** for the 4 tested emotions (very happy, very angry,
very afraid, very sad). Russian style tags also work, but are less consistent.

The adapter API accepts free-form `emotion_text` in any language. Our convention:
the Web UI maps user-visible Russian emotion labels to canonical English style
tags before sending to the API. CLI / curl users can pass either - English is
recommended.

### Suggested style tags

| Emotion | Recommended style tag |
|---|---|
| Happy | `very happy, cheerful, smiling tone` |
| Sad | `very sad, tired, restrained tone` |
| Angry | `very angry, sharp, irritated, high energy` |
| Afraid | `very afraid, trembling, scared` |
| Calm | `calm, warm, reassuring, slow pace` |
| Neutral | `natural, neutral tone` |

### Rejected modes

VoxCPM2 doesn't support `emotion_audio` or `emotion_vector`. Sending them
returns **400** with a hint to switch to IndexTTS2 (which has all 3 modes,
but is English/Chinese/Japanese only).

`emotion_alpha` is also rejected (anything other than the default 1.0) -
VoxCPM2 has no `emo_alpha` equivalent. Use the style tag itself to control
intensity (e.g. "slightly happy" vs "very happy").

## VoxCPM2 vs the other engines

| Engine | Russian | Clone + emotion | Best for |
|---|:-:|:-:|---|
| Qwen3 | yes | NO (model-arch limitation) | preset speakers, voice design, general clone |
| IndexTTS2 | NO (CN/EN/JP only) | yes (3 modes + alpha) | EN/CN/JP emotional cloning |
| **VoxCPM2** | **yes** | **yes (text-tag only)** | **Russian emotional cloning** |

## Output format

- **Sample rate:** 48 kHz (higher than Qwen3's 24 kHz and IndexTTS2's 22 kHz)
- **Format:** WAV float32

## Cold-start latency

The worker takes ~25 s to load the model on first `/load` (model.safetensors +
audiovae.pth into VRAM). With `TTS_VOXCPM2_OPTIMIZE=true` (default), the first
inference also runs `torch.compile`, adding another ~10-30 s. Subsequent
inferences are fast (RTF ~1.1 on RTX 4070 12 GB after warmup).

## Caveats

- **Russian quality is mid-tier.** Per upstream's CV3-eval table, Russian WER is
  5.21 (better than CosyVoice3 at 6.64, worse than Fish Audio S2 at 2.78). Real
  but not state-of-the-art. Run a few samples before committing to it.
- **Stochastic variation.** Upstream notes generation may vary - the model
  retries internally up to 3 times with `retry_badcase=True` (default). Some
  generations may take noticeably longer than others.
- **bf16 only.** No fp16 / int8 toggles. ~8 GB VRAM peak on RTX 4070 (well within 12 GB).
- **No batch.** One request at a time.
- **Voice design upstream-supported but not exposed.** Sending `/tts/design`
  returns NotImplementedError. Use Qwen3 VoiceDesign for now.

## Offline operation

After `make install-voxcpm2`, the worker constructs
`VoxCPM.from_pretrained(hf_model_id="<local_path>", load_denoiser=False)` with
explicit local paths - no HF Hub calls. With `HF_HUB_OFFLINE=1` set, no network
access required. The denoiser (which would otherwise pull from ModelScope on
first `/load`) is disabled by default.

For Russian emotional cloning, see also:

- [Qwen3 Engine docs](../qwen3/README.md) - for general Russian (no clone+emotion)
- [IndexTTS2 Engine docs](../indextts2/README.md) - for EN/CN/JP emotional cloning
