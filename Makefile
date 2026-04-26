.PHONY: help install install-qwen3 install-indextts2 install-indextts clean-indextts2 download-model download-indextts2 run-indextts2 serve server tts tts-clone tts-clone-emotion tts-design test build build-indextts2 build-all verify-indextts2-docker rebuild up down logs health shell clean indextts2 all

# Detect docker compose command (v2 with space vs v1 with hyphen)
DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Default target
help:
	@echo "TTS Adapter"
	@echo "==========="
	@echo ""
	@echo "Local (no Docker):"
	@echo "  make install         - Install Python deps (uv sync)"
	@echo "  make install-qwen3   - Full Qwen3 install (deps + checkpoints, prints .env hint)"
	@echo "  make download-model  - Download Qwen3 weights only (skip uv sync)"
	@echo "  make serve           - Run server locally (Ctrl+C to stop)"
	@echo "  make server stop     - Kill local server"
	@echo "  make tts text=\"...\" [instruct=\"...\"] - Generate speech"
	@echo "  make tts-clone text=\"...\" ref=sample.wav - Clone voice (Base model)"
	@echo "  make tts-clone-emotion text=\"...\" ref=sample.wav emotion-text=\"angry\" [alpha=0.7] - Clone+emotion (IndexTTS2)"
	@echo "  make tts-design text=\"...\" instruct=\"...\" - Design voice (VoiceDesign model)"
	@echo ""
	@echo "IndexTTS2 (separate worker process - one-time install):"
	@echo "  make install-indextts2  - Snapshot upstream + isolated venv + worker deps + checkpoints (~6 GB)"
	@echo "  make run-indextts2      - Start IndexTTS2 worker on :9881"
	@echo "  make clean-indextts2    - Wipe vendor/index-tts/ (use before bumping INDEXTTS_REF)"
	@echo "  make download-indextts2 - Re-download just the checkpoints (skip clone/venv)"
	@echo ""
	@echo "  make test            - Test single TTS generation"
	@echo "  make test batch      - Test batch TTS generation"
	@echo ""
	@echo "Docker (auto-detects engines installed in models/):"
	@echo "  make build           - Build images for installed engines (Qwen3 + IndexTTS2 if present)"
	@echo "  make build-indextts2 - Build only the IndexTTS2 worker image"
	@echo "  make build-all       - Build both images regardless of install state"
	@echo "  make verify-indextts2-docker - Quick container import smoke test (catches ABI/.pth issues)"
	@echo "  make rebuild         - Force rebuild with no cache"
	@echo "  make up              - Start everything that's installed (auto-adds --profile indextts2)"
	@echo "  make down            - Stop containers"
	@echo "  make logs [indextts2|all] - View main adapter logs (default), worker logs, or both"
	@echo "  make health          - Health-check all running services (main + worker if up)"
	@echo "  make shell           - Shell into main adapter container"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Remove output files"

# Install dependencies
install:
	uv sync
	@echo ""
	@echo "Done! Now run: source .venv/bin/activate"

# Download model for offline use (Qwen3)
download-model:
	uv run python scripts/qwen3/download_model.py

# Full Qwen3 install: deps + checkpoints. Symmetric to install-indextts2.
# Prints the .env lines to paste at the end.
install-qwen3: install
	uv run python scripts/qwen3/download_model.py
	@echo ""
	@echo "============================================================"
	@echo "Qwen3 install complete. Add to .env:"
	@echo "  TTS_ENGINE=qwen3"
	@echo "  TTS_QWEN3_MODEL_PATH=./models/qwen3/Qwen3-TTS-12Hz-1.7B-CustomVoice"
	@echo "  HF_HUB_OFFLINE=1"
	@echo ""
	@echo "Then: make serve   (or 'make up' for Docker)"
	@echo "============================================================"

# Download IndexTTS-2 checkpoints only (use this to refresh weights without
# re-cloning vendor/index-tts or reinstalling the worker venv).
download-indextts2:
	uv run python scripts/indextts2/download_model.py

# Full IndexTTS2 install: clone upstream, set up isolated venv, install worker
# deps, download checkpoints, prewarm w2v-bert. Idempotent - safe to re-run.
# Why two processes: see docs/engines/indextts2/README.md.
#
# Pin a specific upstream ref for reproducible installs:
#   make install-indextts2 INDEXTTS_REF=v0.1.0
# Defaults to `main` for exploration; pin before relying on it.
INDEXTTS_REF ?= main

