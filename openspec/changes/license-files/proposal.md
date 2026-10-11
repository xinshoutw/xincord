## Why

The owner added LICENSE (AGPL-3.0-or-later) on 2026-10-12, before PyPI's first release. Both
distributions declare the license by its expression only: `uv_build` packs no license file without
`license-files`, so neither wheel nor sdist holds the text that the AGPL asks to accompany the
program.

## What Changes

- `pyproject.toml` declares `license-files = ["LICENSE"]`.
- `packages/xincord-plugins/` gets a copy of LICENSE, which its `pyproject.toml` declares the same
  way: a project's license files must lie inside its own directory.
- A test keeps the copy equal to the root file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release`: one requirement added for the license in both distributions.

## Impact

`pyproject.toml`, `packages/xincord-plugins/pyproject.toml`, `packages/xincord-plugins/LICENSE`,
`tests/test_release.py`. The wheels gain `licenses/LICENSE` in their metadata and the sdists the
file.
