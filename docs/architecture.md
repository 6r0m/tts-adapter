# Architecture

## Mental model

**`tts-adapter` is the single public API and Web UI.** Clients only ever talk to it.

Qwen3 runs **in-process** as the default engine. Some engines have incompatible Python dependency stacks (e.g. IndexTTS2 pins `transformers==4.52.1` / `torch==2.8.*`, our adapter pins `qwen-tts` which needs `transformers==4.57.3`). Those engines run as **optional isolated workers** in their own processes/containers and are integrated through the same adapter API. Users still call only the main adapter.

Current workers:

| Worker | Reason for isolation | Public? |
|---|---|---|
| IndexTTS2 (`adapter-tts-indextts2:9881`) | Requires its own `indextts` dependency stack | No, internal worker |

The main adapter talks to workers over HTTP and exposes them through `/models`, `/model/switch`, and `/tts/clone`.

```
                    user / UI / client
                           |
                           v
                  adapter-tts :9880
        main API + Web UI + engine registry
                           |
        +------------------+------------------+
        |                                     |
        v                                     v
  Qwen3Engine                         IndexTTS2RemoteEngine
  in-process                          HTTP forwarder
  default                             optional, lazy
                                        |
                                        v
                              adapter-tts-indextts2 :9881
                              isolated worker, own venv
                              cold until /load
```

### Boundary

- **Public API/UI:** `adapter-tts` only (`http://localhost:9880`)
- **Internal engine workers:** optional, isolated, hidden behind the adapter

## Repo layout

```
tts-adapter/
  tts_adapter/
    api/routes.py          # FastAPI endpoints (the public contract)
    web/                   # HTML Web UI templates
    engine.py              # TTSEngine protocol
    engines/
      __init__.py          # _ENGINES registry
      qwen3.py             # Qwen3Engine - in-process
      indextts2.py         # IndexTTS2RemoteEngine - HTTP forwarder
    contract.py            # request/response models
    config.py              # 12-factor env config
    audio_utils.py         # trim_silence, bytes_to_tempfile (engine-agnostic)
    gpu_utils.py           # unload_gpu_model
  scripts/
    qwen3/                 # Qwen3 CLI scripts
    indextts2/
      serve.py             # IndexTTS2 worker FastAPI app (runs in vendor venv)
      tts_clone_emotion.py # CLI for emotion clone
  Dockerfile               # main adapter image (qwen3 in-process)
  Dockerfile.indextts2     # thin worker image (bind-mounts host vendor venv)
  compose.yml              # adapter-tts + adapter-tts-indextts2 (profile-gated)
  vendor/index-tts/        # cloned upstream + isolated venv (gitignored)
  models/                  # downloaded weights (gitignored)
```

## Engine protocol

All engines satisfy a single `TTSEngine` Protocol:

```python
class TTSEngine(Protocol):
    engine_name: str
    model_id: str
    device: str
    supports_cloning: bool
    supports_design: bool
    supports_custom_voice: bool
    supports_emotional_cloning: bool

    def warmup(self) -> None: ...
    def reload(self, model_id: str) -> None: ...
    def synthesize(...) -> bytes: ...
    def synthesize_batch(...) -> list[bytes]: ...
    def synthesize_clone(..., *, emotion_audio=, emotion_text=, emotion_vector=, emotion_alpha=) -> bytes: ...
    def synthesize_design(...) -> bytes: ...

    def catalog_models(self) -> list[ModelInfo]: ...    # static - always returned
    def available_models(self) -> list[ModelInfo]: ...  # only what's reachable RIGHT NOW
```

The catalog/availability split lets `/model/switch` route to engines whose backend is currently down (returns 503 with actionable hint via `warmup()`) instead of rejecting as 400 unknown. Meanwhile `/models` returns only reachable entries so the UI dropdown stays clean.

Unsupported methods raise `NotImplementedError` with an actionable message. Capability flags drive UI (e.g. emotion controls visible only when `supports_emotional_cloning=true`).

## Cross-engine model switch

`POST /model/switch` is one endpoint that handles both same-engine variant swap AND cross-engine swap. The pattern is the same in both cases: **unload current, load new**. Strict VRAM rule: only ONE model loaded at a time.

```
1. Look up which engine owns model_id (catalog union of all engines)
2. If same engine + same model -> no-op
3. If same engine, different variant -> engine.reload(new_id)
4. If different engine:
   a. Construct target engine instance (cheap, no model load)
   b. Unload current:
        - Qwen3 in-process    -> gpu_utils.unload_gpu_model
        - Remote (IndexTTS2)  -> POST {URL}/unload (best-effort)
   c. target_engine.warmup():
        - Qwen3   -> in-process model load
        - Remote  -> GET /health + POST /load on the worker
   d. On warmup failure: rollback _engine to current, attempt re-warm of
      previous engine, surface 503 with status string
   e. On success: commit globals, return new engine info
```

