# Add IndexTTS2 Engine  -  Emotional Voice Cloning

> WARNING **SUPERSEDED for implementation architecture.**
> The in-process engine pattern this file describes was rejected post-review (dependency conflict between `qwen-tts` and `indextts`  -  `transformers==4.57.3` vs `transformers==4.52.1`, `torch==2.8.*`, `deepspeed==0.17.1`). The current source of truth is **[engine_install_and_switch.md](engine_install_and_switch.md) Phase A.1** (`IndexTTS2RemoteEngine` + isolated worker process).
>
> **What stays valid in this file:**
> - The motivation (Qwen3 limitation: cannot combine clone + emotion)
> - The emotion contract (3 modes: audio / text / 8-dim vector; alpha range; vector ordering)
> - API validation rules (one-mode-only, alpha bounds, vector length, upload size)
> - Russian-quality and 4070-12GB benchmark notes
>
> **What is rejected:**
> - In-process `IndexTTS2Engine` class
> - `TTS_INDEXTTS2_REPO_DIR` / `sys.path` injection
> - Any plan step that imports `indextts` from the main adapter venv
>
> Do NOT pick between this file and the new one. The new one wins for architecture.

> **When complete:** move this file to `todo/done/` (do **not** delete).
> **Context doc:** approved plan at `~/.claude/plans/search-web-carefully-is-merry-aurora.md`
> **Why:** Qwen3-TTS cannot combine clone + emotion (model-architecture limitation  -  see [docs/engines/qwen3/README.md:33-35](../docs/engines/qwen3/README.md)). IndexTTS2 (Bilibili, Sept 2025) solves this via disentangled timbre/emotion conditioning. **Qwen3 stays the default**; IndexTTS2 is an additive second engine.

**Engine role split:**
- `qwen3` -> Russian / multilingual / general cloning (current default)
- `indextts2` -> emotional voice cloning (new)
- `cosyvoice2` (0.5B) -> fallback if IndexTTS2 is too slow/heavy on RTX 4070 12 GB

---

## Execution order (strict)

1. **Phase 0**  -  upstream proof on RTX 4070 12 GB (go/no-go gate)
2. **Qwen3 regression baseline**  -  run existing Qwen3 smoke tests and record golden outputs *before* any refactor
3. **Phase 1.5**  -  extract shared helpers (pure refactor, Qwen3 regressions must pass unchanged)
4. **Phase 1**  -  protocol flags + `available_models()`
5. **Phase 2**  -  IndexTTS2 engine
6. **Phase 3**  -  API validation + route wiring
7. **Phase 7**  -  4070 benchmark + A/B emotion subjective test

Phases 4 (install), 5 (CLI), 6 (docs) run alongside 2-3 as needed.

---

## Phase 0: Upstream proof  -  before touching adapter contract

**Goal:** validate IndexTTS2 works on the target hardware *before* we commit to any adapter changes. If upstream can't run reliably, we stop here and pivot to CosyVoice 2.

- [ ] Clone official repo: `git clone https://github.com/index-tts/index-tts && cd index-tts && uv sync` (use the official `uv` path  -  do **not** improvise with `pip install git+...`; upstream warns non-standard installs cause random dep/GPU bugs)
- [ ] Download checkpoints: `hf download IndexTeam/IndexTTS-2 --local-dir checkpoints`
- [ ] Run official `infer_v2` example unchanged  -  confirm model loads on RTX 4070 12 GB
- [ ] Run all three emotion modes against the same `spk_audio_prompt`:
  1. `emo_audio_prompt` (emotion reference WAV)
  2. `emo_text` with `use_emo_text=True`
  3. `emo_vector=[h,a,s,af,d,m,su,c]` (8 floats)
- [ ] Measure & record for each mode:
  - max VRAM (`nvidia-smi` peak)
  - wall time
  - generated audio duration
  - RTF (elapsed / audio_seconds)
  - whether Russian text produces acceptable output (the model is CN/EN/JP-trained  -  Russian is not guaranteed)
