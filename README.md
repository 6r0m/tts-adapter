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
make download-model     # Downloads to ~/.cache/tts-adapter/models/
# Add to .env:
# TTS_QWEN3_MODEL_PATH=~/.cache/tts-adapter/models/Qwen3-TTS-12Hz-1.7B-CustomVoice
# HF_HUB_OFFLINE=1
```

See [Qwen3 Engine docs](docs/engines/qwen3/README.md#offline-mode) for details.

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
| [IndexTTS2 Engine](docs/engines/indextts2/README.md) | Voice cloning + emotion control |
| [AGENTS.md](AGENTS.md) | Project instructions for AI agents |

## Engines

| Engine | Status | Description |
|--------|--------|-------------|
| [Qwen3-TTS](docs/engines/qwen3/README.md) | Ready | 1.7B/0.6B with voice cloning, preset speakers, instructions |
| [IndexTTS2](docs/engines/indextts2/README.md) | WIP (isolated worker design) | Emotional voice cloning - runs as a separate process due to upstream dep pins (see [todo/engine_install_and_switch.md](todo/engine_install_and_switch.md)) |

**Promotion criterion for IndexTTS2 -> Ready:** `make install-indextts2 && make run-indextts2 && make serve` followed by a `/tts/clone` request with `emotion_text` returns `200 audio/wav`.

### Adding New Engines

1. Create `tts_adapter/engines/new_engine.py`
2. Implement `TTSEngine` protocol
3. Register in `engines/__init__.py`
4. Document in `docs/engines/`

See [Architecture](docs/architecture.md) for details.

## License

Apache-2.0