install-indextts2:
	@echo "==> [1/5] vendor/index-tts (snapshot at ref=$(INDEXTTS_REF))..."
	@# We vendor upstream as CODE, not as a tracked git repo. After clone+checkout
	@# we drop .git/ entirely so:
	@#   - VSCode doesn't show a separate Source Control entry for the nested repo
	@#   - we save ~34 MB of upstream history we never need
	@#   - we avoid accidentally committing into upstream's repo
	@# To bump INDEXTTS_REF: run `make clean-indextts2` first, then re-install.
	@# To force a re-clone: same. The `[ -d vendor/index-tts ]` guard below
	@# means re-running install-indextts2 with a different INDEXTTS_REF is a no-op
	@# unless you clean first - this is intentional (avoid accidental ref churn).
	@if [ ! -d vendor/index-tts ]; then \
	    git clone https://github.com/index-tts/index-tts vendor/index-tts \
	        && cd vendor/index-tts && git checkout $(INDEXTTS_REF) && cd ../.. \
	        && rm -rf vendor/index-tts/.git; \
	else \
	    echo "vendor/index-tts already exists - skipping clone (run 'make clean-indextts2' first to bump ref)"; \
	fi
	@echo ""
	@echo "==> [2/5] isolated venv via upstream's official uv flow..."
	# env -u VIRTUAL_ENV: prevents the parent shell's activated venv from
	# leaking in (uv pip install would otherwise install into the WRONG venv).
	cd vendor/index-tts && env -u VIRTUAL_ENV uv sync
	@echo ""
	@echo "==> [3/5] worker deps (fastapi/uvicorn/multipart/soundfile/dotenv)..."
	cd vendor/index-tts && env -u VIRTUAL_ENV uv pip install fastapi uvicorn 'python-multipart' soundfile python-dotenv
	@echo ""
	@echo "==> [4/5] IndexTTS-2 checkpoints (~6 GB, idempotent resume)..."
	uv run python scripts/indextts2/download_model.py
	@echo ""
	@echo "==> [5/6] prewarm facebook/w2v-bert-2.0 into HF cache (~2 GB)..."
	@echo "    (fetched by IndexTTS2 on first /load - prewarming makes HF_HUB_OFFLINE=1 honest)"
	cd vendor/index-tts && env -u VIRTUAL_ENV uv run python -c \
	    "from transformers import AutoModel, SeamlessM4TFeatureExtractor; \
	     AutoModel.from_pretrained('facebook/w2v-bert-2.0'); \
	     SeamlessM4TFeatureExtractor.from_pretrained('facebook/w2v-bert-2.0')"
	@# Upstream's infer_v2.py forces HF_HUB_CACHE='./checkpoints/hf_cache' at
	@# import time. Mirror w2v-bert into THAT dir so /load finds it.
	@# Try hardlink first (zero disk cost when same FS); fall back to copy if
	@# the HF cache lives on a different filesystem (split home, external disk,
	@# WSL drvfs, etc.). Hardlink-failed "Invalid cross-device link" -> deep copy.
	@echo "    -> mirror w2v-bert into vendor/index-tts/checkpoints/hf_cache/"
	@mkdir -p vendor/index-tts/checkpoints/hf_cache
	@if [ -d ~/.cache/huggingface/hub/models--facebook--w2v-bert-2.0 ] && \
	    [ ! -d vendor/index-tts/checkpoints/hf_cache/models--facebook--w2v-bert-2.0 ]; then \
	    cp -al ~/.cache/huggingface/hub/models--facebook--w2v-bert-2.0 \
	           vendor/index-tts/checkpoints/hf_cache/ 2>/dev/null \
	    || ( echo "    (hardlink failed, doing full copy ~2 GB; cross-filesystem)"; \
	         cp -a ~/.cache/huggingface/hub/models--facebook--w2v-bert-2.0 \
	               vendor/index-tts/checkpoints/hf_cache/ ); \
	fi
	@echo ""
	@echo "==> [6/6] patch editable .pth to relative path (cross-host portable)..."
	@# uv writes the host's absolute path into _editable_impl_indextts.pth.
	@# That breaks bind-mounting the venv into Docker (container sees a different
	@# absolute path). Replace with a relative path that points at the same
	@# vendor/index-tts/ dir from any mount target. Works for host AND container.
	@PTH=vendor/index-tts/.venv/lib/python3.10/site-packages/_editable_impl_indextts.pth; \
	    if [ -f "$$PTH" ]; then \
	        echo '../../../..' > "$$PTH"; \
	        echo "patched: $$PTH -> ../../../..  (resolves to vendor/index-tts from site-packages)"; \
	    else \
	        echo "WARNING: $$PTH not found - import may fail in Docker"; \
	    fi
	@echo ""
	@echo "==> verify host vendor venv import works after .pth patch..."
	@cd vendor/index-tts && env -u VIRTUAL_ENV .venv/bin/python -c \
	    "import indextts; print('  host import OK:', indextts.__file__)" \
	    || ( echo "FATAL: host import broke after .pth patch - revert manually"; exit 1 )
	@echo ""
	@echo "============================================================"
	@echo "IndexTTS2 install complete. Add to .env:"
	@echo "  TTS_INDEXTTS2_URL=http://localhost:9881"
	@echo "  TTS_INDEXTTS2_TIMEOUT=180"
	@echo ""
	@echo "Then in two terminals:"
	@echo "  make run-indextts2     # IndexTTS2 worker on :9881"
	@echo "  make serve             # main adapter on :9880"
	@echo ""
	@echo "Switch to IndexTTS2 at runtime:"
	@echo "  curl -X POST http://localhost:9880/model/switch \\"
	@echo "       -H 'content-type: application/json' \\"
	@echo "       -d '{\"model_id\":\"IndexTeam/IndexTTS-2\"}'"
	@echo "============================================================"

