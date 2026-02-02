# TTS Adapter

Universal text-to-speech adapter with pluggable engines.

## Table of Contents

- [Quick Start](#quick-start)
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
uv run tts-server
```

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
make build    # Build image
make up       # Start container
make health   # Check health
make logs     # View logs
make down     # Stop
make shell    # Shell into container
```

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

### Health Check

```bash
curl http://localhost:9880/health
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Design decisions, engine protocol |
| [API Reference](docs/api-reference.md) | Endpoint specs, request/response formats |
| [Qwen3 Engine](docs/engines/qwen3.md) | Model variants, speakers, setup |
| [AGENTS.md](AGENTS.md) | Project instructions for AI agents |

## Engines

| Engine | Status | Description |
|--------|--------|-------------|
| [Qwen3-TTS](docs/engines/qwen3.md) | ✅ Ready | 1.7B/0.6B CustomVoice with instruction support |

### Adding New Engines

1. Create `tts_adapter/engines/new_engine.py`
2. Implement `TTSEngine` protocol
3. Register in `engines/__init__.py`
4. Document in `docs/engines/`

See [Architecture](docs/architecture.md) for details.

## License

Apache-2.0
