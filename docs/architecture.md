# Architecture

## Overview

TTS Adapter follows the **capability adapter pattern**: one repo per capability (TTS), with multiple engine implementations inside.

```
tts-adapter/
├── tts_adapter/
│   ├── engine.py        # TTSEngine protocol
│   ├── contract.py      # Request/response models
│   ├── config.py        # Environment config
│   ├── engines/
│   │   └── qwen3.py     # Qwen3-TTS implementation
│   └── api/
│       └── routes.py    # FastAPI endpoints
```

## Design Decisions

### Why single repo with multiple engines?

- **SOLID**: Single responsibility (TTS), open for extension (add engines)
- **Shared contract**: All engines use the same request/response models
- **Simple deployment**: One container/process per capability

Split into separate repos only if:
- Dependency conflicts (different CUDA/torch versions)
- Different runtime requirements (GPU vs CPU)
- Separate scaling needs

### Engine Protocol

All engines implement `TTSEngine` protocol:

```python
class TTSEngine(Protocol):
    def warmup(self) -> None: ...
    def synthesize(text, language, speaker, instruct) -> bytes: ...
    def synthesize_batch(texts, language, speaker, instruct) -> list[bytes]: ...
```

This allows swapping engines without changing API code.

### Configuration

12-factor style via environment variables:

- `TTS_ENGINE` - Engine name (e.g., `qwen3`)
- `TTS_MODEL_ID` - HuggingFace model identifier
- `TTS_DEVICE` - CUDA device (e.g., `cuda:0`)
- `TTS_DTYPE` - Data type (`bfloat16`, `float16`, `float32`)

Loaded via `pydantic-settings` with `.env` file support.

### Thread Safety

GPU inference requires serialization. Each engine uses a `threading.Lock` to prevent concurrent GPU access:

```python
with self._lock:
    wavs, sr = self._model.generate_custom_voice(...)
```

Single-worker uvicorn (`--workers 1`) recommended.

## Adding New Engines

1. Create `tts_adapter/engines/new_engine.py`
2. Implement `TTSEngine` protocol
3. Register in `engines/__init__.py` (`_ENGINES` dict)
4. Set `TTS_ENGINE=new_engine` to use it