# Alias - keep 'install-indextts' working but prefer the canonical name.
install-indextts: install-indextts2
	@echo "(alias) prefer 'make install-indextts2' as canonical target"

# Wipe the vendored IndexTTS2 install (vendor source + isolated venv).
# Use this before bumping INDEXTTS_REF or to recover from a broken install.
# Does NOT touch models/indextts2/IndexTTS-2/ (the 6 GB checkpoints) -
# use `rm -rf models/indextts2` separately if you also want those gone.
clean-indextts2:
	@if [ -d vendor/index-tts ]; then \
	    echo "removing vendor/index-tts/ (~10 GB inc. isolated venv)..."; \
	    rm -rf vendor/index-tts; \
	    echo "done. Re-run 'make install-indextts2' to reinstall."; \
	else \
	    echo "vendor/index-tts/ does not exist - nothing to clean."; \
	fi

# IndexTTS2 worker process. Requires `make install-indextts2` first to populate
# vendor/index-tts/.venv with the indextts package + worker deps.
run-indextts2:
	@if [ ! -d vendor/index-tts ]; then \
	    echo "vendor/index-tts not found."; \
	    echo "Worker script scripts/indextts2/serve.py exists, but it needs the indextts package"; \
	    echo "from vendor/index-tts/.venv. Run 'make install-indextts2' (Phase B) to set that up."; \
	    exit 1; \
	fi
	cd vendor/index-tts && env -u VIRTUAL_ENV uv run python ../../scripts/indextts2/serve.py

# === LOCAL SERVER ===
serve:
	uv run python -m tts_adapter.cli

server:
	@$(eval ACTION := $(filter-out $@,$(MAKECMDGOALS)))
	@if [ "$(ACTION)" = "stop" ]; then \
		pkill -f "python.*tts_adapter" 2>/dev/null && echo "Server stopped" || echo "No server running"; \
	else \
		echo "Usage: make server stop"; \
	fi

stop:
	@:

# === TTS CLI ===
tts:
ifndef text
	@echo "Usage: make tts text=\"Your text here\" [instruct=\"...\"]"
else
ifdef instruct
	PYTHONPATH=. uv run python scripts/qwen3/tts.py "$(text)" --instruct "$(instruct)"
else
	PYTHONPATH=. uv run python scripts/qwen3/tts.py "$(text)"
endif
endif

