.PHONY: help install install-indextts2 install-indextts download-model download-indextts2 run-indextts2 serve server tts tts-clone tts-clone-emotion tts-design test build build-indextts2 build-all rebuild up down logs health shell clean

# Detect docker compose command (v2 with space vs v1 with hyphen)
DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Default target
help:
	@echo "TTS Adapter"
	@echo "==========="
	@echo ""
	@echo "Local (no Docker):"
	@echo "  make install         - Install deps (uv sync)"
	@echo "  make download-model  - Download model for offline use"
	@echo "  make serve           - Run server locally (Ctrl+C to stop)"
	@echo "  make server stop     - Kill local server"
	@echo "  make tts text=\"...\" [instruct=\"...\"] - Generate speech"
	@echo "  make tts-clone text=\"...\" ref=sample.wav - Clone voice (Base model)"
	@echo "  make tts-clone-emotion text=\"...\" ref=sample.wav emotion-text=\"angry\" [alpha=0.7] - Clone+emotion (IndexTTS2)"
	@echo "  make tts-design text=\"...\" instruct=\"...\" - Design voice (VoiceDesign model)"
	@echo ""
	@echo "IndexTTS2 (separate worker process - one-time install):"
	@echo "  make install-indextts2  - Clone upstream + isolated venv + worker deps + checkpoints (~6 GB)"
	@echo "  make run-indextts2      - Start IndexTTS2 worker on :9881"
	@echo "  make download-indextts2 - Re-download just the checkpoints (skip clone/venv)"
	@echo ""
	@echo "  make test            - Test single TTS generation"
	@echo "  make test batch      - Test batch TTS generation"
	@echo ""
	@echo "Docker (auto-detects engines installed in models/):"
	@echo "  make build           - Build images for installed engines (Qwen3 + IndexTTS2 if present)"
	@echo "  make build-indextts2 - Build only the IndexTTS2 worker image"
	@echo "  make build-all       - Build both images regardless of install state"
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

# Download model for offline use
download-model:
	uv run python scripts/qwen3/download_model.py

# Download IndexTTS-2 checkpoints only (use this to refresh weights without
# re-cloning vendor/index-tts or reinstalling the worker venv).
download-indextts2:
	uv run python scripts/indextts2/download_model.py

# Full IndexTTS2 install: clone upstream, set up isolated venv, install worker
# deps, download checkpoints. Idempotent - safe to re-run.
# Why two processes: see docs/engines/indextts2/README.md.
install-indextts2:
	@echo "==> [1/4] vendor/index-tts (idempotent clone)..."
	@if [ ! -d vendor/index-tts ]; then \
	    git clone https://github.com/index-tts/index-tts vendor/index-tts; \
	else \
	    echo "vendor/index-tts already exists - skipping clone"; \
	fi
	@echo ""
	@echo "==> [2/4] isolated venv via upstream's official uv flow..."
	# env -u VIRTUAL_ENV: prevents the parent shell's activated venv from
	# leaking in (uv pip install would otherwise install into the WRONG venv).
	cd vendor/index-tts && env -u VIRTUAL_ENV uv sync
	@echo ""
	@echo "==> [3/4] worker deps (fastapi/uvicorn/multipart/soundfile/dotenv)..."
	cd vendor/index-tts && env -u VIRTUAL_ENV uv pip install fastapi uvicorn 'python-multipart' soundfile python-dotenv
	@echo ""
	@echo "==> [4/4] IndexTTS-2 checkpoints (~6 GB, idempotent resume)..."
	uv run python scripts/indextts2/download_model.py
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
INDEXTTS2_INSTALLED := $(shell test -d models/indextts2/IndexTTS-2 && echo yes || echo no)
COMPOSE_PROFILES := --profile gpu
ifeq ($(INDEXTTS2_INSTALLED),yes)
COMPOSE_PROFILES += --profile indextts2
endif

build:
	@echo "Building with profiles:$(COMPOSE_PROFILES)"
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) build

# Build only the IndexTTS2 worker image (skips the main adapter rebuild).
build-indextts2:
	$(DOCKER_COMPOSE) --profile indextts2 build adapter-tts-indextts2

# Build both images.
build-all:
	$(DOCKER_COMPOSE) --profile gpu --profile indextts2 build

rebuild:
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) build --no-cache --pull

up:
	@if [ "$(INDEXTTS2_INSTALLED)" = "yes" ]; then \
	    echo "Detected models/indextts2/IndexTTS-2 - including indextts2 worker"; \
	else \
	    echo "models/indextts2/IndexTTS-2 not found - skipping indextts2 worker (run 'make install-indextts2' to enable)"; \
	fi
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) up -d --no-build
	@sleep 2
	@echo "Started. Run: make health"

down:
	$(DOCKER_COMPOSE) $(COMPOSE_PROFILES) down

# `make logs` -> main adapter; `make logs indextts2` -> worker; `make logs all` -> both.
logs:
	@$(eval LOG_TARGET := $(filter-out $@,$(MAKECMDGOALS)))
	@if [ "$(LOG_TARGET)" = "indextts2" ]; then \
	    $(DOCKER_COMPOSE) --profile indextts2 logs -f adapter-tts-indextts2; \
	elif [ "$(LOG_TARGET)" = "all" ]; then \
	    $(DOCKER_COMPOSE) $(COMPOSE_PROFILES) logs -f; \
	else \
	    $(DOCKER_COMPOSE) --profile gpu logs -f adapter-tts; \
	fi

all:
	@:

health:
	@echo "main adapter (:9880):"
	@curl -sf http://localhost:9880/health && echo "" || echo "FAIL"
	@if [ "$(INDEXTTS2_INSTALLED)" = "yes" ]; then \
	    echo "indextts2 worker (:9881):"; \
	    curl -sf http://localhost:9881/health && echo "" || echo "FAIL"; \
	fi

shell:
	$(DOCKER_COMPOSE) --profile gpu exec adapter-tts bash

# Catch-all to allow arguments after commands
%:
	@:
