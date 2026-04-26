# Per-Engine Inference Progress (multi-worker SSE)

> **When complete:** move this file to `todo/done/` (do not delete).
> **Design doc:** approved plan at `~/.claude/plans/search-web-carefully-is-merry-aurora.md`
> **Why:** all 3 engines block `/tts/clone` for 4-30 s with only an indeterminate spinner. Users can't tell whether work is happening, how far along, or how long left. Confirmed by user observation of cold-compile waits on VoxCPM2.

**Engine progress capabilities (verified upstream):**
- `qwen3` -> opaque (no callback, no streaming) -> ESTIMATE-only
- `indextts2` -> `_set_gr_progress(value, desc)` hook at [vendor/index-tts/indextts/infer_v2.py:322-324](../vendor/index-tts/indextts/infer_v2.py) -> MILESTONE (real, but coarse: 0/0.1/0.2-0.9/0.9)
- `voxcpm2` -> `streaming=True` mode yields chunks at [vendor/voxcpm/src/voxcpm/core.py:295](../vendor/voxcpm/src/voxcpm/core.py); inference_timesteps drives a tqdm bar inside upstream -> CHUNK (count yielded chunks)

---

## Execution order (strict)

1. **Phase 1** - estimate-only progress for ALL engines, NO server changes (~half day, pure UI win)
2. **Phase 2** - real SSE for indextts2 + voxcpm2, falls back to estimate for qwen3 (~1.5 days, only if Phase 1 isn't enough)
3. **Phase 3** - verification

---

## Phase 1 - estimate-only UX (no worker / SSE changes)

> Goal: every generation shows a determinate bar that fills based on text length x measured wall-time-per-audio-second, with rotating status text. **Phase 1 DOES touch the server-side API surface** (new `EngineProgressInfo` capability flag in `/health` + `/engines`) - but workers stay untouched, no SSE, no async job system, no background tasks. Pure additive capability + UI win.

### Capability flag (additive only)

- [ ] **`tts_adapter/contract.py`** (EDIT) - add new model:
  ```python
  class EngineProgressInfo(BaseModel):
      granularity: Literal["none", "estimate", "milestone", "chunk", "step"] = "none"
      # NOTE: explicitly NOT named `rtf` - the engineering convention for
      # real-time factor is wall/audio (>1 = slower than realtime, <1 = faster).
      # Naming the field this way prevents misuse / inversion bugs.
      wall_seconds_per_audio_second: float = 1.0
      typical_load_seconds: float = 0.0      # cold-start overhead per first call (warmup/compile)
      chars_per_audio_second: float = 14.0   # used to convert text length -> expected audio duration
      stages: list[str] = []                 # i18n keys: ["progress.stage.encoding_ref", ...]
  ```
  Add `progress: EngineProgressInfo` to `HealthResponse`, `EngineInfo`, `ModelInfo`. Default = `EngineProgressInfo()` (no progress).
- [ ] **`tts_adapter/engine.py`** (EDIT) - add `progress: EngineProgressInfo` Protocol property (mirror `generation_params` pattern - module-level `_PROGRESS` constant per engine).

### Per-engine declarations

Initial values (start here; refine based on observed wall time once shipped):

- [ ] **`tts_adapter/engines/qwen3.py`** - `granularity="estimate"`, `wall_seconds_per_audio_second=0.4`, `typical_load_seconds=0`, `chars_per_audio_second=14`, stages: `["progress.stage.generating"]`
- [ ] **`tts_adapter/engines/indextts2.py`** - `granularity="estimate"`, `wall_seconds_per_audio_second=1.5`, `typical_load_seconds=2.0`, `chars_per_audio_second=14`, stages: `["progress.stage.encoding_ref", "progress.stage.generating", "progress.stage.synthesizing"]`
- [ ] **`tts_adapter/engines/voxcpm2.py`** - `granularity="estimate"`, `wall_seconds_per_audio_second=1.3`, `typical_load_seconds=30.0` (cold torch.compile), `chars_per_audio_second=14`, stages: `["progress.stage.encoding_ref", "progress.stage.generating", "progress.stage.synthesizing"]`

### Estimate formula (frozen contract for the UI)

```
estimated_audio_seconds = max(1.5, text_length / chars_per_audio_second)
estimated_wall_seconds  = estimated_audio_seconds * wall_seconds_per_audio_second
if not health.loaded:
    estimated_wall_seconds += typical_load_seconds
estimated_wall_seconds  = max(2.0, estimated_wall_seconds)   # never show silly 0.2 s
```

**Warmup overhead source-of-truth: `health.loaded` from the server**, NOT a JS-only `engineWarmupDone` map. `/model/switch`, worker restart, or container restart can flip `loaded` back to false; the JS map would lie. Local cache-of-last-loaded-engine is OK as a smoothing hint but only as a tiebreaker.

### Routes surface it

- [ ] **`tts_adapter/api/routes.py`** - add `progress=engine.progress` to `health()`, `_engine_info()`, `_switch_response()` (3 places, mirrors how `emotion_modes` was added in the previous engine pass).

### UI consumes it

- [ ] **`tts_adapter/web/templates_i18n.py`** (EDIT) - add EN+RU strings:
  - `progress.stage.encoding_ref` = "Кодирование референса" / "Encoding reference"
  - `progress.stage.generating` = "Генерация речи" / "Generating speech"
  - `progress.stage.synthesizing` = "Сборка аудио" / "Synthesizing audio"
  - `progress.stage.warmup` = "Прогрев модели..." / "Warming up model..."
  - `progress.eta_seconds` = "осталось ~{s} с" / "~{s}s left"
  - `progress.still_working` = "Ещё работаю..." / "Still working..." - shown after the bar reaches 95% but the response hasn't arrived yet (so the user never sees a flat "0s left" forever)
- [ ] **`tts_adapter/web/templates_style.py`** (EDIT) - convert `.progress-bar-inner` so it can take a JS-driven `width` style instead of CSS keyframe animation. Keep keyframe as fallback when `granularity == "none"`.
- [ ] **`tts_adapter/web/templates_script.py`** (EDIT):
  - Extend `setProgressVisible(visible, label, hint)` -> `setProgressVisible(visible, {labelKey, hintKey, mode, estimatedSeconds, stages})`
  - New `tickEstimatedProgress(estimatedSeconds, stages)`:
    - On show, record `t0 = performance.now()`, store stages array, set bar to 0%
    - `setInterval(tick, 100)`:
      - `frac = min(elapsed / estimatedSeconds, 0.95)` (cap at 95% so the bar never claims "done" before the actual response)
      - update `bar.style.width = (frac * 100) + "%"`
      - rotate stage text every `estimatedSeconds / stages.length` seconds: `progress.label = t(stages[currentStage])`
      - update ETA hint: `progress.hint = t("progress.eta_seconds").replace("{s}", Math.max(0, Math.ceil(estimatedSeconds - elapsed)))`
      - **When `frac >= 0.95`**: switch hint to `t("progress.still_working")` (no more flat "0s left"), keep the indeterminate animation overlay if available
    - On hide / response arrival: clear interval, snap to 100% then fade out
  - In `generateSimple()`/`generateDesign()`/`generateClone()`:
    - Apply the **frozen estimate formula** above using `serverInfo.progress.*` and `serverInfo.loaded` (server is source of truth for warmup state).
    - Optional smoothing: keep a local `engineLastLoadedSeen[engine]` to add a small grace window when `loaded` flickers between polls. NOT a substitute for `serverInfo.loaded`.
    - Call `setProgressVisible(true, { mode: "estimate", estimatedSeconds, stages: serverInfo.progress.stages })`

### Phase 1 verification

- [ ] `curl localhost:9880/health | jq .progress` shows the right `typical_rtf` per active engine
- [ ] Generate a 50-char Russian text on VoxCPM2 -> bar smoothly fills over ~3 s, snaps to 100% on response arrival
- [ ] Switch to qwen3 -> bar fills over ~1 s for the same text, ETA visible in label
- [ ] First call after engine switch on VoxCPM2 -> bar shows ~30 s warmup overhead first, then ticks generation. No more "stuck spinner" feeling
- [ ] Existing 72-test pytest suite stays green (no regression - all changes are additive)

---

## Phase 2 - real SSE for engines that can (optional)

> Only do this if Phase 1 estimate isn't accurate enough in practice. Phase 1 fixes 90% of the perceived-slowness pain.

### New protocol (backwards-compatible)

```
Browser
  |
  +- POST /tts/clone?stream=1  --> 202 + {request_id, progress_url, result_url}
  |
  +- GET /tts/progress/<id>  --> SSE stream of {step, total, stage, eta_seconds}
  |
  +- GET /tts/result/<id>    --> 200 WAV when done | 202 if pending | 404 if expired
```

POST without `?stream=1` keeps today's exact contract (returns WAV bytes synchronously). No client breakage.

### New module

- [ ] **`tts_adapter/api/progress.py`** (CREATE) - `ProgressJobRegistry`:
  - In-process `dict[str, JobState]`. Single-process. **No Redis.**
  - `JobState`: `{queue: asyncio.Queue, status: "running"|"done"|"error", result_bytes: bytes|None, error: str|None, created_at: float}`
  - `create_job() -> request_id` (uuid4)
  - `enqueue_event(id, event)` - event is a dict matching the **frozen event schema** below
  - `drain_events(id) -> AsyncIterator[dict]` - yields events until `status != "running"`, then yields a terminal event
  - `set_result(id, wav_bytes)` / `set_error(id, message)`
  - `gc_old_jobs(ttl=300)` - run on each `create_job()` call
  - **Soft caps**: `MAX_ACTIVE_JOBS = 4` (refuse `create_job()` with 503 when exceeded; protects against runaway clients), `JOB_RESULT_TTL = 300 s`
- [ ] **`tests/test_progress.py`** (CREATE) - unit + integration:
  - `ProgressJobRegistry` create/enqueue/drain/cleanup
  - `?stream=1` returns 202 + URLs
  - `GET /tts/progress/<id>` SSE format conforms to spec (`data: {...}\n\n`)
  - `GET /tts/result/<id>` returns 200 WAV only after status=done
  - Expired job (TTL passed) -> 404
  - 5th concurrent job -> 503 (cap enforcement)
  - Worker-side registry parity (mock httpx for the forwarding case)

### Frozen event schema (one shape, all engines)

Engines emit the SAME shape regardless of granularity. Avoids divergent frac/value/step/stage variants across engines.

```json
{
  "type": "progress",
  "fraction": 0.42,
  "step": 4,
  "total": 10,
  "stage": "progress.stage.generating",
  "eta_seconds": 12
}
```

Terminal events:

```json
{"type": "done"}
{"type": "error", "message": "..."}
```

Engines that don't know `step`/`total` (milestone-only) populate `fraction` + `stage` and leave step/total null. Engines that don't know `eta_seconds` leave it null - UI computes from `fraction` + elapsed.

### Engine + worker hooks

- [ ] **`tts_adapter/engine.py`** - add optional kwarg `progress_callback: Callable[[dict], None] | None = None` to `synthesize_*()`. Engines with `granularity != "estimate"` MUST honor it; others ignore.
- [ ] **`scripts/voxcpm2/serve.py`** + **`scripts/indextts2/serve.py`** - each worker maintains its OWN local `ProgressJobRegistry` (cross-process state); each adds `?stream=1` -> 202 + own progress/result endpoints.
- [ ] **`tts_adapter/engines/voxcpm2.py`** - when `progress_callback` is set:
  - POST worker `?stream=1`
  - Open streaming GET to worker's `/progress/<id>`, parse SSE lines, invoke `progress_callback` per event
  - Final `result_url` GET returns the WAV bytes
- [ ] **`tts_adapter/engines/indextts2.py`** - same shape as voxcpm2
- [ ] **IndexTTS2 worker hook (engine-specific)** - on `_load_model()`, set `_model.gr_progress = lambda value, desc: registry.enqueue_event(current_id, {"frac": value, "stage": desc})`. Granularity `"milestone"`. **No upstream patch** - just inject our callable into the existing `gr_progress` field.
- [ ] **VoxCPM2 worker hook (engine-specific)** - use the **upstream-verified streaming API** (do not invent a method name). Per [vendor/voxcpm/src/voxcpm/core.py:295](../vendor/voxcpm/src/voxcpm/core.py): the canonical entry is `model.generate(..., streaming=True)` which returns a generator yielding chunks (not a separate `generate_streaming` method). Confirm the exact call shape during implementation by reading the current upstream source - if upstream renames or refactors before this lands, follow what upstream actually exposes. Count yielded chunks: `for i, chunk in enumerate(gen): registry.enqueue_event(id, {"type": "progress", "step": i, "total": inference_timesteps, "fraction": i/inference_timesteps, "stage": "progress.stage.generating"})`. Concatenate chunks into final WAV. Granularity `"chunk"`. **One wrong method name breaks the entire SSE worker - re-verify the API in Phase 2 before coding.**

### Routes

- [ ] **`tts_adapter/api/routes.py`** (EDIT):
  - `POST /tts/clone`, `/tts`, `/tts/design` accept `?stream: bool = False`. When true:
    - `request_id = registry.create_job()` (returns 503 if at MAX_ACTIVE_JOBS)
    - kick off background coroutine that **runs the blocking synth call in a thread**:
      ```python
      import anyio
      async def run_job():
          try:
              wav = await anyio.to_thread.run_sync(
                  lambda: engine.synthesize_clone(
                      ..., progress_callback=lambda ev: registry.enqueue_event(request_id, ev),
                  )
              )
              registry.set_result(request_id, wav)
          except Exception as e:
              registry.set_error(request_id, str(e))
      asyncio.create_task(run_job())
      ```
      **Critical:** engines do GPU/blocking work. Calling them directly inside an async task stalls the FastAPI event loop and freezes /health polls. `anyio.to_thread.run_sync` is the correct primitive.
    - return 202 + `{"request_id": id, "progress_url": f"/tts/progress/{id}", "result_url": f"/tts/result/{id}"}`
  - `GET /tts/progress/<id>` -> `StreamingResponse(generator, media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})`. For remote engines, opens streaming GET to worker's `/progress/<id>` and forwards lines through. For in-process engines, drains the local registry.
  - `GET /tts/result/<id>` -> 200 WAV | 202 still-running | 404 expired/unknown.

### UI logic ladder

- [ ] **`tts_adapter/web/templates_script.py`** - on POST /tts/clone, branch on `serverInfo.progress.granularity`:
  1. `"step"|"chunk"` -> POST `?stream=1` -> open `EventSource(progress_url)` -> drive bar from real events -> `fetch(result_url)` on done
  2. `"milestone"` -> same SSE path, but bar snaps to milestone fractions; label = stage from event
  3. `"estimate"` -> Phase 1 timer-based (no SSE)
  4. `"none"` -> indeterminate animation (today's behavior)
  - Common error path: SSE `error` event -> close, surface as the same JSON-error toast we built for /tts/clone 502.

### Phase 2 verification

- [ ] `tests/test_progress.py` green
- [ ] Live: VoxCPM2 generation shows bar incrementing 0% -> 100% over ~3 s with chunk count visible
- [ ] Live: IndexTTS2 generation snaps through "Encoding text" -> "Generating tokens" -> "Synthesizing audio"
- [ ] Live: Kill worker mid-stream -> SSE closes with error event -> UI shows error toast (no silent stall)
- [ ] **Regression**: `curl -X POST /tts/clone` (no `?stream=1`) returns WAV bytes, same shape as today. All existing pytest stays green.

---

## Phase 3 - documentation + final regression

- [ ] **`docs/architecture.md`** - add a "Progress" section explaining the 3-URL contract (POST + SSE GET + result GET), the granularity ladder, and the in-process registry choice
- [ ] **`docs/engines/qwen3/README.md`** + **`indextts2/README.md`** + **`voxcpm2/README.md`** - one paragraph each on the engine's progress granularity and `typical_rtf`
- [ ] **`README.md`** - one-line note that `?stream=1` exists for clients that want progress events
- [ ] Full pytest + e2e curl on all 3 engines, both `?stream=1` and legacy paths

---

## Scope guardrails

- **Do NOT** add Redis / Celery / task queues. Single-host, single-user, single-RTX 4070. `asyncio.Queue` per request_id covers everything we need.
- **Do NOT** patch upstream VoxCPM2 inference loop. The chunk-count approach via `streaming=True` is good enough for a fill animation. Forking upstream is a maintenance trap.
- **Do NOT** implement real audio streaming via MediaSource API. Browser support is finicky (Safari/mobile broken) and the win (~1 s earlier audio start) doesn't match the work. Defer until we ship long-form content.
- **Do NOT** use WebSockets. Progress is one-way server -> client; SSE is the right primitive.
- **Do NOT** mix audio + progress events in one stream. Two URLs (`/progress/<id>` SSE + `/result/<id>` GET) is simpler than multiplexing.
- **Do NOT** break the existing `POST /tts/clone -> WAV bytes` contract. `?stream=1` is opt-in. CLI users + `make tts-clone` keep working unchanged.
- **Do NOT** branch on `engine.engine_name` in routes. The `granularity` enum is the dispatch key.

---

## Reuse / patterns

- The `EngineProgressInfo` capability flag mirrors the existing `EngineInfo` / `GenerationParam` / `emotion_modes` pattern in [tts_adapter/contract.py](../tts_adapter/contract.py).
- The `_filter_gen_kwargs_for_engine` route-level filter pattern in [tts_adapter/api/routes.py](../tts_adapter/api/routes.py) is the model for how routes adapt requests to engine capabilities.
- The `tests/test_emotion_cloning.py` mock-httpx pattern at lines 88-100 is the template for `tests/test_progress.py` SSE-forwarding tests.
- The two-phase rollback in `/model/switch` is the pattern for the cross-engine atomic guarantee (don't break it when adding background tasks).