# Voice design (requires VoiceDesign model)
tts-design:
ifndef text
	@echo "Usage: make tts-design text=\"Your text\" instruct=\"voice description\""
else ifndef instruct
	@echo "Usage: make tts-design text=\"Your text\" instruct=\"voice description\""
else
	PYTHONPATH=. uv run python scripts/qwen3/tts_design.py "$(text)" --instruct "$(instruct)"
endif

# Voice cloning (requires Base model)
tts-clone:
ifndef text
	@echo "Usage: make tts-clone text=\"Your text\" ref=sample.wav"
else ifndef ref
	@echo "Usage: make tts-clone text=\"Your text\" ref=sample.wav"
else
	PYTHONPATH=. uv run python scripts/qwen3/tts_clone.py "$(text)" --ref "$(ref)"
endif

# Voice cloning + emotion (requires TTS_ENGINE=indextts2 and a running worker).
# Pick exactly one emotion mode: emotion-text=, emotion-audio=, or emotion-vector=
# Worker URL falls back to the same default the engine uses; override with
#   make tts-clone-emotion TTS_INDEXTTS2_URL=http://other:9881 ...
TTS_INDEXTTS2_URL ?= http://localhost:9881

tts-clone-emotion:
ifndef text
	@echo "Usage: make tts-clone-emotion text=\"...\" ref=sample.wav emotion-text=\"angry\" [alpha=0.7]"
else ifndef ref
	@echo "Usage: make tts-clone-emotion text=\"...\" ref=sample.wav emotion-text=\"angry\" [alpha=0.7]"
else
	@curl -fsS "$(TTS_INDEXTTS2_URL)/health" >/dev/null 2>&1 || \
	    (echo "IndexTTS2 worker not running at $(TTS_INDEXTTS2_URL). Start it first: make run-indextts2"; exit 1)
	@PYTHONPATH=. uv run python scripts/indextts2/tts_clone_emotion.py "$(text)" \
	    --ref "$(ref)" \
	    $(if $(emotion-text),--emotion-text "$(emotion-text)") \
	    $(if $(emotion-audio),--emotion-audio "$(emotion-audio)") \
	    $(if $(emotion-vector),--emotion-vector "$(emotion-vector)") \
	    $(if $(alpha),--alpha $(alpha))
endif

# === TEST ===
test:
	@$(eval GOALS := $(filter-out $@,$(MAKECMDGOALS)))
	@$(eval MODE := $(word 1,$(GOALS)))
	@if [ "$(MODE)" = "batch" ]; then \
		$(MAKE) -s _test-batch; \
	elif [ -z "$(MODE)" ]; then \
		$(MAKE) -s _test-single; \
	else \
		echo "Usage: make test [batch]"; \
	fi

_test-single:
	@echo "Testing single TTS generation..."
	@curl -sf -X POST http://localhost:9880/tts \
		-H 'content-type: application/json' \
		-d '{"text":"Тест генерации","language":"Russian","speaker":"Ryan"}' \
		--output /tmp/tts_test.wav \
	&& echo "OK: /tmp/tts_test.wav" || echo "FAIL (is server running?)"

_test-batch:
	@echo "Testing batch TTS generation..."
	@curl -sf -X POST http://localhost:9880/tts/batch \
		-H 'content-type: application/json' \
		-d '{"items":[{"id":"001","text":"Первая фраза","language":"Russian","speaker":"Ryan"},{"id":"002","text":"Вторая фраза","language":"Russian","speaker":"Ryan"}]}' \
		--output /tmp/tts_batch.zip \
	&& echo "OK: /tmp/tts_batch.zip" || echo "FAIL (is server running?)"

batch:
	@:

# === CLEAN ===
clean:
	@echo "Cleaning temp files..."
	rm -f /tmp/tts_*.wav /tmp/tts_*.zip
	@echo "Done!"

# === DOCKER ===
# `make up` brings up everything that's installed on the host.
# Auto-detects models/indextts2/IndexTTS-2/ and adds --profile indextts2.
# Without that dir, only the main adapter (Qwen3) starts.

