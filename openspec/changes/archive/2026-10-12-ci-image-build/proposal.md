## Why

Renovate's first run on 2026-10-12 opened PR #4, uv's image from 0.12 to 0.13. Its checks passed
although nothing had built the image: only a release tag builds it, and Renovate merges patch
updates of the Python image and of `uv.lock` itself once the gate passes, so a broken image would
show at the next release. The same PR's commit said `chore:`, not `build:`.

## What Changes

- The `ci` workflow gets a job `image`: on every push to `main` and every pull request it builds the
  image for linux/amd64 with the GitHub Actions cache, pushes nothing, and runs in it the import of
  every installed plugin and `xincord --no-online`. An update's PR builds the image before it merges.
- Renovate's package rules start with one that gives every package the type `build`, so that the
  presets of `config:recommended` no longer decide it; GitHub Actions keep `ci`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: the image is built and checked in CI.
- `project-tooling`: Renovate's commit type holds over the presets' types.

## Impact

`.github/workflows/ci.yml`, `.github/renovate.json`, `tests/test_container.py`,
`tests/test_dependency_updates.py`. Each CI run takes the image build longer, cached between runs.
