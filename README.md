# TTS Adapter

Universal text-to-speech adapter with pluggable engines.

## Quick Start

```bash
# Install
uv sync

# Run server
uv run uvicorn tts_adapter.api:app --host 0.0.0.0 --port 9880

# Generate audio
curl -X POST http://localhost:9880/tts \
  -H 'content-type: application/json' \
  -d '{"text":"Привет мир","language":"Russian"}' \
  --output out.wav
```

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
TTS_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
TTS_DEVICE=cuda:0
TTS_DTYPE=bfloat16
```

## Documentation

- [Architecture](docs/architecture.md) - design decisions, engine protocol
- [API Reference](docs/api-reference.md) - endpoint specs
- [Qwen3 Engine](docs/engines/qwen3.md) - model variants, speakers, setup

## Engines

| Engine | Status | Description |
|--------|--------|-------------|
| Qwen3-TTS | ✅ Ready | CustomVoice model with instruction support |

## License

Apache-2.0
