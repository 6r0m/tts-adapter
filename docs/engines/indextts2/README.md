# IndexTTS2 Engine

> **Status: WIP - isolated worker architecture in progress.**
> Source of truth: [todo/engine_install_and_switch.md](../../../todo/engine_install_and_switch.md) Phase A.1.
> The current `tts_adapter/engines/indextts2.py` (in-process) is rejected and will be rewritten as `IndexTTS2RemoteEngine` (HTTP forwarder).

## Overview

[IndexTTS2](https://github.com/index-tts/index-tts) (Bilibili, Sept 2025) is a zero-shot TTS model with disentangled timbre + emotion conditioning.

**Planned use case:** clone a specific voice and apply emotion control (audio / text / 8-dim vector) once the isolated worker lands. Qwen3-TTS cannot do both at once - see the [qwen3 limitation](../qwen3/README.md). Until Phase A.1 + Phase B ship, this engine is not runnable.

| Feature | Supported |
|---------|:---------:|
| Voice cloning from reference audio | yes |
| Emotion control via reference audio | yes |
| Emotion control via text description | yes |
| Emotion control via 8-dim vector | yes |
| Preset speakers | no - use Qwen3 CustomVoice |
| Voice design from description | no - use Qwen3 VoiceDesign |
| Batch generation | no |

## Why a separate worker process

IndexTTS2 upstream pins `transformers==4.52.1`, `torch==2.8.*`, optional `deepspeed==0.17.1`. Our adapter pins `qwen-tts` which requires `transformers==4.57.3`. **They cannot coexist in one Python environment.** So IndexTTS2 runs as its own process in `vendor/index-tts/.venv/`, and the main adapter forwards requests over HTTP via `IndexTTS2RemoteEngine`.

Architecture:

```
client
  |
  v
main adapter (qwen env, port 9880)
  |
  +--> Qwen3Engine (in-process)
  |
  +--> IndexTTS2RemoteEngine -- HTTP --> IndexTTS2 worker (port 9881)
                                         (vendor/index-tts/.venv)
                                         uses indextts.infer_v2.IndexTTS2 directly
```

## Install (planned, Phase B)

> **Not implemented yet.** Block below describes the target UX once Phase A.1 + Phase B land. Until then, `make run-indextts2` is a stub that exits with a "not implemented" message, and the download script still defaults to `~/.cache/tts-adapter/models/IndexTTS-2/` (Phase A.2 flips that default to repo-local).

```
make install-indextts2     # clones upstream, runs uv sync in vendor venv, downloads weights
```

This will:
1. `git clone https://github.com/index-tts/index-tts vendor/index-tts` (idempotent)
2. `cd vendor/index-tts && uv sync` (creates isolated `.venv`)
3. Download checkpoints (about 6 GB) to `models/indextts2/IndexTTS-2/` (after Phase A.2 flips the default)
4. Print the `.env` lines to paste

Then in two terminals:

```
make run-indextts2     # terminal 1 - IndexTTS2 worker on :9881
make serve             # terminal 2 - main adapter on :9880
```

## Configuration

### Main adapter (TTS_INDEXTTS2_*)

```
TTS_ENGINE=indextts2
TTS_INDEXTTS2_URL=http://localhost:9881
TTS_INDEXTTS2_TIMEOUT=180
```

### Worker process (TTS_INDEXTTS2_*)

These vars belong to the worker, not the main adapter. The worker reads them from the same `.env` (or its own).

| Var | Default | Description |
|---|---|---|
| `TTS_INDEXTTS2_MODEL_DIR` | `~/.cache/tts-adapter/models/IndexTTS-2` (today); `./models/indextts2/IndexTTS-2` (after Phase A.2) | Local checkpoint directory |
| `TTS_INDEXTTS2_CFG_PATH` | `{MODEL_DIR}/config.yaml` | Path to config.yaml |
| `TTS_INDEXTTS2_USE_FP16` | `true` | FP16 inference (required on RTX 4070 12GB) |
| `TTS_INDEXTTS2_USE_CUDA_KERNEL` | `false` | Optional CUDA kernel speed path |
| `TTS_INDEXTTS2_USE_DEEPSPEED` | `false` | Optional DeepSpeed inference |
| `TTS_INDEXTTS2_USE_RANDOM` | `false` | Random sampling reduces clone fidelity |
| `TTS_INDEXTTS2_TRIM_SILENCE` | `false` | Off by default to preserve emotional pauses |
| `TTS_INDEXTTS2_PORT` | `9881` | HTTP port the worker listens on |

GPU is selected via `CUDA_VISIBLE_DEVICES`; the upstream `IndexTTS2(...)` constructor takes no `device` argument.

## Emotion input modes

Pick exactly one per request. Mixing modes returns 400.

### 1. Emotion via reference audio

Copy timbre from `reference_audio` and emotion from `emotion_audio`:

```
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Hello world' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_audio=@happy_sample.wav' \
  -F 'emotion_alpha=0.9' \
  --output out.wav
```

### 2. Emotion via free-form text

```
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Hello world' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_text=very excited and warm' \
  -F 'emotion_alpha=0.6' \
  --output out.wav
```

### 3. Emotion via 8-dim vector

Order is fixed: `[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]`.

```
curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Hello world' \
  -F 'reference_audio=@voice.wav' \
  -F 'emotion_vector=0,0,0.8,0,0,0,0,0' \
  -F 'emotion_alpha=0.7' \
  --output sad.wav
```

### Recommended emotion_alpha ranges

| Mode | Recommended alpha | Note |
|---|---|---|
| `emotion_audio` | 0.8 to 1.0 | Strong emotion transfer |
| `emotion_text` | 0.4 to 0.7 | About 0.6 keeps speech natural (upstream guidance) |
| `emotion_vector` | 0.6 to 1.0 | Higher = more expressive |

## CLI

```
make tts-clone-emotion text="Hello world" ref=voice.wav emotion-text="excited" alpha=0.6
```

Or directly:

```
PYTHONPATH=. uv run python scripts/indextts2/tts_clone_emotion.py \
    "Hello world" --ref voice.wav --emotion-text "excited and warm" --alpha 0.6 --bench
```

`--bench` emits one-line JSON with VRAM and RTF for hardware benchmarking.

## Caveats

- **Russian is not guaranteed.** Upstream training is CN/EN/JP-focused. Run a few samples before committing to Russian production work.
- **Not a real-time target.** Expect RTF > 1x on consumer GPUs. Use Qwen3 if you need streaming-ish latency.
- **RTX 4070 12GB:** start with `TTS_INDEXTTS2_USE_FP16=true`, `USE_CUDA_KERNEL=false`, `USE_DEEPSPEED=false`. Benchmark with `--bench` before enabling kernels/deepspeed.
- **No preset speakers.** `/tts`, `/tts/batch`, `/tts/design` raise `NotImplementedError`. Use `/tts/clone`.
- **Emotion params on Qwen3 are rejected.** The API returns 400 if you send `emotion_*` while `TTS_ENGINE=qwen3`. Never silently ignored.

## Offline operation

Once `make install-indextts2` finishes, the worker constructs `IndexTTS2(cfg_path=<local>, model_dir=<local>)` with explicit local paths. No HuggingFace Hub calls. Combined with `HF_HUB_OFFLINE=1`, this works fully offline.