- [ ] **Go/no-go decision** based on the above. If RTF > ~3x or Russian is broken -> pivot to CosyVoice 2.

## SOLID & reuse alignment (read before any coding)

Before writing IndexTTS2, audit what already exists in the repo and **reuse, don't duplicate**. Summary of the audit (grep-verified):

| Existing helper | Location | Engine-agnostic? | Action |
|---|---|---|---|
| `_trim_silence(wav, sr, pad_seconds)` | [qwen3.py:319](../tts_adapter/engines/qwen3.py) | [ready] pure numpy | **Extract to `tts_adapter/audio_utils.py`**  -  reuse in IndexTTS2 |
| GPU reload pattern (`lock` + `gc.collect()` + `torch.cuda.empty_cache()`) | [qwen3.py:402-418](../tts_adapter/engines/qwen3.py) | [ready] | **Extract to `tts_adapter/gpu_utils.py`** as `unload_gpu_model(model_ref)`  -  reuse in IndexTTS2 |
| Bytes -> WAV tempfile (for `reference_audio`) | [qwen3.py:248-256](../tts_adapter/engines/qwen3.py) | [ready] | **Extract as context manager** `bytes_to_tempfile(data, suffix) -> path` in `tts_adapter/audio_utils.py`. IndexTTS2 will need it twice (speaker + emotion audio). |
| `_collect_gen_kwargs(...)` | [routes.py:228](../tts_adapter/api/routes.py) | [ready] route-level | **Already shared**  -  reuse in extended `/tts/clone`. No action. |
| `_sanitize_id` | [routes.py:178](../tts_adapter/api/routes.py) | [ready] route-level | Already shared. No action. |
| `_GEN_KWARG_KEYS` / `_filter_gen_kwargs` | [qwen3.py:51,153](../tts_adapter/engines/qwen3.py) | [no] qwen3-specific params | **Keep per-engine**  -  IndexTTS2 has a different generation-kwarg surface. |
| `_resolve_speaker` / `_resolve_language` | [qwen3.py:130,141](../tts_adapter/engines/qwen3.py) | [no] qwen3 concepts (preset speakers) | **Keep per-engine**  -  IndexTTS2 has no preset speakers. |

**SOLID application:**
- **S (Single Responsibility):** `audio_utils.py` owns audio-shape ops; `gpu_utils.py` owns GPU-lifecycle ops; each engine owns only its backend-specific inference.
- **O (Open/Closed):** engine registry `_ENGINES` dict and `TTSEngine` Protocol already satisfy this  -  IndexTTS2 plugs in without touching Qwen3.
- **L (Liskov):** both engines must satisfy the full `TTSEngine` Protocol; unsupported methods raise `NotImplementedError` with actionable message (current pattern  -  keep it).
- **I (Interface Segregation):** **decision  -  keep capability flags (`supports_*` bools), do NOT split the Protocol into sub-protocols.** The flags + `NotImplementedError` pattern is simpler and already in use; splitting adds indirection without new capability. Exception: the new `supports_emotional_cloning` flag follows the same pattern.
- **D (Dependency Inversion):** routes depend on `TTSEngine` Protocol, not concrete classes  -  already holds. Add `engine.model_info()` / `engine.available_models()` to keep it that way (no `isinstance` / `engine_name` branching in routes).

**Type hints:** match existing style  -  `str | None` (PEP 604), `list[float]`, keyword-only via `*` (as already used in qwen3 `synthesize_clone`). Use `Protocol` types from the existing engine.py, not new ones.

---

## Phase 1: Contract  -  protocol & response models

- [ ] Extend [tts_adapter/engine.py](../tts_adapter/engine.py) `TTSEngine` protocol:
  - Add `supports_emotional_cloning: bool` property
  - Add `available_models() -> list[ModelInfo]` method (engines own their metadata  -  **no engine-name branching in routes**). Existing `model_id` property already covers "which is current"; **do not add** a separate `model_info()`  -  one accessor is enough.
  - Extend `synthesize_clone()` signature with **keyword-only** optional params:
    - `emotion_audio: bytes | str | None = None`
    - `emotion_text: str | None = None`
    - `emotion_vector: list[float] | None = None` (8 floats, order fixed: `[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]`)
    - `emotion_alpha: float = 1.0`
  - Engine internals may silently ignore unknown kwargs. **API is responsible** for rejecting emotion params against non-supporting engines (see Phase 3).
