# AGENTS.md - TTS Adapter Project Instructions

Project-specific agent instructions for TTS Adapter codebase.

---

## Quick Routes

**Build & Run:**
- Install: `make install`
- Run server: `make up` (Docker) or `uv run tts-server` (local)
- Test: `make test` or `make test batch`
- Health check: `make health`

**Architecture:**
- Overview: [docs/architecture.md](docs/architecture.md)
- API Reference: [docs/api-reference.md](docs/api-reference.md)
- Web UI (i18n, settings, LAN): [docs/web-ui.md](docs/web-ui.md)
- Qwen3 Engine: [docs/engines/qwen3/README.md](docs/engines/qwen3/README.md)

**Check universal rules:** See `~/.claude/CLAUDE.md` for global standards

---

## Critical Project Rules

### GPU Required

Qwen3-TTS requires CUDA GPU. No CPU fallback available.
- RTX 4070 (12GB): Use 1.7B model with bf16
- Lower VRAM: Use 0.6B model

### Engine Protocol

All engines must implement `TTSEngine` protocol:
- `warmup()` - Load model
- `synthesize(text, language, speaker, instruct)` - Single text
- `synthesize_batch(texts, language, speaker, instruct)` - Multiple texts

### Configuration Precedence

1. Constructor args (programmatic)
2. Environment variables (`.env` file)
3. Engine defaults (hardcoded)

---

## Project Structure

```
tts-adapter/
├── tts_adapter/
│   ├── __init__.py
│   ├── api/                 # FastAPI routes
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── engines/             # TTS engines
│   │   ├── __init__.py      # Engine factory
│   │   └── qwen3.py         # Qwen3-TTS implementation
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Global settings
│   ├── contract.py          # Request/response models
│   └── engine.py            # TTSEngine protocol
├── scripts/
│   └── tts_batch.py         # Batch CLI tool
├── docs/                    # Documentation
├── data/                    # Local data (git-ignored)
│   └── cache/               # HuggingFace model cache
├── Dockerfile               # Multi-stage GPU build
├── compose.yml              # Docker Compose
├── Makefile                 # Build/test automation
├── pyproject.toml           # uv config
└── uv.lock                  # Locked dependencies
```

---

## Tech Stack

- **TTS**: Qwen3-TTS (qwen-tts package)
- **API**: FastAPI, uvicorn
- **Config**: pydantic-settings
- **Audio**: soundfile

---

## Development Workflow

### 1. Local Development

```bash
# Install
make install
source .venv/bin/activate

# Copy and edit config
cp .env.example .env

# Run server
uv run tts-server

# Test
make test
```

### 2. Docker Development

```bash
# Build and start
make build
make up

# Check logs
make logs

# Test
make health
make test
```

### 3. API Usage

```bash
# Single generation
curl -X POST http://localhost:9880/tts \
  -H 'content-type: application/json' \
  -d '{"text":"Привет","language":"Russian","speaker":"Ryan"}' \
  --output out.wav

# Batch generation
curl -X POST http://localhost:9880/tts/batch \
  -H 'content-type: application/json' \
  -d '{"items":[{"id":"001","text":"Первая"},{"id":"002","text":"Вторая"}]}' \
  --output batch.zip
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_ENGINE` | `qwen3` | Engine name |
| `TTS_DEFAULT_SPEAKER` | - | Default speaker |
| `TTS_DEFAULT_LANGUAGE` | - | Default language |
| `TTS_HOST` | `0.0.0.0` | Server host |
| `TTS_PORT` | `9880` | Server port |
| `TTS_QWEN3_MODEL_ID` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Model |
| `TTS_QWEN3_DEVICE` | `cuda:0` | CUDA device |
| `TTS_QWEN3_DTYPE` | `bfloat16` | Data type |
| `TTS_INDEXTTS2_MODEL_DIR` | `~/.cache/tts-adapter/models/IndexTTS-2` | Local checkpoint dir |
| `TTS_INDEXTTS2_REPO_DIR` | - | Path to cloned `index-tts` repo (added to sys.path) |
| `TTS_INDEXTTS2_USE_FP16` | `true` | FP16 inference |
| `TTS_INDEXTTS2_USE_CUDA_KERNEL` | `false` | Optional CUDA kernel speed path |
| `TTS_INDEXTTS2_USE_DEEPSPEED` | `false` | Optional DeepSpeed inference |
| `TTS_INDEXTTS2_USE_RANDOM` | `false` | Random sampling (reduces clone fidelity) |
| `TTS_INDEXTTS2_TRIM_SILENCE` | `false` | Trim leading/trailing silence (preserves emotional pauses by default) |

---

## Adding New Engines

1. Create `tts_adapter/engines/new_engine.py`
2. Implement `TTSEngine` protocol
3. Add engine-specific `Settings` class with pydantic-settings
4. Register in `engines/__init__.py` (`_ENGINES` dict)
5. Document in `docs/engines/new_engine.md`

---

## Git Workflow

- **Branches**: Feature branches from `develop`
- **PRs**: Target `develop` branch
- **See**: `~/.claude/CLAUDE.md` for universal git rules

---

## References

- Universal rules: `~/.claude/CLAUDE.md`
- Architecture: [docs/architecture.md](docs/architecture.md)
- API Reference: [docs/api-reference.md](docs/api-reference.md)
