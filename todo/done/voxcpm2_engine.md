# Add VoxCPM2 Engine - Russian Emotional Voice Cloning

> **When complete:** move this file to `todo/done/` (do not delete).
> **Design doc:** approved plan at `~/.claude/plans/search-web-carefully-is-merry-aurora.md`
> **Why:** neither current engine delivers Russian + clone + emotion in one call. Qwen3 = Russian but no clone+emotion. IndexTTS2 = clone+emotion but CN/EN/JP only. VoxCPM2 (OpenBMB, Apr 2026, Apache-2.0, ~8 GB VRAM bf16) closes the gap.

**Engine role split after this lands (only if Phase 0 passes):**
- `qwen3` -> Russian / multilingual / general clone (boot default - unchanged)
- `indextts2` -> EN/CN/JP emotional clone (rich emotion modes: audio + text + 8-vec)
- `voxcpm2` -> **recommended** engine for Russian emotional cloning (text-tag emotion only, 30 langs incl. ru). Qwen3 stays the boot default; users opt into VoxCPM2 by installing + selecting it. We do not flip the default until VoxCPM2 has earned it on real Russian voiceovers in production.

---

## Execution order (strict)

1. **Phase 0** - bare-upstream Russian proof on RTX 4070 12 GB (mandatory go/no-go gate; zero adapter / infra work)
2. **Phase 1** - architecture cleanups: kill 3 hard-coded engine-name branches + `emotion_modes` capability + `is_installed()` + `/engines` endpoint
3. **Phase 2** - VoxCPM2 worker backend (engine class, serve.py, Docker, compose, Makefile, .env)
4. **Phase 3** - UI + docs (engine/model labels, emotion controls filtered by `emotion_modes`, READMEs, language tables)
5. **Phase 4** - verification

If Phase 0 fails: stop, document the failure mode in this file, replace `voxcpm2` references with `chatterbox` (Resemble AI Chatterbox Multilingual, MIT, runner-up per design doc), restart Phase 0. Do not "fix" a failing model - pivot.

---

## Phase 0 - upstream Russian proof (the only gate)

**Goal:** verify VoxCPM2 produces intelligible Russian, preserves cloned timbre, applies emotion via text tag, and runs on 4070 12 GB without OOM. **Bare upstream only - zero adapter changes, zero infrastructure work.** Architecture cleanup (`is_installed()`, `/engines`, capability flags) is Phase 1 - do not start it until proof passes.

### Setup (bare upstream)

All commands run from **adapter repo root** (cwd-stable; no `cd` chains):

- [ ] `mkdir -p vendor && git clone https://github.com/OpenBMB/VoxCPM vendor/voxcpm`
- [ ] `(cd vendor/voxcpm && uv venv .venv --python 3.10)` - subshell; cwd returns to repo root
- [ ] `env -u VIRTUAL_ENV vendor/voxcpm/.venv/bin/python -m pip install -e vendor/voxcpm` (env-unset pattern matches indextts2 worker - prevents adapter venv from leaking into vendor install)
- [ ] Pre-flight reuse audit (per CLAUDE.md "research existing host resources" rule):
  - [ ] `du -sh ~/.cache/huggingface/hub/models--openbmb--VoxCPM2/ 2>/dev/null` - reuse if cached
  - [ ] `du -sh ~/.cache/uv/wheels-v*/ | head` - confirm torch/transformers wheels already pulled
  - [ ] `ls ~/repos*/*/vendor/voxcpm 2>/dev/null` - sibling project may already have it
- [ ] `hf download openbmb/VoxCPM2 --local-dir vendor/voxcpm/checkpoints/VoxCPM2` (~10 GB)

### Proof script