- [ ] Extend [tts_adapter/contract.py](../tts_adapter/contract.py):
  - Add `supports_emotional_cloning: bool = False` to `HealthResponse`, `ModelInfo`, `SwitchModelResponse`
- [ ] Update [tts_adapter/engines/qwen3.py](../tts_adapter/engines/qwen3.py): add `available_models()` returning the 4-entry list currently hardcoded in [routes.py:72-105](../tts_adapter/api/routes.py) (moved verbatim), and `supports_emotional_cloning: bool = False` property. No behavior change.

## Phase 1.5: Extract shared utilities (BEFORE creating IndexTTS2 engine)

> Pure refactor  -  Qwen3 behavior must be byte-identical after this phase.

- [ ] Create `tts_adapter/audio_utils.py`:
  - `trim_silence(wav, sr, pad_seconds=0.05)`  -  move from `Qwen3Engine._trim_silence` (make module-level; drop `self`)
  - `bytes_to_tempfile(data: bytes, suffix: str = ".wav") -> contextmanager`  -  extract the pattern from `qwen3.py:248-256`; yields path, unlinks on exit even on exception
- [ ] Create `tts_adapter/gpu_utils.py`:
  - `unload_gpu_model(model_ref)`  -  gc + `torch.cuda.empty_cache()`; guards `torch.cuda.is_available()`
- [ ] Refactor `Qwen3Engine` to use the new helpers (import from `..audio_utils`, `..gpu_utils`). Delete the inlined versions. **Run existing Qwen3 smoke tests  -  must pass unchanged.**

## Phase 2: IndexTTS2 engine

- [ ] Create `tts_adapter/engines/indextts2.py`  -  **reuse `audio_utils.trim_silence`, `audio_utils.bytes_to_tempfile`, `gpu_utils.unload_gpu_model`** (do not re-implement). Mirror shape of [qwen3.py](../tts_adapter/engines/qwen3.py):
  - `IndexTTS2Settings(BaseSettings)` with env prefix `TTS_INDEXTTS2_`:
    - `model_dir: str`  -  checkpoints directory (required)
    - `cfg_path: str | None`  -  default `{model_dir}/config.yaml`
    - `repo_dir: str | None`  -  optional path to cloned `index-tts` repo (for Python import)
    - `use_fp16: bool = True`
    - `use_cuda_kernel: bool = False`  -  benchmark before enabling
    - `use_deepspeed: bool = False`  -  official docs note may be faster or slower depending on hardware
    - `use_random: bool = False`  -  **default False for clone fidelity**. Upstream warns random sampling can reduce cloning quality. Pass through to `infer(use_random=...)`.
    - `trim_silence: bool = False`  -  **default False**. Emotional speech includes breaths / pauses / expressive endings that trimming would cut. Opt-in only if Phase 0 shows bad leading/trailing silence.
  - **Do NOT pass `device`** to `IndexTTS2(...)` constructor  -  upstream constructor does not expose it. Control GPU via `CUDA_VISIBLE_DEVICES` in the process environment instead. (Verify constructor signature in Phase 0.)
  - `IndexTTS2Engine` class:
    - Lazy `from indextts.infer_v2 import IndexTTS2` in `warmup()`. If missing -> raise `RuntimeError` with exact install steps pointing to `docs/engines/indextts2/README.md`.
    - Construct with `cfg_path`, `model_dir`, `use_fp16`, `use_cuda_kernel`, `use_deepspeed`  -  **no other kwargs** until verified upstream.
    - `synthesize_clone(text, reference_audio, *, emotion_audio=None, emotion_text=None, emotion_vector=None, emotion_alpha=1.0, **kwargs) -> bytes`:
      - Use `bytes_to_tempfile(reference_audio)` context manager (nested for `emotion_audio` if provided)  -  **reused helper, no inline tempfile code**
      - Dispatch to `self._model.infer(spk_audio_prompt=..., emo_audio_prompt=..., use_emo_text=(emotion_text is not None), emo_text=emotion_text, emo_vector=emotion_vector, emo_alpha=emotion_alpha, use_random=self._use_random, text=..., output_path=<output_tempfile>)`
      - Read output WAV bytes. **Do NOT trim by default**  -  emotional speech relies on breaths, pauses, and expressive tails that `trim_silence` would cut. Apply `trim_silence` only if `TTS_INDEXTTS2_TRIM_SILENCE=true`. (Decision point revisits in Phase 0 based on observed output.)
      - `_lock` around the `infer()` call for GPU serialization (same pattern as Qwen3)
    - `synthesize()`, `synthesize_batch()`, `synthesize_design()` -> `raise NotImplementedError("IndexTTS2 supports /tts/clone only. Use Qwen3 for preset speakers.")`
    - `reload(model_dir)` -> call `gpu_utils.unload_gpu_model(self._model)` under lock, then re-warmup (**reuses shared helper**  -  same lifecycle as Qwen3)
    - `model_info()` -> single `ModelInfo(id="IndexTeam/IndexTTS-2", name="IndexTTS-2", variant="Base+Emotion", supports_cloning=True, supports_emotional_cloning=True, supports_design=False, supports_custom_voice=False)`
    - Properties: `engine_name="indextts2"`, `supports_cloning=True`, `supports_emotional_cloning=True`, others `False`
