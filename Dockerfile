# syntax=docker/dockerfile:1

# TTS Adapter - GPU image for Qwen3-TTS inference
# Multi-stage build for optimal layer caching:
# 1. base: CUDA runtime + Python env vars (rarely changes)
# 2. deps: System packages + Python dependencies with locked versions
# 3. user_setup: Non-root user configuration
# 4. runtime: Application code only (changes frequently)

# Base stage: NVIDIA CUDA runtime
ARG REGISTRY=docker.io
FROM ${REGISTRY}/nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=300

# Deps stage: System packages + Python dependencies
FROM base AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    curl \
    tini \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s /usr/bin/python3.10 /usr/bin/python

# Install uv (pinned version)
ARG UV_VERSION=0.8.9
RUN curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh \
 && mv /root/.local/bin/uv /usr/local/bin/

WORKDIR /app

# Copy dependency lock files first (cache invalidates only when deps change)
COPY pyproject.toml uv.lock ./

# Install dependencies with BuildKit cache mount and locked versions
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

# User setup stage: Non-root user configuration
FROM deps AS user_setup

ARG USER=app
ARG UID=10001
RUN useradd -m -u ${UID} -s /bin/bash ${USER}
RUN install -d -o ${UID} -g ${UID} /work /home/${USER}/.cache/huggingface

# Runtime stage: Application code only (most frequently changed)
FROM user_setup AS runtime

ARG UID=10001

# Copy application code last
COPY --chown=${UID}:${UID} tts_adapter/ ./tts_adapter/
COPY --chown=${UID}:${UID} scripts/ ./scripts/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    HF_HOME="/home/app/.cache/huggingface"

USER ${USER}
EXPOSE 9880

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9880/health', timeout=10)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "tts_adapter.cli"]
