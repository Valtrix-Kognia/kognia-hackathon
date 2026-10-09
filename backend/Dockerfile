# syntax=docker/dockerfile:1
# Kognia Voice agent worker (LiveKit Agents). Deploy with `lk agent deploy` or any container host.
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch

FROM base AS build
RUN apt-get update && apt-get install -y gcc g++ python3-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Dependencies first (cached across code changes). The package itself is installed after COPY.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra agent --no-dev --no-install-project

# Model files: LiveKit plugins (turn detector, etc.) and the Spanish emotion/sentiment models.
RUN uv run --no-project --module livekit.agents download-files
RUN uv run --no-project python -c "from pysentimiento import create_analyzer; \
create_analyzer(task='sentiment', lang='es'); create_analyzer(task='emotion', lang='es')"

COPY . .
RUN uv sync --locked --extra agent --no-dev

FROM base
ARG UID=10001
RUN adduser --disabled-password --gecos "" --home "/app" --shell "/sbin/nologin" --uid "${UID}" appuser
COPY --from=build --chown=appuser:appuser /app /app
WORKDIR /app
USER appuser
CMD ["uv", "run", "--no-sync", "app/voice/worker.py", "start"]
