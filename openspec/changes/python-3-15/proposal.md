# Proposal

## Why

Python 3.15 is out (3.15.2), and Renovate's PR #23 moves the image to it. That PR alone fails:
`uv sync` in the image looks for the 3.14 interpreter that `.python-version` names, and the
container test pins the 3.14 series. The owner allowed the move to 3.15 on 2026-11-15. Every test
passes on 3.15.2 with the locked dependencies.

## What Changes

- The image builds from `python:3.15.2-slim-trixie`, both stages.
- `.python-version` names 3.15, so development, CI and the image run the same interpreter.
- `requires-python` stays `>=3.14`, and pyright keeps checking against 3.14: the published
  distributions still install on 3.14.

Out of scope: dropping 3.14 support and adopting 3.15-only features.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: the image's Python series becomes 3.15.

## Impact

`Dockerfile`, `.python-version`, `tests/test_container.py`, `docs/architecture.md`,
`docs/pitfalls.md`, `AGENTS.md`, `openspec/config.yaml`, `HANDOFF.md`. Renovate's PR #23 becomes
redundant once this is pushed.
