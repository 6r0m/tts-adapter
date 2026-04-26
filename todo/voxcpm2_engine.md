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

- [ ] `mkdir -p vendor && git clone https://github.com/OpenBMB/VoxCPM vendor/voxcpm`
- [ ] `cd vendor/voxcpm && uv venv .venv --python 3.10`
- [ ] `env -u VIRTUAL_ENV vendor/voxcpm/.venv/bin/pip install -e vendor/voxcpm` (env-unset pattern matches indextts2 worker - prevents adapter venv from leaking into vendor install)
- [ ] Pre-flight reuse audit (per CLAUDE.md "research existing host resources" rule):
  - [ ] `du -sh ~/.cache/huggingface/hub/models--openbmb--VoxCPM2/ 2>/dev/null` - reuse if cached
  - [ ] `du -sh ~/.cache/uv/wheels-v*/ | head` - confirm torch/transformers wheels already pulled
  - [ ] `ls ~/repos*/*/vendor/voxcpm 2>/dev/null` - sibling project may already have it
- [ ] `hf download openbmb/VoxCPM2 --local-dir vendor/voxcpm/checkpoints/VoxCPM2` (~10 GB)

### Proof script

- [ ] Write `vendor/voxcpm/phase0_proof.py` (lives in vendor only, never enters adapter):
  - **Verify constructor signature first** by inspecting `VoxCPM.from_pretrained`. The README example uses `from_pretrained("openbmb/VoxCPM2", load_denoiser=False)`; for offline the safe call is likely `from_pretrained(model_dir_or_path="vendor/voxcpm/checkpoints/VoxCPM2", load_denoiser=False)`. Do NOT assume `local_files_only` / `cache_dir` kwargs exist - inspect the signature, then pick the simplest working invocation.
  - Use `optimize=False` for proof (skip ~30s torch.compile warmup; we benchmark the inference path, not the compile path)
  - 4 emotion variants on the same Russian reference voice (neutral / angry / sad / calm)
  - 4 Russian texts (per design doc)
  - **Style-prompt language A/B (critical):** test each emotion BOTH ways, English style tag and Russian style tag, e.g.
    - EN style: `"(angry, sharp, irritated, high energy)Я очень зол. Это было несправедливо."`
    - RU style: `"(злой, резкий, раздражённый, высокая энергия)Я очень зол. Это было несправедливо."`
    - Decide which the adapter will use as the canonical style channel. Most likely outcome: English style tags work better (matches upstream's training); UI labels stay Russian and the adapter maps RU UI label -> EN style tag internally. Document the chosen mapping in the docs as part of Phase 2.
  - 3 repeats per (emotion x style-language) cell = 24 generations total
  - Generate: `m.generate(text=f"({style_tag}){text}", reference_wav_path="samples/voice_ru.wav")`
  - Log per generation: torch version, CUDA available, GPU name, peak VRAM (`torch.cuda.max_memory_allocated`), elapsed seconds, output audio seconds, RTF, style prompt used, seed if applicable

### Run

- [ ] `env -u VIRTUAL_ENV vendor/voxcpm/.venv/bin/python vendor/voxcpm/phase0_proof.py --ref samples/voice_ru.wav --out phase0_out --repeat 3`
- [ ] `nvidia-smi --query-gpu=memory.used,memory.total --format=csv` during run (sanity-check peak)

### Pass criteria (manual A/B, score 1-5)

- [ ] Russian intelligibility >= 4 on every clip
- [ ] Speaker similarity to reference >= 3.5 on every clip
- [ ] Emotion difference between styles >= 3.5 — **AND blind-listen distinguishability:** in a randomized blind playback, the 4 emotions (happy/sad/angry/calm) must be audibly distinguishable, not "same emotion every time with different timbre." Style-control models commonly preserve timbre but ignore emotion - this is the failure mode this gate exists to catch.
- [ ] Naturalness (no robotic / glitched output) >= 3.5
- [ ] Stability across 3 repeats - no cutoffs / loops / artifacts
- [ ] Style-tag language: at least ONE of {EN, RU} reliably produces the intended emotion. Pick the winner.

### Hardware gate

- [ ] VRAM peak < 11 GB on RTX 4070 12 GB (room for KV cache)
- [ ] RTF < 3.0x

### Decision

- [ ] Pass -> proceed to Phase 1.
- [ ] Fail -> pivot per "if Phase 0 fails" rule above. Do not attempt to fix.

---

## Phase 1 - architecture cleanups (anti-pattern fixes + auto-detection)

> Pure refactor. Existing Qwen3 + IndexTTS2 behavior must be byte-identical after this phase. Run full test suite + Russian smoke (qwen3) + 400-rejection smoke (indextts2) to confirm no regression before Phase 2.

### Anti-patterns to remove (do these FIRST)

- [ ] **Cyrillic guard hard-codes engine name** at [tts_adapter/api/routes.py:415](../tts_adapter/api/routes.py)
  - Add capability flag to engine Protocol (option A: `supports_cyrillic: bool`; option B: derive from `supported_languages` containing `"Russian"` - decide which generalizes cleaner during impl)
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

### Auto-detection of installed engines (new SOLID capability)

- [ ] Add classmethod `is_installed() -> bool` to [tts_adapter/engine.py](../tts_adapter/engine.py) `TTSEngine` Protocol
  - Qwen3: in-process import succeeds AND `TTS_QWEN3_MODEL_PATH` (or default cache) exists
  - IndexTTS2: `vendor/index-tts/.venv/bin/python` exists AND checkpoint dir exists
  - VoxCPM2: `vendor/voxcpm/.venv/bin/python` exists AND checkpoint dir exists
  - Cheap, synchronous - no HTTP calls (worker reachability is `loaded`, not `installed`)
- [ ] Add `GET /engines` endpoint in [tts_adapter/api/routes.py](../tts_adapter/api/routes.py):
  ```json
  {
    "engines": [
      {"name": "qwen3", "installed": true, "loaded": true, "supports_emotional_cloning": false, "supported_languages": [...]},
      {"name": "indextts2", "installed": true, "loaded": false, "supports_emotional_cloning": true, "supported_languages": [...]},
      {"name": "voxcpm2", "installed": false, "loaded": false, ...}
    ],
    "active": "qwen3"
  }
  ```
- [ ] Filter `/models` to installed engines only - UI dropdown can no longer offer an uninstalled engine
- [ ] Default engine selection at startup: if `TTS_ENGINE` unset, pick first installed in priority order `[qwen3, voxcpm2, indextts2]`. If `TTS_ENGINE` is set but not installed, fail fast with the exact `make install-<engine>` command.
- [ ] Web UI: pull `/engines`, populate engine dropdown from installed engines only (mirrors the Phase D language-dropdown SOT pattern). Reuse the existing 3 s `/health` poller - add `/engines` to the same poll cycle.

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

### Backend smoke (before moving to Phase 3)

- [ ] `make install-voxcpm2 && make build-voxcpm2 && make verify-voxcpm2-docker` passes
- [ ] `curl -X POST localhost:9882/load` then `curl -X POST localhost:9882/tts/clone -F text=... -F reference_audio=@... -F emotion_text=...` returns valid WAV
- [ ] `curl -X POST localhost:9882/tts/clone -F emotion_audio=@x.wav -F text=... -F reference_audio=@...` returns 400 (mode-rejection)

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
engine_name              = "voxcpm2"
supports_cloning         = True
emotion_modes            = {"text"}  # NEW: explicit set; bool supports_emotional_cloning derives from this
supports_design          = False     # scoping decision, not a model limitation - upstream supports text-only design
supports_custom_voice    = False
supports_batch           = False     # upstream has no batch API
supports_cyrillic        = True      # NEW capability flag (replaces hard-coded indextts2 check)
supported_languages      = [...]     # 30 langs from HF card; "Russian" included
```

---

## Phase 4 - verification

- [ ] **Engine listing:** `curl localhost:9880/engines` returns 3 engines, each with correct `installed`, `loaded`, capability flags
- [ ] **Worker health:** `make install-voxcpm2 && make build-voxcpm2 && make up && make verify-voxcpm2-docker` passes
- [ ] **Cross-engine switch with rollback:**
  ```bash
  curl -X POST localhost:9880/model/switch -d '{"model_id":"openbmb/VoxCPM2"}'
  curl -X POST localhost:9880/model/switch -d '{"model_id":"Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"}'
  ```
  Both 200; `/health` reflects active engine each time
- [ ] **The user's primary use case - Russian clone + emotion in one call:**
  ```bash
  curl -X POST localhost:9880/tts/clone \
    -F 'text=Привет, я очень рад тебя видеть' \
    -F 'language=Russian' \
    -F 'reference_audio=@samples/voice.wav' \
    -F 'emotion_text=радостно и тепло' \
    -F 'emotion_alpha=0.7' \
    --output cloned_happy_ru.wav
  ```
  Returns 200 + WAV that sounds like the cloned speaker AND audibly conveys the emotion. **This is the success criterion.**
- [ ] **Auto-detection regression:** `make clean-voxcpm2`, restart adapter; `/engines` reports `voxcpm2.installed=false`; UI dropdown drops the option; `TTS_ENGINE=voxcpm2` env fails fast with install instructions
- [ ] **License-gate negative tests (no regression):**
  - Russian on indextts2 still 400 (existing gate intact)
  - Russian on qwen3 still 200 (no regression)
  - Russian on voxcpm2 200 (new)
- [ ] **Subjective A/B (final):** same Russian reference voice, 3 emotions (happy / sad / angry) on voxcpm2. Each clip recognizable as the cloned speaker AND audibly different emotion. Beats IndexTTS2 on Russian (it has to - IndexTTS2 can't do Russian at all).

---

## Scope guardrails

- **Do not modify** existing Qwen3 or IndexTTS2 engine behavior beyond adding `is_installed()` and the capability flag(s) needed by Phase 1 cleanups.
- **Do not pin** `voxcpm` in main `pyproject.toml` - heavy dep stack (gradio 6, modelscope, funasr) will conflict.
- **Do not bake** the vendor venv into `Dockerfile.voxcpm2` - bind-mount, mirrors IndexTTS2 thin-image pattern (~3 GB vs ~12 GB).
- **Do not branch** on `engine.engine_name` anywhere new. After Phase 1 there should be ZERO such branches in `routes.py`.
- **Do not duplicate** the audio / GPU helpers - reuse [tts_adapter/audio_utils.py](../tts_adapter/audio_utils.py) and [tts_adapter/gpu_utils.py](../tts_adapter/gpu_utils.py).
- **Do not promise** Russian quality matches Fish S2. Document upstream CV3-eval WER 5.21 honestly - mid-tier Russian, but real and combined with clone+emotion which qwen3 cannot do.
- **Do not skip Phase 0.** This is the gate that should have caught IndexTTS2's Russian gap. Not repeating that.
