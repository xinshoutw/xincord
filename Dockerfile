# syntax=docker/dockerfile:1
# xincord with the official plugins, installed from uv.lock. Run it with compose.yaml.

FROM python:3.14.8-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# Dependencies first, so code changes reuse this layer until the lock file changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=packages/xincord-plugins/pyproject.toml,target=packages/xincord-plugins/pyproject.toml \
    uv sync --locked --no-dev --all-packages --no-install-workspace
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --all-packages --no-editable

FROM python:3.14.8-slim-trixie
# /bot/data is created here so a new named volume mounted there starts owned by xincord.
RUN useradd --uid 1000 --create-home xincord \
    && mkdir -p /bot/data \
    && chown -R xincord:xincord /bot
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1
USER xincord
WORKDIR /bot
ENTRYPOINT ["xincord"]
