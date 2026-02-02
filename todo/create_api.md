# TTS Adapter Implementation Checklist

> **Temporary file** - delete after implementation complete

## Phase 1: Foundation
- [x] Initialize uv project
- [x] Add dependencies (qwen-tts, fastapi, pydantic, etc.)
- [x] Create directory structure

## Phase 2: Core Abstractions
- [x] `src/tts_adapter/contract.py` - request/response models
- [x] `src/tts_adapter/engine.py` - TTSEngine protocol
- [x] `src/tts_adapter/config.py` - environment config

## Phase 3: Qwen3 Engine
- [x] `src/tts_adapter/engines/qwen3.py` - implementation
- [x] Thread lock for GPU serialization
- [x] Flash attention fallback

## Phase 4: FastAPI Server
- [x] `src/tts_adapter/api/routes.py`
- [x] GET `/health` endpoint
- [x] POST `/tts` endpoint
- [x] POST `/tts/batch` endpoint (ZIP response)

## Phase 5: CLI Batch Runner
- [x] `scripts/tts_batch.py`
- [x] JSONL input support
- [x] Batch processing with configurable size

## Phase 6: Documentation
- [ ] Update README.md as router
- [ ] `docs/architecture.md`
- [ ] `docs/api-reference.md`
- [ ] `docs/engines/qwen3.md`

## Verification
- [ ] Test health endpoint
- [ ] Test single TTS generation
- [ ] Test batch generation
- [ ] Verify WAV output plays correctly
