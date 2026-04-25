# Engine Install UX + Unified Cross-Engine Switch

> ⚠️ **STATUS: pre-implementation cleanup REQUIRED before any new feature work.**
> The current `develop` branch contains the rejected in-process IndexTTS2 design (engine class, `TTS_INDEXTTS2_REPO_DIR` env, README "✅ Ready" claim, isinstance-coupled CLI). This contradicts the architecture decision below. **Phase 0 must run first** to remove the contradiction — otherwise future agents will follow the wrong path.
>
> **When complete:** move this file to `todo/done/` (do **not** delete).
> **Supersedes:** [todo/indextts2_engine.md](indextts2_engine.md) for implementation architecture (that file now carries a SUPERSEDED banner). Emotion contract / validation / benchmark sections from the old todo remain valid.
> **Why:** the user wants a fresh `git clone` → one `make` command → working server. Plus engine selection from the web UI rather than `.env` edits + restart. Without sound dependency isolation, neither happens.

---

## ARCHITECTURE DECISION (post-review): IndexTTS2 runs as a separate process/service

**Final answer: Option C is the only solid architecture. Option A is a probe. Option B is a trap.**

IndexTTS2 upstream pins `transformers==4.52.1`, `torch==2.8.*`, optional `deepspeed==0.17.1`, and expects `uv` to manage its own `.venv`. Our adapter pins `qwen-tts` which requires `transformers==4.57.3`. **They cannot coexist in one Python environment.** Source: [index-tts/pyproject.toml](https://github.com/index-tts/index-tts/blob/main/pyproject.toml).

### Architecture

```
client
  │
  ▼
tts-adapter (main API, Qwen env)
  │
  ├──► Qwen3Engine             (in-process, ./.venv with qwen-tts)
  │
  └──► IndexTTS2RemoteEngine   ── HTTP ──►  scripts/indextts2/serve.py
                                            (separate process, vendor/index-tts/.venv)
                                            uses indextts.infer_v2.IndexTTS2 directly
```

### Concrete consequences

- The in-process `IndexTTS2Engine` in [tts_adapter/engines/indextts2.py](../tts_adapter/engines/indextts2.py) is **rejected as production architecture** — it imports `indextts` directly and would fail when its internal deps don't resolve in the adapter venv. To be **rewritten** as a thin HTTP-forwarding `IndexTTS2RemoteEngine`.
- New file: `scripts/indextts2/serve.py` — minimal FastAPI app exposing `/tts/clone` (same form contract as the main adapter), runs in `vendor/index-tts/.venv`. Self-contained: imports `indextts.infer_v2`, `fastapi`, `soundfile`, plus `tts_adapter.audio_utils` / `gpu_utils` via `sys.path` injection (these helper modules have zero internal `tts_adapter` deps, so cross-venv reuse is safe).
- New env var: `TTS_INDEXTTS2_URL` (default `http://localhost:9881`) — the remote engine forwards `/tts/clone` to this URL.
- New Make target: `make run-indextts2` — runs `cd vendor/index-tts && uv run python ../../scripts/indextts2/serve.py`.

### Why not B (sys.path injection of vendor venv site-packages)?

```
adapter .venv imports torch A
vendor .venv site-packages exposes torch B / transformers B
```

Mixed Python environments fail randomly, or worse — work until CUDA/runtime explodes. **Do not build serious code on this.**

### Why not A (install indextts into adapter venv)?

Useful only as a **throwaway probe** to confirm the conflict assumption:

```bash
uv pip install -e vendor/index-tts
uv pip check
```

Because IndexTTS2 pins exact versions, expect `uv pip check` to flag conflicts. Do NOT make any phase depend on this path.

---

## Policy decisions (post-review)

### `~/.cache/tts-adapter/` legacy fallback

| | |
|---|---|
| **Canonical** | explicit `TTS_*_MODEL_DIR` / `TTS_*_MODEL_PATH` env (or repo-local `./models/...` default) |
| **Legacy fallback** | `~/.cache/tts-adapter/` — accepted but warns once at startup |
| **Removal** | next minor release (or after one stable release) |
| **Migration** | none — user moves files manually if they want |

Startup warning text:
```
Using legacy model cache path ~/.cache/tts-adapter. Set TTS_INDEXTTS2_MODEL_DIR
(or the engine-specific equivalent) explicitly. This fallback will be removed in
the next minor release.
```

Once per startup. Never per request. Reason: silent fallbacks become invisible technical debt; immediate deletion is unnecessary risk.

### Make target naming — REVERSED from earlier in this thread

| | |
|---|---|
| **Canonical** | `make install-indextts2` (hyphen-separated, matches engine name) |
| **Alias** | `make install-indextts` → delegates to canonical with a one-line "alias" hint |
| **Same shape for** | `run-indextts2`, `test-indextts2`, `bench-indextts2` |

```makefile
.PHONY: install-indextts2 install-indextts run-indextts2 ...

install-indextts2:
	# real implementation

install-indextts: install-indextts2
	@echo "(alias) prefer 'make install-indextts2' as canonical target"
```

Reason: engine name, env var, docs, runtime all match (`TTS_ENGINE=indextts2`, `TTS_INDEXTTS2_*`, `make install-indextts2`). `indextts` alone is ambiguous with IndexTTS 1.x.

**Note:** earlier in this thread we discussed `make install indextts` (positional arg, no hyphen). That is **dropped** — hyphenated `install-indextts2` is canonical.

## Out of scope

- Auto-editing `.env` (print + ask user to paste — safer than upsert).
- Loading both engine workers simultaneously on one GPU (VRAM doesn't allow on 4070 12 GB — operator stops one before starting the other).
- Auto-managing the IndexTTS2 worker lifecycle from the main adapter (operator runs `make run-indextts2` separately, same as `make serve`).
- Two-Docker-services orchestration (deferred — `compose.yml` can grow a second service later, but local-dev path uses two terminals).

---

## Phase 0: Architecture-drift cleanup (BLOCKING — do this first)

> Pure subtractive work. Removes claims/code that contradict the Option C decision. **No new features.** After Phase 0 the repo honestly reflects "IndexTTS2 = WIP, isolated worker design" with no in-process trap left to step in.

- [ ] **Demote IndexTTS2 status in [README.md](../README.md):**
  - Engines table: `✅ Ready` → `🚧 WIP (isolated worker design)`
  - Drop the "indextts2 — when you need to clone…" recommendation paragraph (or rephrase as "planned").
  - Promotion criterion documented inline:
    > Switches to ✅ once: `make install-indextts2 && make run-indextts2 && make serve` then a `/tts/clone` with `emotion_text` returns `200 audio/wav`.
- [ ] **Strip in-process env vars from [.env.example](../.env.example):**
  - Remove: `TTS_INDEXTTS2_REPO_DIR`, `TTS_INDEXTTS2_USE_FP16`, `TTS_INDEXTTS2_USE_CUDA_KERNEL`, `TTS_INDEXTTS2_USE_DEEPSPEED`, `TTS_INDEXTTS2_USE_RANDOM`, `TTS_INDEXTTS2_TRIM_SILENCE`, `TTS_INDEXTTS2_MODEL_DIR`.
  - Replace with the **main-adapter-side** vars only:
    ```env
    # IndexTTS2 (remote worker — set TTS_ENGINE=indextts2 and run `make run-indextts2` separately)
    # TTS_INDEXTTS2_URL=http://localhost:9881
    # TTS_INDEXTTS2_TIMEOUT=180
    ```
  - Worker-side env vars (MODEL_DIR, USE_FP16, etc.) move to `docs/engines/indextts2/README.md` under "Worker configuration", not `.env.example`.
- [ ] **Strip in-process rows from [AGENTS.md](../AGENTS.md):**
  - Remove: `TTS_INDEXTTS2_MODEL_DIR`, `TTS_INDEXTTS2_REPO_DIR`, `TTS_INDEXTTS2_USE_FP16`, `TTS_INDEXTTS2_USE_CUDA_KERNEL`, `TTS_INDEXTTS2_USE_DEEPSPEED`, `TTS_INDEXTTS2_USE_RANDOM`, `TTS_INDEXTTS2_TRIM_SILENCE`.
  - Add: `TTS_INDEXTTS2_URL`, `TTS_INDEXTTS2_TIMEOUT`.
  - Note in the table: "Worker-side env (USE_FP16, MODEL_DIR, …) is documented in [docs/engines/indextts2/README.md](../docs/engines/indextts2/README.md), not here."
- [ ] **Decouple [scripts/indextts2/tts_clone_emotion.py](../scripts/indextts2/tts_clone_emotion.py) from the concrete class:**
  - Drop `from tts_adapter.engines.indextts2 import IndexTTS2Engine`.
  - Drop `if not isinstance(engine, IndexTTS2Engine):` — that breaks the moment we rename to `IndexTTS2RemoteEngine`.
  - Replace with capability check via the protocol:
    ```python
    engine = create_engine()
    if engine.engine_name != "indextts2" or not engine.supports_emotional_cloning:
        print("Error: set TTS_ENGINE=indextts2 and run `make run-indextts2`",
              file=sys.stderr)
        return 1
    ```
- [ ] **Health-gate `make tts-clone-emotion` on the worker URL:**
  ```make
  tts-clone-emotion:
      @curl -fsS http://localhost:9881/health >/dev/null 2>&1 || \
          (echo "IndexTTS2 worker not running. Start it first: make run-indextts2"; exit 1)
      ...existing body...
  ```
- [ ] **Trim/relabel [docs/engines/indextts2/README.md](../docs/engines/indextts2/README.md):**
  - Top banner: "Status: WIP — isolated worker architecture in progress (see [todo/engine_install_and_switch.md](../../../todo/engine_install_and_switch.md))."
  - Drop the "Install indextts into the adapter env" path and the `TTS_INDEXTTS2_REPO_DIR` mention.
  - Keep the emotion-mode contract, alpha ranges, vector ordering, Russian/4070 caveats — these survive the rewrite.
- [ ] **No code rewrites yet** — `tts_adapter/engines/indextts2.py` is left in place for now. Phase A.1 rewrites it. Phase 0 is purely about stopping the docs/CLI from advertising the rejected design.
- [ ] Verify: `git grep TTS_INDEXTTS2_REPO_DIR` returns ONLY hits inside the engine source file (which Phase A.1 will rewrite). All docs/env/Makefile mentions are gone.

## Phase A: IndexTTS2 isolation refactor + repo-local weights convention

**Two parts.** First the architecture rewrite (the in-process engine becomes a remote client), then the repo-local weights pattern that both engines adopt.

### A.1 — Replace in-process IndexTTS2Engine with remote-service architecture

- [ ] **Reject the in-process design.** Strip [tts_adapter/engines/indextts2.py](../tts_adapter/engines/indextts2.py) of the `from indextts.infer_v2 import IndexTTS2` import path, the `repo_dir` / `sys.path` injection, and the direct `self._model.infer(...)` call. The class becomes `IndexTTS2RemoteEngine`.
- [ ] **`IndexTTS2RemoteEngine`** (new contents of `tts_adapter/engines/indextts2.py`):
  - HTTP client over `httpx` (already a dep via fastapi/httpx test stack).
  - Settings via `TTS_INDEXTTS2_URL` (default `http://localhost:9881`), `TTS_INDEXTTS2_TIMEOUT` (default 180 s).
  - `synthesize_clone(...)` POSTs to `{URL}/tts/clone` as multipart form (mirrors the main adapter's contract); returns the WAV bytes.
  - `warmup()` does a lightweight `GET {URL}/health` with a single retry — does NOT load any model itself.
  - `available_models()` returns the same single `ModelInfo(id="IndexTeam/IndexTTS-2", ...)` constant.
  - `engine_name = "indextts2"`, `supports_emotional_cloning = True` — unchanged from current.
  - `synthesize / synthesize_batch / synthesize_design` keep their `NotImplementedError` semantics.
  - **Settings `TTS_INDEXTTS2_MODEL_DIR`, `TTS_INDEXTTS2_USE_FP16`, etc. are no longer used by the engine** — they belong to the worker now. Remove them from `IndexTTS2Settings` and document them on the worker side.
- [ ] **New file: `scripts/indextts2/serve.py`** — minimal FastAPI app, runs in `vendor/index-tts/.venv`:
  - Single endpoint `/tts/clone` matching the main adapter's form contract (`text`, `reference_audio`, `emotion_audio`, `emotion_text`, `emotion_vector`, `emotion_alpha`).
  - `/health` returning `{ok: true, model_dir: ..., supports_emotional_cloning: true}`.
  - Imports `indextts.infer_v2.IndexTTS2` (available in vendor venv).
  - Reuses `tts_adapter.audio_utils.bytes_to_tempfile` + `trim_silence` via `sys.path.insert(0, <repo root>)` — these helpers have zero internal `tts_adapter` deps so cross-venv reuse is safe (verify by reading [tts_adapter/audio_utils.py](../tts_adapter/audio_utils.py) before relying on it).
  - All worker-side settings via `TTS_INDEXTTS2_*` env: `MODEL_DIR`, `CFG_PATH`, `USE_FP16`, `USE_CUDA_KERNEL`, `USE_DEEPSPEED`, `USE_RANDOM`, `TRIM_SILENCE`. Defaults same as today.
  - Listens on `TTS_INDEXTTS2_PORT` (default 9881).
- [ ] **`tts_adapter/engines/__init__.py`** — registration unchanged: `_ENGINES["indextts2"] = IndexTTS2RemoteEngine`. Same engine name, same protocol, different implementation.
- [ ] **Tests** — keep the protocol-conformance assertion (`isinstance(e, TTSEngine)`) for the remote engine. Add a unit test that mocks `httpx.Client.post` and verifies the form fields are wired correctly. The integration tests requiring a live worker get skipped via the `live_client` fixture defined in the Verification section (skips on `httpx.ConnectError`, never raises).
- [ ] **Docs** — rewrite [docs/engines/indextts2/README.md](../docs/engines/indextts2/README.md) for the two-process model: install / run worker / configure main adapter URL.

### A.2 — Repo-local weights + vendor convention (both engines)

- [ ] Add to `.gitignore`:
  ```
  models/
  vendor/
  ```
- [ ] Flip `scripts/qwen3/download_model.py` default: `~/.cache/tts-adapter/models/<name>/` → `./models/qwen3/<name>/`. Keep `--dir` override and `~/.cache/...` as a recognized path.
- [ ] Flip `scripts/indextts2/download_model.py` default: `~/.cache/tts-adapter/models/IndexTTS-2/` → `./models/indextts2/IndexTTS-2/`.
- [ ] Update post-download hint messages (printed paths) in both scripts.
- [ ] [compose.yml](../compose.yml): add a `./models:/work/models` mount alongside the existing HF cache mount.
- [ ] [.env.example](../.env.example): swap the example paths to `./models/qwen3/...` and `./models/indextts2/IndexTTS-2/`. Add the new `TTS_INDEXTTS2_URL` / `TTS_INDEXTTS2_PORT` block (worker-side settings stay commented out since they belong to the worker process, not the main adapter).
- [ ] [AGENTS.md](../AGENTS.md): update the `data/` line in the project-structure block to `models/` + `vendor/` (and drop the stale `data/cache/` reference).
- [ ] **Legacy `~/.cache/tts-adapter/` fallback warning** — single startup log line in the engine settings code paths when the user's configured path resolves to `~/.cache/tts-adapter/...`. One log line, never per-request. Reference the policy table above for the wording.

## Phase B: `make install-{qwen3,indextts2}` + `make run-indextts2`

> Hyphenated targets per the policy decision above. **No positional-arg pattern.**

- [ ] [Makefile](../Makefile) — new canonical targets:
  ```makefile
  .PHONY: install install-qwen3 install-indextts2 install-indextts \
          run-indextts2 download-model download-indextts2

  # Default `make install` keeps current behavior (uv sync only).
  install:
  	uv sync
  	@echo "Done. Run 'make install-qwen3' or 'make install-indextts2' for an engine."

  install-qwen3:
  	uv sync
  	uv run python scripts/qwen3/download_model.py
  	@echo ""
  	@echo "Add to .env:"
  	@echo "  TTS_ENGINE=qwen3"
  	@echo "  TTS_QWEN3_MODEL_PATH=./models/qwen3/Qwen3-TTS-12Hz-1.7B-CustomVoice"
  	@echo "  HF_HUB_OFFLINE=1"

  install-indextts2:
  	uv sync
  	@if [ ! -d vendor/index-tts ]; then \
  	    git clone https://github.com/index-tts/index-tts vendor/index-tts; \
  	fi
  	cd vendor/index-tts && uv sync
  	uv run python scripts/indextts2/download_model.py
  	@echo ""
  	@echo "Add to .env:"
  	@echo "  TTS_ENGINE=indextts2"
  	@echo "  TTS_INDEXTTS2_URL=http://localhost:9881"
  	@echo "  HF_HUB_OFFLINE=1"
  	@echo ""
  	@echo "Then in two terminals:"
  	@echo "  make run-indextts2   # starts the IndexTTS2 worker (port 9881)"
  	@echo "  make serve           # starts the main adapter (port 9880)"

  # Alias — keeps user-typed 'install-indextts' working.
  install-indextts: install-indextts2
  	@echo "(alias) prefer 'make install-indextts2' as canonical target"

  # Worker process — runs in vendor venv, isolated deps.
  run-indextts2:
  	@if [ ! -d vendor/index-tts ]; then \
  	    echo "vendor/index-tts not found. Run 'make install-indextts2' first."; exit 1; \
  	fi
  	cd vendor/index-tts && uv run python ../../scripts/indextts2/serve.py
  ```
- [ ] Update legacy `download-model` / `download-indextts2` targets to delegate to the canonical `install-*` (or remove if redundant — `download` is now a sub-step of `install`).
- [ ] [README.md](../README.md): rewrite Quick Start:
  ```bash
  # one-time
  make install-qwen3        # OR
  make install-indextts2    # (clones upstream + downloads weights ~6 GB)
  # paste the printed lines into .env

  # for indextts2: two terminals
  make run-indextts2   # terminal 1
  make serve           # terminal 2

  # for qwen3: one terminal
  make serve
  ```

## Phase B.5: Probe — confirm Option A really fails (one-shot)

> Throwaway. Documents *why* the architecture is split. Not committed code.

- [ ] After Phase B clones `vendor/index-tts/`, run inside the **adapter** venv (NOT the vendor venv):
  ```bash
  uv pip install -e vendor/index-tts
  uv pip check
  ```
- [ ] Capture the conflict output (expected: `transformers` and `torch` mismatches with `qwen-tts`). Paste into [docs/engines/indextts2/README.md](../docs/engines/indextts2/README.md) as the "why two processes" rationale.
- [ ] Reset the adapter venv: `rm -rf .venv && uv sync`. (Or `uv pip uninstall indextts` plus its deps — but reset is cleaner.)

## Phase C: Unified `/model/switch` (cross-engine swap)

- [ ] [tts_adapter/api/routes.py](../tts_adapter/api/routes.py): replace the current "models from current engine only" with a registry-wide view.
  ```python
  def _models_index() -> dict[str, str]:
      """{model_id: engine_name} across all registered engines."""
      from ..engines import _ENGINES
      return {m.id: name for name, cls in _ENGINES.items() for m in cls().available_models()}

  @app.get("/models")
  def list_models():
      engine = get_engine()
      available = [m for cls in _ENGINES.values() for m in cls().available_models()]
      return ModelsResponse(current=engine.model_id, available=available)
  ```
  Note: instantiating engines for metadata is cheap — no `warmup()` is called and `__init__` doesn't load the model.
- [ ] Extend `/model/switch` — handles both same-engine variant switch (Qwen3) and cross-engine swap (Qwen3 ↔ IndexTTS2-remote):
  ```python
  @app.post("/model/switch")
  def switch_model(req):
      global _engine
      idx = _models_index()
      if req.model_id not in idx:
          raise HTTPException(400, ...)
      target = idx[req.model_id]
      current = get_engine()

      if target == current.engine_name:
          # Same-engine variant switch (e.g. Qwen3 CustomVoice ↔ Base)
          if current.model_id == req.model_id:
              return SwitchModelResponse(message="Model already loaded", ...)
          current.reload(req.model_id)
      else:
          # Cross-engine swap.
          # NOTE: With remote IndexTTS2, the main adapter only releases
          # in-process GPU memory if the *current* engine holds it (Qwen3).
          # Switching TO indextts2 simply replaces the engine reference;
          # the IndexTTS2 worker process is NOT started/stopped here — the
          # operator runs `make run-indextts2` in a separate terminal.
          if hasattr(current, "_model") and current._model is not None:
              model_ref = current._model
              current._model = None
              unload_gpu_model(model_ref)
          os.environ["TTS_ENGINE"] = target
          get_settings.cache_clear()
          _engine = _ENGINES[target]()
          _engine.warmup()  # for remote engine: pings worker /health

      e = get_engine()
      return SwitchModelResponse(success=True, model=e.model_id, ...)
  ```
- [ ] Cross-engine swap caveats — surface in API docs + response message:
  - Server briefly unavailable during reload (same as today's variant switch).
  - **Switching to indextts2 requires the worker process to already be running** (`make run-indextts2`). Switch returns 503 if `IndexTTS2RemoteEngine.warmup()`'s health-ping fails.
  - In-flight requests on the old engine may collide.
  - Runtime swap does NOT persist across restart — permanent change still requires `.env` edit.
- [ ] Tests in `tests/test_engine_switch.py` (new file):
  - Unit: `_models_index()` returns expected ids across both engines.
  - Unit: `IndexTTS2RemoteEngine` with mocked `httpx` → verify form-field wiring.
  - Integration (skip if not both engines available): switch qwen3→indextts2→qwen3, verify `/health.engine` updates.
  - Integration (skip if worker not running): switch to indextts2 with no worker → expect 503 with actionable error message.

## Phase D: Web UI (follow-on — split if needed)

- [ ] [tts_adapter/web/templates_body.py](../tts_adapter/web/templates_body.py): on the Voice Clone tab, render emotion controls (audio upload / text / 8-float vector + alpha slider) **conditional on `supports_emotional_cloning`** from `/health`.
- [ ] [tts_adapter/web/templates_script.py](../tts_adapter/web/templates_script.py): the existing periodic `/health` poller (see [todo/multi_client_sync.md](multi_client_sync.md) for context) toggles the emotion controls visibility when the flag flips after a model switch.
- [ ] Model dropdown: replace the current Qwen3-variants-only list with the union from `/models`. Include the engine name in each option's label (e.g. `[qwen3] Base 1.7B`, `[indextts2] IndexTTS-2`). Switch button calls the same `/model/switch`.
- [ ] [tts_adapter/web/templates_i18n.py](../tts_adapter/web/templates_i18n.py): add labels for emotion-mode dropdown, alpha slider, and the cross-engine switch warning ("This will unload the current engine and load…").

## Verification

### Test infrastructure fixes (apply alongside Phase A.1)

- [ ] **Add a `live_client` fixture** in `tests/conftest.py` (new file) so integration tests skip cleanly when no server/worker is running — currently they raise `httpx.ConnectError` which surfaces as ERROR not SKIP:
  ```python
  @pytest.fixture
  def live_client():
      client = httpx.Client(base_url="http://localhost:9880", timeout=30.0)
      try:
          client.get("/health")
      except httpx.ConnectError:
          pytest.skip("Live server not running at localhost:9880")
      return client
  ```
  Use `live_client` in every test that calls the API. Reserve the bare `client` fixture for tests that intentionally exercise connection failure.
- [ ] **Stop accepting 400 as success** in [tests/test_emotion_cloning.py](../tests/test_emotion_cloning.py). The current `assert response.status_code in {200, 400}` lets generation be silently broken. Split into:
  - **Validation tests** (silent minimal WAV, `expect == 400`) — rejection paths only.
  - **Real integration tests** (uses a real reference WAV from `tests/fixtures/`, `expect == 200 and content-type == "audio/wav"`) — gated by `live_client`.
  - Real fixtures live under `tests/fixtures/voice_3s.wav` (and `emo_*.wav` for emotion-audio mode); add a one-line README in that folder describing license / source.
- [ ] **Strengthen the upload-size test** — `_MAX_UPLOAD_BYTES == 20 * 1024 * 1024` only proves the constant. Replace with a real rejection test:
  ```python
  class _FakeUpload:
      def __init__(self, size): self.size = size

  def test_oversized_upload_rejected_413():
      with pytest.raises(HTTPException) as exc:
          _validate_upload_size(_FakeUpload(_MAX_UPLOAD_BYTES + 1), "reference_audio")
      assert exc.value.status_code == 413

  def test_unknown_size_passes():
      _validate_upload_size(_FakeUpload(None), "reference_audio")  # no raise
  ```

### End-to-end happy path

- [ ] **Fresh-clone happy path** (in a scratch dir):
  ```bash
  git clone <repo> tts-adapter-test && cd tts-adapter-test
  make install-indextts2
  # paste printed env lines into .env

  # Two terminals (or backgrounded):
  make run-indextts2        # terminal 1 — IndexTTS2 worker on :9881
  make serve                # terminal 2 — main adapter on :9880

  curl -F 'text=hi' -F 'reference_audio=@voice.wav' -F 'emotion_text=excited' \
       http://localhost:9880/tts/clone -o out.wav
  ```
- [ ] **Cross-engine switch** (worker must be running for the indextts2 leg):
  ```bash
  curl -X POST http://localhost:9880/model/switch \
       -H 'content-type: application/json' \
       -d '{"model_id":"IndexTeam/IndexTTS-2"}'
  curl http://localhost:9880/health   # engine should now be indextts2
  curl -X POST http://localhost:9880/model/switch \
       -H 'content-type: application/json' \
       -d '{"model_id":"Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"}'
  curl http://localhost:9880/health   # back to qwen3
  ```
- [ ] **Switch with no worker → 503**: stop `run-indextts2`, then attempt the switch — expect a 503 with a hint to start the worker.
- [ ] **Legacy fallback warning**: set `TTS_*_MODEL_PATH=~/.cache/tts-adapter/...`, start server, verify ONE warning line at startup, NO per-request warnings.
- [ ] **Regression**: existing 19 unit tests still pass; existing Qwen3 CLI (`make tts-clone`) unchanged; the in-process IndexTTS2 unit tests get rewritten to mock httpx.
- [ ] **Docker happy path** — **deferred**. Requires a `Dockerfile.indextts2` + a second compose service `adapter-tts-indextts2` + healthcheck + volume mount alignment. Local two-terminal worker is the v1 happy path. Re-enable Docker verification once that scaffolding lands as a follow-up todo.

---

## Scope guardrails

- **Do not import `indextts` into the main adapter process** — Option C is the only solid architecture. Any direct import or `sys.path` injection of vendor venv site-packages is **rejected**.
- **Do not auto-edit `.env`** — print + paste only.
- **Do not silently keep `~/.cache/tts-adapter/` forever** — warn once at startup; remove in next minor.
- **Do not load both engine workers simultaneously** — VRAM doesn't allow on 4070 12 GB.
- **Do not auto-manage the IndexTTS2 worker process from the main adapter** — operator runs `make run-indextts2`. Switching to indextts2 with no worker returns 503, not "auto-start."
- **Do not split the engine swap into a new endpoint** — `/model/switch` handles both same-engine and cross-engine.
- **Do not introduce a `/engine/switch` endpoint** — redundant with the unified `/model/switch`.
- **Do not use the positional-arg Make pattern (`make install indextts`)** for engine targets — hyphenated `make install-indextts2` is canonical, `install-indextts` is the alias only.

## Execution order

1. **Phase 0** — architecture-drift cleanup. **BLOCKING**. After this, the repo no longer advertises the rejected in-process design.
2. **Phase A.1** — IndexTTS2 isolation refactor (engine becomes remote client, new worker `serve.py`). Largest blast radius — verify in isolation before A.2.
3. **Test-infra fix** — `live_client` fixture + tightened upload/validation tests (can land in the same PR as A.1 since both touch the test layer).
4. **Phase A.2** — `models/<engine>/<name>/` + `vendor/` repo-local convention + legacy-fallback warning.
5. **Phase B** — `make install-{qwen3,indextts2}` + `make run-indextts2`.
6. **Phase B.5** — One-shot Option-A probe to document the conflict in `docs/engines/indextts2/README.md`.
7. **Phase C** — Unified `/model/switch` (cross-engine). Depends on A.1 (final engine shape).
8. **Phase D** — Web UI: emotion controls + cross-engine model dropdown.

**Hard rule:** do **not** start Phase C, B, or any feature work until Phase 0 lands. Otherwise we're polishing on top of a contradiction.