- [ ] Write `vendor/voxcpm/phase0_proof.py` (lives in vendor only, never enters adapter):
  - **Verify constructor signature first** by inspecting `VoxCPM.from_pretrained`. The README example uses `from_pretrained("openbmb/VoxCPM2", load_denoiser=False)`; for offline the safe call is likely `from_pretrained(model_dir_or_path="vendor/voxcpm/checkpoints/VoxCPM2", load_denoiser=False)`. Do NOT assume `local_files_only` / `cache_dir` kwargs exist - inspect the signature, then pick the simplest working invocation.
  - Use `optimize=False` for proof (skip ~30s torch.compile warmup; we benchmark the inference path, not the compile path)
  - **Emotion matrix: 5 emotions** (neutral / happy / angry / sad / calm). `happy` and `neutral` MUST both be present - "happy" is core to the user use case, "neutral" is the baseline against which emotion is measured. (Earlier 4-emotion list dropped happy by mistake.)
  - **Style-prompt language A/B (critical):** test each emotion BOTH ways, English style tag and Russian style tag, e.g.
    - EN style: `"(angry, sharp, irritated, high energy)Я очень зол. Это было несправедливо."`
    - RU style: `"(злой, резкий, раздражённый, высокая энергия)Я очень зол. Это было несправедливо."`
  - **Matrix size:** 5 emotions x 2 style-languages x 3 repeats = **30 generations total**.
  - Generate: `m.generate(text=f"({style_tag}){text}", reference_wav_path="samples/voice_ru.wav")`
  - Log per generation: torch version, CUDA available, GPU name, peak VRAM (`torch.cuda.max_memory_allocated`), elapsed seconds, output audio seconds, RTF, style prompt used, style language (EN/RU), seed if applicable
  - **Phase 0 outputs (must be recorded in this todo file before Phase 1 starts):**
    - `canonical_style_language` = `"EN"` or `"RU"` - whichever produces more reliable emotion control across the 5 emotions
    - `style_mapping` = the EN tag string for each emotion class (used by adapter to map RU UI labels -> EN style tags). Example: `{"happy": "cheerful, warm, smiling tone", "sad": "sad, tired, restrained tone", "angry": "angry, sharp, irritated tone", "calm": "calm, warm, reassuring tone", "neutral": "natural, neutral tone"}`
    - `cfg_value` / `inference_timesteps` defaults that worked best (these are upstream `generate()` knobs - upstream's "may need 1-3 retries" hint suggests tuning them is part of integration, not a magic knob)
    - Whether `emotion_alpha` (in our adapter API) maps to anything real on VoxCPM2. **Default assumption: NO mapping exists** - VoxCPM2 has no `emo_alpha` equivalent, only `cfg_value` for sampling guidance. If Phase 0 finds a sensible `emotion_alpha` in [0.0, 1.0] -> `cfg_value` in [1.2, 3.0] mapping that audibly varies emotion intensity, document it. Otherwise the adapter rejects non-default `emotion_alpha` for VoxCPM2 (see Blocker 2 in Phase 1).

### Run

- [ ] `env -u VIRTUAL_ENV vendor/voxcpm/.venv/bin/python vendor/voxcpm/phase0_proof.py --ref tmp/input/test_clone.wav --out tmp/output/proof_matrix --repeat 3`
- [ ] `nvidia-smi --query-gpu=memory.used,memory.total --format=csv` during run (sanity-check peak)

### User acceptance deliverable (mandatory output of Phase 0)

The proof matrix is for benchmarking; the **user-acceptance deliverable** is a fixed set of 3 audio files at known paths that the user listens to manually before approving Phase 0. These are non-optional.

- **Reference voice (input):** `tmp/input/test_clone.wav` (already present)
- **Output directory:** `tmp/output/` - create with `mkdir -p tmp/output`
- **Generate exactly 3 files**, one per emotion, using the same Russian text in each (suggested: `"Привет, я очень рад тебя видеть."` - emotion comes from style tag, not text content):

| Output file | Style tag (English; map to RU later if Phase 0 picks RU as canonical) | Russian text |
|---|---|---|
| `tmp/output/test_clone_very_afraid.wav` | `(very afraid)` | "Привет, я очень рад тебя видеть." |
| `tmp/output/test_clone_very_happy.wav` | `(very happy)` | "Привет, я очень рад тебя видеть." |
| `tmp/output/test_clone_very_angry.wav` | `(very angry)` | "Привет, я очень рад тебя видеть." |

- [ ] `mkdir -p tmp/output`
- [ ] Generate all 3 files via the proof script (or a separate one-shot call). Each file MUST exist at the exact path above.
- [ ] Manual listen check: in all 3 files, the speaker MUST sound like `tmp/input/test_clone.wav` AND the emotion MUST be audibly distinct between files. If "afraid" and "happy" sound the same -> Phase 0 fail.
- [ ] **`tmp/` is gitignored** (host-only WSL path, never enters git history). Do not commit these files; they are for manual review only.

### Pass criteria (manual A/B, score 1-5)

Per-condition rule (each `(emotion, style-language)` cell): **at least 2 of 3 repeats must pass** all four metrics. Allows for upstream's documented stochastic variation ("generate 1-3 times for best result") without rejecting a usable model on a single bad sample.

| Metric | Threshold (per passing repeat) |
|---|---|
| Russian intelligibility | >= 4/5 |
| Speaker similarity to reference | >= 3.5/5 |
| Emotion match (does it convey the requested emotion?) | >= 3.5/5 |
| Naturalness (no robotic / glitched output) | >= 3.5/5 |

**Style-tag language:** at least one of {EN, RU} must hit the per-condition rule across all 5 emotions. The winner becomes `canonical_style_language`.

### Hard fail (any one of these = STOP)

- [ ] OOM on RTX 4070 12 GB
- [ ] VRAM peak >= 11 GB
- [ ] RTF >= 3.0x for short clips (<= 5 s output)
- [ ] Repeated cutoffs / loops / artifacts in 2/3 repeats of any condition
- [ ] Any emotion class indistinguishable from neutral across all 3 repeats in blind listening (style-control models often preserve timbre but ignore emotion - this is the failure mode this gate exists to catch)
- [ ] Speaker identity collapses (reference voice unrecognizable) in 2/3 repeats of any condition
- [ ] Russian text sounds foreign/garbled across repeats (the IndexTTS2 failure mode)

### Decision

- [ ] Pass -> record `canonical_style_language` + `style_mapping` + `emotion_alpha` mapping decision in this file, then proceed to Phase 1.
- [ ] Fail -> pivot per "if Phase 0 fails" rule above. Do not attempt to fix.

---

## Phase 1 - architecture cleanups (anti-pattern fixes + auto-detection)

> Pure refactor. Existing Qwen3 + IndexTTS2 behavior must be byte-identical after this phase. Run full test suite + Russian smoke (qwen3) + 400-rejection smoke (indextts2) to confirm no regression before Phase 2.

### Anti-patterns to remove (do these FIRST)

- [ ] **Cyrillic guard hard-codes engine name** at [tts_adapter/api/routes.py:415](../tts_adapter/api/routes.py)
  - Add capability flag `supports_cyrillic_text: bool` to engine Protocol (Cyrillic includes Ukrainian/Belarusian/Bulgarian/Serbian etc. - do NOT derive from `"Russian" in supported_languages`)
  - Route checks the flag, not `engine.engine_name == "indextts2"`
  - Qwen3: True. IndexTTS2: False. VoxCPM2: True.
- [ ] **Legacy env-var path check hard-codes both engines** at [tts_adapter/api/routes.py:56-58](../tts_adapter/api/routes.py)
  - Build the check dynamically from `_ENGINES.keys()` at startup
- [ ] **Emotion-clone error message hard-codes "switch to indextts2"** at [tts_adapter/api/routes.py:467](../tts_adapter/api/routes.py)
  - Iterate `_ENGINES` for first installed engine with `supports_emotional_cloning=True` matching the requested language; suggest dynamically
- [ ] **Replace bool `supports_emotional_cloning` with explicit `emotion_modes: set[str]` capability**
  - IndexTTS2: `{"audio", "text", "vector"}` (3 modes)
  - VoxCPM2: `{"text"}` only (no audio mode, no vector mode upstream)
  - Qwen3: `set()` (none)
  - Keep `supports_emotional_cloning` as a derived `bool(emotion_modes)` for backwards compatibility, but route validation must reject per-mode: e.g. `emotion_audio` on VoxCPM2 -> 400 with hint, `emotion_vector` on VoxCPM2 -> 400 with hint, `emotion_text` on VoxCPM2 -> accepted. UI must hide the audio + vector inputs when active engine's `emotion_modes` doesn't include them - same SOT pattern as the language dropdown.
- [ ] **Add `supports_emotion_strength: bool` capability** for the `emotion_alpha` parameter
  - IndexTTS2: True (upstream `emo_alpha` is real)
  - VoxCPM2: **False** until Phase 0 proves an `emotion_alpha [0.0, 1.0] -> cfg_value [1.2, 3.0]` mapping that audibly varies emotion intensity. If Phase 0 confirms a mapping, flip to True and document the curve.
  - Qwen3: False (no emotion clone path at all)
  - Route behavior on `/tts/clone`: if `emotion_alpha != default(=1.0)` AND `not engine.supports_emotion_strength` -> 400 with hint "engine X does not expose emotion intensity control; omit emotion_alpha or use IndexTTS2"
  - This prevents silent acceptance of a parameter the engine doesn't actually use - the IndexTTS2 silent-Russian-mangle failure mode applied to a different parameter.

### Auto-detection of installed engines (new SOLID capability)

**Three distinct states, do NOT conflate:**

- `installed` = files on disk: vendor venv exists AND checkpoint dir exists. Synchronous, cheap (filesystem stat only). No imports, no GPU, no HTTP.
- `reachable` = for remote workers, `worker /health` responds within ~500 ms. For in-process engines (qwen3), always equals `installed`.
- `loaded` = engine has `model` initialized in memory (warmup completed). For remote workers, derived from `worker /health.model_loaded`.

The split matters: a worker can be installed (files present) but not reachable (Docker service not started); reachable but not loaded (warmup pending). The API behavior differs in each case.

- [ ] Add classmethod `is_installed() -> bool` to [tts_adapter/engine.py](../tts_adapter/engine.py) `TTSEngine` Protocol
  - **MUST be a `@classmethod`, no `self` state required, no model load, no GPU touch, no HTTP call.** Filesystem stat only.
  - Qwen3: package importable AND `TTS_QWEN3_MODEL_PATH` (or default HF cache dir for the configured model id) exists
  - IndexTTS2: `vendor/index-tts/.venv/bin/python` exists AND `TTS_INDEXTTS2_MODEL_DIR` exists
  - VoxCPM2: `vendor/voxcpm/.venv/bin/python` exists AND `TTS_VOXCPM2_MODEL_DIR` exists
- [ ] Add instance method `is_reachable() -> bool` (default impl returns `is_installed()`; remote engines override with `worker /health` ping with short timeout)
- [ ] Add instance property `is_loaded: bool` (already implicitly tracked; surface it explicitly)
- [ ] Add `GET /engines` endpoint in [tts_adapter/api/routes.py](../tts_adapter/api/routes.py):
  ```json
  {
    "engines": [
      {"name": "qwen3", "installed": true, "reachable": true, "loaded": true, "emotion_modes": [], "supports_cyrillic_text": true, "supported_languages": [...]},
      {"name": "indextts2", "installed": true, "reachable": false, "loaded": false, "emotion_modes": ["audio","text","vector"], "supports_cyrillic_text": false, ...},
      {"name": "voxcpm2", "installed": false, "reachable": false, "loaded": false, ...}
    ],
    "active": "qwen3"
  }
  ```
- [ ] **Preserve the existing `catalog_models()` vs `available_models()` split** - this is good infra, do NOT regress it
  - `catalog_models()` (existing) -> known models for routing `/model/switch` validation. Includes models from installed-but-not-reachable workers.
  - `available_models()` (existing) -> models switchable RIGHT NOW (installed AND reachable). Drives `/models` and the UI dropdown.
- [ ] **`/models` returns currently-switchable models** (installed + reachable). This matches existing behavior - just confirm it still works after the auto-detection refactor. Do NOT regress to "installed-only".
- [ ] **`/model/switch` validation:**
  - Target model must exist in `catalog_models()` -> else 404
  - Target engine must be `installed` -> else 400 with install command
  - Target engine must be `reachable` -> else 503 with hint to start the worker (`make run-<engine>` or `docker compose --profile <engine> up -d`)
- [ ] **Boot rule (KISS, defer auto-pick):**
  - `TTS_ENGINE` defaults to `qwen3` (already in `.env.example`) - keep it. Pydantic settings parsing means "unset" rarely observable anyway.
  - If `TTS_ENGINE` is explicitly set to an uninstalled engine, fail fast at startup with the exact `make install-<engine>` command. No auto-fallback to a different engine.
  - Auto-pick "first installed in priority order" is a future enhancement, NOT in scope for this todo.
- [ ] Web UI: pull `/engines`, populate engine dropdown from `installed AND reachable` engines (the switchable subset). Reuse the existing 3 s `/health` poller - add `/engines` to the same poll cycle.

### Tests for Phase 1

- [ ] Unit: `engine.is_installed()` returns False when vendor venv missing
- [ ] Unit: `_validate_language` route-level helper uses capability flag, not engine name
- [ ] API: `GET /engines` shape stable across qwen3-only / qwen3+indextts2 setups
- [ ] Regression: existing 53+ tests still green (especially Russian on qwen3 + 400-on-indextts2)

---

## Phase 2 - VoxCPM2 worker backend (no UI / docs yet)

> Only after Phase 0 passes AND Phase 1 ships green. Each file has a 1:1 IndexTTS2 template - copy, rename, adapt deltas listed below. UI + docs are Phase 3.

### Files to create / edit

- [ ] **`tts_adapter/engines/voxcpm2.py`** (CREATE) - copy [tts_adapter/engines/indextts2.py](../tts_adapter/engines/indextts2.py); rename to `VoxCPM2RemoteEngine`; settings prefix `TTS_VOXCPM2_`; default port 9882; `supported_languages` = the HF card 30-language list (use ISO names matching qwen3 spelling where overlapping); `emotion_modes={"text"}`
- [ ] **`tts_adapter/engines/__init__.py`** (EDIT, 1 line) - register `"voxcpm2": VoxCPM2RemoteEngine`
- [ ] **`scripts/voxcpm2/serve.py`** (CREATE) - copy [scripts/indextts2/serve.py](../scripts/indextts2/serve.py); swap inference for VoxCPM2 (see deltas below). Reject `emotion_audio` / `emotion_vector` with 400 (worker-side defense in depth, mirrors API-side rejection).
- [ ] **`scripts/voxcpm2/download_model.py`** (CREATE) - copy [scripts/indextts2/download_model.py](../scripts/indextts2/download_model.py); `hf download openbmb/VoxCPM2 --local-dir models/voxcpm2/VoxCPM2`
- [ ] **`Dockerfile.voxcpm2`** (CREATE) - copy [Dockerfile.indextts2](../Dockerfile.indextts2); bind-mount `vendor/voxcpm/.venv`; same Ubuntu 22.04 / Python 3.10 base
- [ ] **`compose.yml`** (EDIT) - add `adapter-tts-voxcpm2` service mirroring `adapter-tts-indextts2`; `profiles: ["voxcpm2"]`; expose 9882; bind-mount `./vendor/voxcpm:/work/vendor/voxcpm:ro`
- [ ] **`Makefile`** (EDIT) - add targets: `install-voxcpm2`, `download-voxcpm2`, `run-voxcpm2`, `clean-voxcpm2`, `build-voxcpm2`, `verify-voxcpm2-docker`. Ensure `make down` and `make up` cover all 3 profiles.
- [ ] **`.env.example`** (EDIT) - commented `TTS_VOXCPM2_*` block: `MODEL_DIR`, `URL=http://localhost:9882`, `TIMEOUT=180`, `PORT=9882`, `OPTIMIZE=true`, `LOAD_DENOISER=false`

### VoxCPM2-specific deltas vs IndexTTS2 template (read before copying)

These come from upstream source review and are NOT in the IndexTTS2 template:

1. **Emotion is an inline `(...)` text prefix, NOT a kwarg.** Worker prepends: `text = f"({style_tag}){text}"`. The `style_tag` language (EN vs RU) is decided in Phase 0; worker maps incoming `emotion_text` (UI-language) to the chosen channel.
2. **`emotion_modes = {"text"}` only.** Upstream has NO `emotion_audio` mode and NO `emotion_vector` mode. Worker rejects those at `/tts/clone` with 400 (mirrors Phase 1's per-mode validation). Do NOT silently drop them.
3. **Reference audio is a path string only**, not bytes/array. Worker MUST `bytes_to_tempfile()` the upload. Helper already exists at [tts_adapter/audio_utils.py](../tts_adapter/audio_utils.py).
4. **48 kHz output sample rate.** Verify [tts_adapter/audio_utils.py](../tts_adapter/audio_utils.py) and the WAV write path don't hardcode 22050/24000 anywhere.
5. **`load_denoiser=False`** in worker constructor. Otherwise first `/load` triggers a surprise ModelScope download of `iic/speech_zipenhancer_ans_multiloss_16k_base`.
6. **`optimize=True` (default) runs `torch.compile` at constructor** - adds ~30s to first `/load`. Acceptable for production. Document in engine README.
7. **Offline contract: use `from_pretrained(model_dir_or_path=<local_path>, load_denoiser=False)`** with the local checkpoint dir resolved from `TTS_VOXCPM2_MODEL_DIR`. Do NOT assume `local_files_only` / `cache_dir` kwargs exist - Phase 0 will have verified the actual constructor signature; copy what the proof script used. The HF `from_pretrained("openbmb/VoxCPM2", ...)` path also works but pulls from cache and is less explicit; prefer the local-dir form for the offline guarantee.
8. **bf16 only.** No fp16/int8 toggle. Settings should not expose a dtype field.
9. **Heavy deps conflict with main adapter** (gradio 6, modelscope, funasr, datasets <4) - confirms isolated worker is correct. Do NOT attempt in-process integration.
10. **Voice design IS supported upstream** (text-only, no reference audio). Out of scope for this todo - we ship `/tts/clone` first. Add a TODO comment in the engine class noting `supports_design=False` is a temporary scoping decision, not a model limitation; revisit after clone+emotion is proven in production.

### Capability flags VoxCPM2 sets

```
engine_name                = "voxcpm2"
supports_cloning           = True
emotion_modes              = {"text"}   # NEW: explicit set; bool supports_emotional_cloning derives from this
supports_emotion_strength  = False      # flip to True ONLY if Phase 0 proved an alpha->cfg_value mapping
supports_design            = False      # scoping decision, not a model limitation - upstream supports text-only design
supports_custom_voice      = False
supports_batch             = False      # upstream has no batch API
supports_cyrillic_text     = True       # NEW capability flag (replaces hard-coded indextts2 check)
supported_languages        = [...]      # 30 langs from HF card; "Russian" included
```

### Backend smoke (before moving to Phase 3)

- [ ] `make install-voxcpm2 && make build-voxcpm2 && make verify-voxcpm2-docker` passes
- [ ] `curl -X POST localhost:9882/load` then `curl -X POST localhost:9882/tts/clone -F text=... -F reference_audio=@... -F emotion_text=...` returns valid WAV
- [ ] `curl -X POST localhost:9882/tts/clone -F emotion_audio=@x.wav -F text=... -F reference_audio=@...` returns 400 (mode-rejection)

---

## Phase 3 - UI + docs

- [ ] **`docs/engines/voxcpm2/README.md`** (CREATE) - mirror [docs/engines/indextts2/README.md](../docs/engines/indextts2/README.md): top-line supported-languages banner ("Russian + 29 other languages, Apache-2.0"), install steps, env-vars table, emotion-tag examples (in the Phase-0-chosen style language), Russian benchmark note (CV3-eval WER 5.21), 48 kHz output caveat, `optimize=True` cold-start warning, `load_denoiser=False` ModelScope note, RU-UI -> EN-style-tag mapping (if Phase 0 chose EN as canonical)
- [ ] **`README.md`** (EDIT) - add VoxCPM2 row to top-level Engines table (Languages column: "30 incl. Russian"; Emotion column: "text-tag only"; License column: "Apache-2.0")
- [ ] **`docs/engines/indextts2/README.md`** (EDIT) - add cross-link "For Russian emotional cloning, use [VoxCPM2](../voxcpm2/README.md) instead - this engine cannot."
- [ ] **`docs/engines/qwen3/README.md`** (EDIT) - add cross-link "For Russian + emotion in one call, use [VoxCPM2](../voxcpm2/README.md). This engine cannot combine clone + emotion (see CustomVoice/Base/VoiceDesign limitation)."
- [ ] **Web UI engine + emotion-mode SOT-driven dropdowns** (EDIT [tts_adapter/web/templates_*.py](../tts_adapter/web/templates_body.py))
  - Engine dropdown auto-populates from `/engines` (already SOT-driven after Phase 1's auto-detection refactor; verify on engine switch)
  - Emotion-mode controls (audio upload / text input / vector input) hide/show based on active engine's `emotion_modes` capability. Same pattern as Phase D `supports_emotional_cloning` toggle, but per-mode now. VoxCPM2 active -> only emotion_text textarea visible.
  - Hint banner if user picks an emotion mode not supported by active engine: "VoxCPM2 supports text-only emotion; switch to IndexTTS2 for audio/vector modes (English/Chinese/Japanese only)."
- [ ] **`tts_adapter/web/templates_i18n.py`** (EDIT) - add EN+RU strings for the new emotion-mode hint
- [ ] **`AGENTS.md`** (EDIT) - add `TTS_VOXCPM2_*` rows to the env-vars table

---

## Phase 4 - verification

- [ ] **Engine listing:** `curl localhost:9880/engines` returns 3 engines, each with correct `installed` / `reachable` / `loaded` / capability flags
- [ ] **Worker health:** `make install-voxcpm2 && make build-voxcpm2 && make up && make verify-voxcpm2-docker` passes
- [ ] **Cross-engine switch with rollback:**
  ```bash
  curl -X POST localhost:9880/model/switch -d '{"model_id":"openbmb/VoxCPM2"}'
  curl -X POST localhost:9880/model/switch -d '{"model_id":"Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"}'
  ```
  Both 200; `/health` reflects active engine each time
- [ ] **Switch validation:** `/model/switch` to a model whose worker is installed-but-not-reachable -> 503 with `make run-<engine>` hint (NOT a silent failure or a 200)
- [ ] **The user's primary use case - Russian clone + emotion in one call:**
  ```bash
  # NOTE: emotion_alpha omitted unless Phase 0 proved a mapping. UI sends RU label;
  # adapter maps to canonical_style_language tag internally.
  curl -X POST localhost:9880/tts/clone \
    -F 'text=Привет, я очень рад тебя видеть' \
    -F 'language=Russian' \
    -F 'reference_audio=@samples/voice.wav' \
    -F 'emotion_text=happy' \
    --output cloned_happy_ru.wav
  ```
  Returns 200 + WAV that sounds like the cloned speaker AND audibly conveys the emotion. **This is the success criterion.**
- [ ] **`emotion_alpha` rejection (when `supports_emotion_strength=False`):**
  ```bash
  curl -i -X POST localhost:9880/tts/clone \
    -F 'text=...' -F 'reference_audio=@voice.wav' \
    -F 'emotion_text=happy' -F 'emotion_alpha=0.7'
  ```
  Returns **400** with hint that VoxCPM2 does not expose emotion intensity. (Skip this test if Phase 0 promoted `supports_emotion_strength=True`.)
- [ ] **Per-mode rejection:**
  - `emotion_audio=@x.wav` on voxcpm2 -> 400 (mode not supported)
  - `emotion_vector=0,0,0.8,0,0,0,0,0` on voxcpm2 -> 400 (mode not supported)
- [ ] **Auto-detection regression:** `make clean-voxcpm2`, restart adapter; `/engines` reports `voxcpm2.installed=false`; UI dropdown drops the option; `TTS_ENGINE=voxcpm2` env fails fast at startup with install instructions
- [ ] **License-gate negative tests (no regression):**
  - Russian on indextts2 still 400 (existing gate intact)
  - Russian on qwen3 still 200 (no regression)
  - Russian on voxcpm2 200 (new)
- [ ] **Subjective A/B (final):** same Russian reference voice, 5 emotions (neutral / happy / sad / angry / calm) on voxcpm2. Each clip recognizable as the cloned speaker AND audibly different emotion. Beats IndexTTS2 on Russian (it has to - IndexTTS2 can't do Russian at all).

---

## Scope guardrails

- **Do not modify** existing Qwen3 or IndexTTS2 engine behavior beyond adding `is_installed()` and the capability flag(s) needed by Phase 1 cleanups.
- **Do not pin** `voxcpm` in main `pyproject.toml` - heavy dep stack (gradio 6, modelscope, funasr) will conflict.
- **Do not bake** the vendor venv into `Dockerfile.voxcpm2` - bind-mount, mirrors IndexTTS2 thin-image pattern (~3 GB vs ~12 GB).
- **Do not branch** on `engine.engine_name` anywhere new. After Phase 1 there should be ZERO such branches in `routes.py`.
- **Do not duplicate** the audio / GPU helpers - reuse [tts_adapter/audio_utils.py](../tts_adapter/audio_utils.py) and [tts_adapter/gpu_utils.py](../tts_adapter/gpu_utils.py).
- **Do not promise** Russian quality matches Fish S2. Document upstream CV3-eval WER 5.21 honestly - mid-tier Russian, but real and combined with clone+emotion which qwen3 cannot do.
- **Do not skip Phase 0.** This is the gate that should have caught IndexTTS2's Russian gap. Not repeating that.