# Compute the active profiles based on which engines are downloaded.
# `make up ARGS=--profile=...` can override or augment.
# IndexTTS2 needs BOTH the checkpoints AND the bind-mounted vendor venv.
# Models alone aren't enough - the thin Docker worker bind-mounts the venv,
# so without it the container starts and immediately dies at CMD time.
INDEXTTS2_READY := $(shell \
    test -d models/indextts2/IndexTTS-2 && \
    test -x vendor/index-tts/.venv/bin/python && \
    echo yes || echo no)

# All-profiles set used for `down` / `logs all` / cleanup - we want to STOP
# any running indextts2 worker even if the host install state has since
# changed (e.g., user moved/deleted models or vendor after `make up`).
COMPOSE_PROFILES_ALL := --profile gpu --profile indextts2

# Up-time profile selection: only activate indextts2 if it's actually ready.
COMPOSE_PROFILES := --profile gpu
ifeq ($(INDEXTTS2_READY),yes)
COMPOSE_PROFILES += --profile indextts2
endif

build:
	@echo "Building with profiles:$(COMPOSE_PROFILES)"
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) build

# Build only the IndexTTS2 worker image (skips the main adapter rebuild).
build-indextts2:
	$(DOCKER_COMPOSE) --profile indextts2 build adapter-tts-indextts2

# Verify the worker container can import indextts + torch using the
# bind-mounted vendor venv. Catches .pth-relativization failures, ABI
# mismatches, and missing CUDA libs BEFORE you wait through `make up`
# and a real /load. Runs a one-shot container, no port conflict with `make up`.
verify-indextts2-docker:
	@if [ "$(INDEXTTS2_READY)" != "yes" ]; then \
	    echo "IndexTTS2 not ready - run make install-indextts2 first"; \
	    exit 1; \
	fi
	$(DOCKER_COMPOSE) --profile indextts2 run --rm --entrypoint "" \
	    adapter-tts-indextts2 \
	    /work/vendor/index-tts/.venv/bin/python -c \
	    "import indextts, torch; print('indextts:', indextts.__file__); print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available())"

# Build both images.
build-all:
	$(DOCKER_COMPOSE) --profile gpu --profile indextts2 build

rebuild:
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) build --no-cache --pull

up:
	@if [ "$(INDEXTTS2_READY)" = "yes" ]; then \
	    echo "IndexTTS2 ready (models + vendor venv) - including worker"; \
	else \
	    echo "IndexTTS2 not ready - skipping worker. Need both:"; \
	    echo "  models/indextts2/IndexTTS-2/        ($$([ -d models/indextts2/IndexTTS-2 ] && echo OK || echo MISSING))"; \
	    echo "  vendor/index-tts/.venv/bin/python  ($$([ -x vendor/index-tts/.venv/bin/python ] && echo OK || echo MISSING))"; \
	    echo "Run: make install-indextts2"; \
	fi
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) up -d --no-build
	@sleep 2
	@echo "Started. Run: make health"

# Always stop both profiles - even if INDEXTTS2_READY flipped to "no" since
# `make up`, we still want to shut down a running worker container.
down:
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES_ALL) down

# `make logs` -> main adapter; `make logs indextts2` -> worker; `make logs all` -> both.
logs:
	@$(eval LOG_TARGET := $(filter-out $@,$(MAKECMDGOALS)))
	@if [ "$(LOG_TARGET)" = "indextts2" ]; then \
	    $(DOCKER_COMPOSE) --profile indextts2 logs -f adapter-tts-indextts2; \
	elif [ "$(LOG_TARGET)" = "all" ]; then \
	    $(DOCKER_COMPOSE) $(COMPOSE_PROFILES_ALL) logs -f; \
	else \
	    $(DOCKER_COMPOSE) --profile gpu logs -f adapter-tts; \
	fi

# No-op stubs for the positional args used by `make logs [indextts2|all]` and
# `make test [batch]` so Make doesn't try to build them as real targets.
all indextts2:
	@:

health:
	@echo "main adapter (:9880):"
	@curl -sf http://localhost:9880/health && echo "" || echo "FAIL"
	@if [ "$(INDEXTTS2_READY)" = "yes" ]; then \
	    echo "indextts2 worker (:9881):"; \
	    curl -sf http://localhost:9881/health && echo "" || echo "FAIL"; \
	fi

shell:
	$(DOCKER_COMPOSE) --profile gpu exec adapter-tts bash

# Catch-all to allow arguments after commands
%:
	@:
