# TTS Adapter

Universal text-to-speech adapter with pluggable engines.

## Table of Contents

- [Quick Start](#quick-start)
- [Web UI](#web-ui)
- [Configuration](#configuration)
- [Docker](#docker)
- [API Usage](#api-usage)
- [Documentation](#documentation)
- [Engines](#engines)
- [License](#license)

## Quick Start

```bash
# Copy config
cp .env.example .env

# Build image
make build

# Start server (model downloads on first run, ~4.3GB)
make up

# Wait for health (model warmup ~2min)
make health

# Test generation
make test
```

### Local Development (without Docker)

```bash
uv sync
make serve
```

### Offline Mode

Download model while online, then run without network:

```bash
make install-qwen3      # Full install: deps + weights -> ./models/qwen3/<name>/
# (Or: make download-model to refresh just the weights)

# Add to .env (download script prints these):
# TTS_QWEN3_MODEL_PATH=./models/qwen3/Qwen3-TTS-12Hz-1.7B-CustomVoice
# HF_HUB_OFFLINE=1
```

See [Qwen3 Engine docs](docs/engines/qwen3/README.md#offline-mode) for details.

### Add IndexTTS2 (optional - emotional voice cloning, EN/CN/JP only)

IndexTTS2 runs as a separate worker process with its own venv (upstream dep
pins conflict with `qwen-tts`, see [docs/engines/indextts2/README.md](docs/engines/indextts2/README.md)).
**Russian is NOT supported by IndexTTS2** (upstream tokenizer mangles Cyrillic);
the API rejects Russian on this engine with HTTP 400.

```bash
make install-indextts2   # Clones upstream + isolated venv + downloads checkpoints (~6 GB)

# Then in two terminals:
make run-indextts2       # IndexTTS2 worker on :9881
make serve               # main adapter on :9880

# Switch engines at runtime via the API (or set TTS_ENGINE=indextts2 in .env at boot):
curl -X POST http://localhost:9880/model/switch \
     -H 'content-type: application/json' \
     -d '{"model_id":"IndexTeam/IndexTTS-2"}'
```

### Add VoxCPM2 (optional - **Russian emotional voice cloning**)

VoxCPM2 (OpenBMB, Apr 2026, Apache-2.0) is the recommended engine for Russian
voice cloning + emotion control in one call. Same isolated-worker pattern as
IndexTTS2. See [docs/engines/voxcpm2/README.md](docs/engines/voxcpm2/README.md).

```bash
make install-voxcpm2   # Clones upstream + isolated venv + downloads checkpoints (~10 GB)

# Then in two terminals:
make run-voxcpm2       # VoxCPM2 worker on :9882
make serve             # main adapter on :9880

# Switch engines at runtime:
curl -X POST http://localhost:9880/model/switch \
     -H 'content-type: application/json' \
     -d '{"model_id":"openbmb/VoxCPM2"}'

# Russian clone + emotion in one call:
curl -X POST http://localhost:9880/tts/clone \
     -F 'text=Привет, я очень рад тебя видеть' \
     -F 'language=Russian' \
     -F 'reference_audio=@voice.wav' \
     -F 'emotion_text=very happy, cheerful, smiling tone' \
     --output happy.wav
```

The main adapter forwards `/tts/clone` requests to the appropriate worker via HTTP. Cross-engine `/model/switch` unloads the previous engine before loading the target so VRAM stays within the 4070 12 GB envelope.

## Web UI

Open **http://localhost:9880** - three modes (Simple, Voice Design, Voice Clone), RU/EN switch, advanced generation settings. See [Web UI docs](docs/web-ui.md).

For API access, see [API Reference](docs/api-reference.md). Swagger docs available at `/docs`.

## Configuration

Edit `.env` (copy from `.env.example`):

```bash
# Engine selection
TTS_ENGINE=qwen3

# Defaults
TTS_DEFAULT_SPEAKER=Serena
TTS_DEFAULT_LANGUAGE=Russian

# Qwen3 engine
TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
TTS_QWEN3_DEVICE=cuda:0
TTS_QWEN3_DTYPE=bfloat16
```

See [.env.example](.env.example) for all options.

## Docker

```bash
make build    # Build image (online, one-time or after deps change)
make up       # Start container (offline; reuses cached image)
make health   # Check health
make logs     # View logs
make down     # Stop
make rebuild  # Force rebuild with --no-cache --pull
make shell    # Shell into container
```

`compose.yml` sets `pull_policy: missing`, so `make up` never rebuilds or pulls
when the image exists locally - safe to use offline after a one-time `make build`.
Rebuild only when `uv.lock`, `pyproject.toml`, or the `Dockerfile` changes.

See [Makefile](Makefile) for all targets.

### Model Cache

Model weights (~4.3GB) download automatically on first `make up`. Stored in host's `~/.cache/huggingface` and mounted into container, so:
- Download happens once, persists across container restarts
- Same cache shared between Docker and local development
- Custom path: set `HF_CACHE_PATH` in `.env`

## API Usage

### Single Generation

```bash
curl -X POST http://localhost:9880/tts \
  -H 'content-type: application/json' \
  -d '{"text":"Hello world","language":"English","speaker":"Ryan"}' \
  --output out.wav
```

### Batch Generation

```bash
curl -X POST http://localhost:9880/tts/batch \
  -H 'content-type: application/json' \
  -d '{"items":[{"id":"001","text":"First phrase"},{"id":"002","text":"Second phrase"}]}' \
  --output batch.zip
```

### Voice Cloning

Clone any voice from a 3-10 second audio sample (requires Base model):

```bash
# Switch to Base model in .env:
# TTS_QWEN3_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base

curl -X POST http://localhost:9880/tts/clone \
  -F 'text=Привет мир' \
  -F 'language=Russian' \
  -F 'reference_audio=@voice_sample.wav' \
  -F 'reference_text=Текст из референсного аудио' \
  --output cloned.wav
```

See [Qwen3 Engine docs](docs/engines/qwen3/README.md#voice-cloning) for details.

### Health Check

```bash
curl http://localhost:9880/health
```

## Documentation

| Document | Description |
|----------|-------------|
| [Web UI](docs/web-ui.md) | Language switch, advanced settings, multi-client, LAN |
| [Architecture](docs/architecture.md) | Design decisions, engine protocol |
| [API Reference](docs/api-reference.md) | Endpoint specs, request/response formats |
| [Qwen3 Engine](docs/engines/qwen3/README.md) | Model variants, speakers, setup |
| [VoxCPM2 Engine](docs/engines/voxcpm2/README.md) | Russian voice cloning + text-tag emotion control |
| [IndexTTS2 Engine](docs/engines/indextts2/README.md) | EN/CN/JP voice cloning + rich emotion control |
| [AGENTS.md](AGENTS.md) | Project instructions for AI agents |

## Engines

`tts-adapter` is **one public API + Web UI** at `http://localhost:9880`. Qwen3 runs in-process as the default. Some engines (e.g. IndexTTS2) have incompatible dependency stacks and run as **optional isolated workers** behind the same API; clients only ever talk to the main adapter. See [Architecture](docs/architecture.md) for the full mental model.

| Engine | Status | How it runs | Languages | Description |
|--------|--------|-------------|-----------|-------------|
| [Qwen3-TTS](docs/engines/qwen3/README.md) | Ready | In-process | 10 + Auto (Russian, Chinese, English, Japanese, Korean, German, French, Portuguese, Spanish, Italian) | 1.7B/0.6B preset speakers, voice cloning OR `instruct` style (never both) |
| [VoxCPM2](docs/engines/voxcpm2/README.md) | Ready (local/Docker path; requires installed worker) | Isolated worker on `:9882` | 23 + Auto (incl. **Russian**, English, Chinese, Japanese, Korean, ...) | **Russian-capable** emotional voice cloning (text-tag style); Apache-2.0 |
| [IndexTTS2](docs/engines/indextts2/README.md) | Ready (local/Docker path; requires installed worker) | Isolated worker on `:9881` | Chinese, English, Japanese **only** (no Russian) | Rich emotional voice cloning (audio / text / 8-vector + alpha) |

**Language gate:** the API rejects unsupported language requests with `400` + actionable hint. The Web UI's language dropdown is populated from the active engine's `supported_languages` (via `/health`), so users only see what will actually work. Russian preference is honored when the active engine supports it; otherwise the UI auto-falls-back and shows an inline hint suggesting the engine switch.

### Adding New Engines

- Dependency-compatible engine -> implement `TTSEngine`, register in `engines/__init__.py`, done.
- Dependency-incompatible engine -> add a worker FastAPI app in `scripts/<name>/serve.py`, a thin `<Name>RemoteEngine` HTTP forwarder, a worker Dockerfile, and a profile-gated compose service. Cross-engine `/model/switch` handles the rest.

Full recipe in [docs/architecture.md#adding-a-new-engine](docs/architecture.md#adding-a-new-engine).

## License

Apache-2.0
