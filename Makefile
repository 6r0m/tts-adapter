.PHONY: help install download-model download-indextts2 serve server tts tts-clone tts-clone-emotion tts-design test build rebuild up down logs health shell clean

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
	@echo "  make download-indextts2  - Download IndexTTS-2 checkpoints (offline use)"
	@echo "  make test            - Test single TTS generation"
	@echo "  make test batch      - Test batch TTS generation"
	@echo ""
	@echo "Docker:"
	@echo "  make build           - Build GPU image (online, one-time)"
	@echo "  make rebuild         - Force rebuild with no cache"
	@echo "  make up              - Start container (offline; reuses cached image)"
	@echo "  make down            - Stop container"
	@echo "  make logs            - View logs"
	@echo "  make health          - Test health endpoint"
	@echo "  make shell           - Shell into container"
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

# Download IndexTTS-2 checkpoints for offline use
download-indextts2:
	uv run python scripts/indextts2/download_model.py

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
# Build once online; `up` then runs offline via pull_policy: missing in compose.yml
build:
	$(DOCKER_COMPOSE) --profile gpu build

rebuild:
	$(DOCKER_COMPOSE) --profile gpu build --no-cache --pull

up:
	$(DOCKER_COMPOSE) --profile gpu up -d --no-build
	@sleep 2
	@echo "Started. Run: make health"

down:
	$(DOCKER_COMPOSE) --profile gpu down

logs:
	$(DOCKER_COMPOSE) --profile gpu logs -f adapter-tts

health:
	@echo "health: " && curl -sf http://localhost:9880/health && echo "" || echo "FAIL"

shell:
	$(DOCKER_COMPOSE) --profile gpu exec adapter-tts bash

# Catch-all to allow arguments after commands
%:
	@:
