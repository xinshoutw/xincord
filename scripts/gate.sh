#!/bin/sh
# The single quality gate. The pre-push hook, the Claude Code Stop hook and CI all run it.
set -eu
cd "$(dirname "$0")/.."

uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pyright
uv run --locked coverage run -m pytest
uv run --locked coverage report
OPENSPEC_TELEMETRY=0 npx --yes --prefer-offline @fission-ai/openspec@1.14.1 validate --all --strict </dev/null
