# syntax=docker/dockerfile:1.7
# Build context is the repo root: the image installs svoi-bot from the uv workspace.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependency layer: rebuilt only when manifests or the lock change.
COPY pyproject.toml uv.lock ./
COPY packages/contracts/pyproject.toml packages/contracts/
COPY apps/api/pyproject.toml apps/api/
COPY apps/bot/pyproject.toml apps/bot/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package svoi-bot

COPY packages/contracts packages/contracts
COPY apps/bot apps/bot
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package svoi-bot

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 svoi
COPY --from=build --chown=svoi:svoi /app/.venv /app/.venv
# FakeApiClient (BOT_USE_FAKE_API=true) serves the seed fixtures
COPY --chown=svoi:svoi packages/contracts/fixtures /app/fixtures
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 SVOI_FIXTURES_DIR=/app/fixtures
WORKDIR /app
USER svoi