## Remote worker contract

`IndexTTS2RemoteEngine` is a thin httpx client (~250 LOC). The actual `indextts.infer_v2.IndexTTS2` lives in the worker container's bind-mounted `vendor/index-tts/.venv`.

The worker exposes four endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | `{ok, model_loaded, model_dir, supports_emotional_cloning}` - cheap, no model touch |
| `POST /load` | Idempotent warmup |
| `POST /unload` | Idempotent VRAM release |
| `POST /tts/clone` | Lazy-loads if not loaded; same form contract as the main adapter's `/tts/clone` |

The worker comes up COLD (no model load on container start). VRAM is released on `/unload` or by killing the container.

## Docker scope

Two images, both opt-in via compose profiles:

| Image | Profile | Self-contained? |
|---|---|---|
| `tts/adapter-tts` | `gpu` (always on for `make up`) | yes - `qwen-tts` baked into venv |
| `tts/adapter-tts-indextts2` | `indextts2` (only on if host has both `models/indextts2/IndexTTS-2/` AND `vendor/index-tts/.venv/`) | **no - thin local-dev image, bind-mounts host vendor venv** |

The thin worker image is fast to build (~1.5 min vs ~30 min) and small (~3 GB vs ~12 GB) but **not portable** - it requires the host to have run `make install-indextts2`. Suitable for local dev. For CI / cross-host deployment, switch to a self-contained image (the original Phase A.1 design lives in git history). See `docs/engines/indextts2/README.md` for details.

`make up` auto-detects via `INDEXTTS2_READY` (checks both checkpoints AND vendor venv) and adds `--profile indextts2` only if both are present. `make down` always covers both profiles so a partially-installed cluster still shuts down cleanly.

## Configuration (12-factor)

Global (engine-agnostic, `TTS_*` prefix):

| Var | Default | Note |
|---|---|---|
| `TTS_ENGINE` | `qwen3` | Boot-time default; `/model/switch` overrides at runtime |
| `TTS_DEFAULT_SPEAKER` | - | |
| `TTS_DEFAULT_LANGUAGE` | - | |
| `TTS_HOST` / `TTS_PORT` | `0.0.0.0` / `9880` | Main adapter |

Engine-specific (namespaced; each engine class owns its defaults):

- Qwen3 (`TTS_QWEN3_*`): `MODEL_ID`, `MODEL_PATH`, `DEVICE`, `DTYPE`
- IndexTTS2 main-adapter side (`TTS_INDEXTTS2_*`): `URL`, `TIMEOUT`, `LOAD_TIMEOUT`, `HEALTH_TIMEOUT`
- IndexTTS2 worker side (`TTS_INDEXTTS2_*`): `MODEL_DIR`, `CFG_PATH`, `USE_FP16`, `USE_CUDA_KERNEL`, `USE_DEEPSPEED`, `USE_RANDOM`, `TRIM_SILENCE`, `PORT`

Worker-side env is documented in `docs/engines/indextts2/README.md`, not here - those vars belong to the worker process.

## Thread safety

GPU inference must be serialized. Each in-process engine and the worker each hold a `threading.Lock` covering load/unload/inference as a single critical section (closes the load-then-unload race during cross-engine switch).

Single-worker uvicorn (`--workers 1`) is required.

## Adding a new engine

If the engine is dependency-compatible with the main adapter (`qwen-tts`'s pins):

1. Create `tts_adapter/engines/<name>.py` implementing `TTSEngine`
2. Register in `engines/__init__.py` (`_ENGINES` dict)
3. Use `TTS_ENGINE=<name>` at boot OR switch via `/model/switch`

If the engine has incompatible dependencies (transformers/torch pin clash, etc.):

1. Add a worker FastAPI app in `scripts/<name>/serve.py` (use `vendor/<repo>/.venv` for isolated deps)
2. Add a `<Name>RemoteEngine` in `tts_adapter/engines/<name>.py` that forwards over HTTP
3. Register the remote engine in `engines/__init__.py`
4. Add a thin `Dockerfile.<name>` that bind-mounts the host vendor venv (or self-contained if you need a portable image)
5. Add the worker as a profile-gated service in `compose.yml`
6. Wire `make install-<name>` + `make run-<name>` (with `env -u VIRTUAL_ENV` to keep the parent shell's venv from leaking in)

Never import the worker's package directly in the main adapter process. The point of isolation is that those dependency stacks must NEVER load in the same Python process.

## Related docs

- `docs/api-reference.md` - endpoint specs
- `docs/web-ui.md` - Web UI details
- `docs/engines/qwen3/README.md` - Qwen3 engine specifics
- `docs/engines/indextts2/README.md` - IndexTTS2 worker setup, install, caveats
- `todo/engine_install_and_switch.md` - phase log of the IndexTTS2 + cross-engine work
