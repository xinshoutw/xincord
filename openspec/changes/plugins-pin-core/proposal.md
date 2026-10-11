## Why

`xincord-plugins` requires `xincord` without a version: its wheel says `Requires-Dist: xincord`.
Once both are on PyPI, installing `xincord-plugins==1.0.0` would take any later `xincord`, a 2.0
included, which may break the plugins. Both come from one tag with one version, so the plugins
should require exactly their own release of the core. A 1.0.0 also promises plugins outside the
repository a stable API, and nothing says which names that covers.

## What Changes

- `xincord-plugins` requires `xincord==<its own version>`. `scripts/release_version.py` fails a
  release whose pin names another version, or none; the README's "Releasing" says to set it.
- `docs/plugin-api.md` names the plugin API: the entry point and module conventions and the names
  of `xincord.core` that plugins use, under semantic versioning from 1.0.0. The rest of
  `xincord.core` is internal.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release`: the version check covers the plugins' requirement on the core.

## Impact

`packages/xincord-plugins/pyproject.toml`, `uv.lock`, `scripts/release_version.py`, README, the new
`docs/plugin-api.md`, `tests/test_release.py`. Installing `xincord-plugins` brings its own `xincord`.