- [ ] Register in [tts_adapter/engines/__init__.py](../tts_adapter/engines/__init__.py): `_ENGINES["indextts2"] = IndexTTS2Engine`

## Phase 3: API routes

- [ ] [tts_adapter/api/routes.py](../tts_adapter/api/routes.py)  -  extend `/tts/clone` Form params:
  - `emotion_audio: UploadFile | None = File(default=None)`
  - `emotion_text: str = Form(default="")`
  - `emotion_vector: str = Form(default="")` (comma-separated 8 floats; empty = unused)
  - `emotion_alpha: float = Form(default=1.0)`
- [ ] Reuse existing [`_collect_gen_kwargs`](../tts_adapter/api/routes.py#L228) helper for generation params (no duplication)
- [ ] **Upload size guard** (applies to both `reference_audio` and `emotion_audio`  -  DoS protection, runs before any bytes are buffered into RAM):
  ```python
  _MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB per file

  def _validate_upload_size(upload: UploadFile | None, field: str) -> None:
      if upload is None or upload.size is None:
          return
      if upload.size > _MAX_UPLOAD_BYTES:
          raise HTTPException(413, f"{field} exceeds {_MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
  ```
  Apply to both uploads at the top of `/tts/clone`. Duration-based validation (recommended `emotion_audio` about 2-10 s) can come later - size cap is the immediate DoS fix.
- [ ] **API-side validation (mandatory  -  do NOT silently ignore):**
  ```python
  has_emotion = any([
      emotion_audio is not None,
      bool(emotion_text),
      bool(emotion_vector),
  ])
  if has_emotion and not engine.supports_emotional_cloning:
      raise HTTPException(400, "Current engine does not support emotional cloning")

  modes = sum([emotion_audio is not None, bool(emotion_text), bool(emotion_vector)])
  if modes > 1:
      raise HTTPException(400, "Use only one emotion mode: emotion_audio, emotion_text, OR emotion_vector")

  if not 0.0 <= emotion_alpha <= 1.0:
      raise HTTPException(400, "emotion_alpha must be between 0.0 and 1.0")

  vec = None
  if emotion_vector:
      try:
          vec = [float(x) for x in emotion_vector.split(",")]
      except ValueError:
          raise HTTPException(400, "emotion_vector must be comma-separated floats")
      if len(vec) != 8:
          raise HTTPException(400, "emotion_vector must have exactly 8 floats: [happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]")
  ```
- [ ] Refactor `/models` to use `engine.available_models()`  -  remove the hardcoded `AVAILABLE_MODELS` list from [routes.py:72-105](../tts_adapter/api/routes.py), move per-variant list into qwen3 engine. Route becomes:
  ```python
  @app.get("/models")
  def list_models():
      engine = get_engine()
      return ModelsResponse(current=engine.model_id, available=engine.available_models())
  ```
  (qwen3 returns its 4-entry variant list; indextts2 returns its single-entry list). The existing `model_id` property covers "which is current"  -  no new `model_info()` accessor needed.
- [ ] `/health` returns new `supports_emotional_cloning` flag

## Phase 4: Install, isolation & Docker

- [ ] **Do NOT** add `indextts` to main [pyproject.toml](../pyproject.toml) deps  -  not on PyPI and likely to conflict with `qwen-tts`'s transformers pin (4.57.3).
- [ ] Recommended isolation options (pick one, document both in engine README):
  1. **Separate Docker image** (`Dockerfile.indextts2` + new `adapter-tts-indextts2` service in [compose.yml](../compose.yml)) with its own uv-locked environment. Reuses the existing HF-cache volume mount and `pull_policy: missing` offline pattern.
  2. **Parallel uv env** outside adapter  -  set `TTS_INDEXTTS2_REPO_DIR` so engine imports from there via `sys.path`
- [ ] If Phase 0 confirms no `qwen-tts` <-> `indextts` dep conflict, reconsider making it an optional extra: `[project.optional-dependencies] indextts2 = [...]`. Decide only after probe.
- [ ] Update [.env.example](../.env.example): add commented-out `TTS_INDEXTTS2_*` section. Default `TTS_INDEXTTS2_MODEL_DIR=~/.cache/tts-adapter/models/IndexTTS-2` matches the download script's destination.
- [ ] **Offline contract** (mirrors existing Qwen3 pattern):
  - Engine constructs `IndexTTS2(...)` with explicit local `cfg_path` + `model_dir`  -  no HF Hub calls
  - `HF_HUB_OFFLINE=1` (already a global env in `.env.example`) blocks any accidental network access
  - First-run download via `make download-indextts2`; all subsequent runs work fully offline
- [ ] [AGENTS.md](../AGENTS.md)  -  add `TTS_INDEXTTS2_*` rows to the env-vars table (lines 141-150)

## Phase 5: CLI

- [ ] `scripts/indextts2/tts_clone_emotion.py`  -  args: `--ref`, `--emotion-audio | --emotion-text | --emotion-vector`, `--alpha`, `--output`, `--bench`
- [ ] `scripts/indextts2/download_model.py`  -  thin wrapper around `hf download IndexTeam/IndexTTS-2 --local-dir ...` (mirror [scripts/qwen3/download_model.py](../scripts/qwen3/download_model.py)). Default cache: `~/.cache/tts-adapter/models/IndexTTS-2/`.
- [ ] `--bench` flag emits one-line JSON per run:
  ```
  {"engine":"indextts2","text_chars":42,"audio_seconds":2.8,"elapsed_seconds":4.1,"rtf":1.46,"cuda_max_memory_mb":7842}
  ```
- [ ] [Makefile](../Makefile)  -  add targets mirroring qwen3 conventions:
  - `make download-indextts2` -> runs `scripts/indextts2/download_model.py`
  - `make tts-clone-emotion text="..." ref=sample.wav emotion-text="..."` -> runs the emotion CLI
- [ ] [tests/](../tests/)  -  add `test_emotion_cloning.py`:
  - Integration tests using existing `httpx.Client` + `BASE_URL` pattern
  - Skip on `if not health.get("supports_emotional_cloning"): pytest.skip(...)` (mirrors existing `supports_design` skip pattern)
  - Unit tests for emotion-vector parsing + alpha bounds (no server needed)

## Phase 6: Docs

- [ ] `docs/engines/indextts2/README.md`:
  - Overview, capabilities table
  - Install: clone official repo + `uv sync` + `hf download` (the supported path)
  - Env vars (`TTS_INDEXTTS2_*`)
  - Emotion input modes: audio / text / 8-dim vector with order-fixed list `[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]`
  - Recommended `emotion_alpha` ranges per mode:
    - `emotion_audio`: 0.8 - 1.0
    - `emotion_text`: 0.4 - 0.7 (official docs recommend ~0.6 for more natural speech)
    - `emotion_vector`: 0.6 - 1.0
  - Caveats: **not guaranteed for Russian**, **not a real-time target**, **RTX 4070 12 GB must use FP16 first**
- [ ] Top-level [README.md](../README.md)  -  one-line engine-choice note:
  > `qwen3` = multilingual/Russian/general clone. `indextts2` = emotional clone.

## Phase 7: Verification

- [ ] Upstream smoke  -  covered by Phase 0
- [ ] Adapter-level isolation test (no API):
  ```bash
  TTS_ENGINE=indextts2 uv run python scripts/indextts2/tts_clone_emotion.py \
      "Hello world" --ref voice.wav --emotion-text "excited and happy" --alpha 0.6 --bench
  ```
- [ ] API smoke:
  ```bash
  curl -X POST http://localhost:9880/tts/clone \
    -F 'text=Hello' -F 'reference_audio=@voice.wav' \
    -F 'emotion_text=very excited' -F 'emotion_alpha=0.6' \
    --output out.wav
  ```
- [ ] API rejection tests:
  - emotion params sent while `TTS_ENGINE=qwen3` -> 400
  - multiple emotion modes in one request -> 400
  - `emotion_alpha=1.5` -> 400
  - `emotion_vector="1,2,3"` (wrong length) -> 400
  - oversized upload (>20 MB WAV as `reference_audio` or `emotion_audio`) -> 413
- [ ] Regression: `TTS_ENGINE=qwen3`  -  all existing CLI + API calls unchanged
- [ ] Offline load: `HF_HUB_OFFLINE=1` + local `TTS_INDEXTTS2_MODEL_DIR`
- [ ] RTX 4070 12 GB benchmark (the go/no-go gate):
  ```bash
  /usr/bin/time -v \
    env TTS_ENGINE=indextts2 TTS_INDEXTTS2_USE_FP16=true \
    uv run python scripts/indextts2/tts_clone_emotion.py \
      "Привет. Я очень рад тебя видеть." \
      --ref voice.wav --emotion-text "excited and warm" --alpha 0.6 --bench
  nvidia-smi
  ```
- [ ] **A/B subjective**  -  same reference voice, three emotions (happy / sad / angry). Success = each clip sounds like the cloned speaker AND audibly conveys the intended emotion. This is the original user complaint being resolved.

---

## Scope guardrails

- **Do not modify** existing Qwen3 engine behavior (additive only: `model_info()` + `supports_emotional_cloning=False` + internal refactor to use extracted helpers).
- **Do not add** Web UI changes  -  backend only.
- **Do not pin** `indextts` in main `pyproject.toml`  -  keep opt-in until Phase 0 confirms no conflicts.
- **Do not pass** `device` to `IndexTTS2` constructor  -  use `CUDA_VISIBLE_DEVICES` env.
- **Do not branch on `engine.engine_name`** in routes  -  engines own their metadata via `model_info()` / `available_models()`.
- **Do not duplicate** helpers already in the repo. See the reuse audit table above  -  `trim_silence`, tempfile handling, GPU-unload, and `_collect_gen_kwargs` must all be reused.
- **Do not split** the `TTSEngine` Protocol into sub-protocols. Capability flags (`supports_*`) already cover negotiation; splitting adds indirection without new value.
- **Do not add** a `BaseTTSEngine` abstract class. The Protocol contract + shared module-level helpers keep engines loosely coupled without inheritance.
