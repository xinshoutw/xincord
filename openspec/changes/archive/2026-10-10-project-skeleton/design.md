## Context

The decisions fix the stack (Python 3.14, uv, discord.py), the two-distribution layout (B2, B18,
resolution 2), strict gates (A8), the CJK and ASCII boundaries (A5) and xfail-first TDD (A11).
Tool versions were researched on 2026-10-08 (`docs/porting/analysis/research/tooling.md`).

## Goals / Non-Goals

**Goals:** one layout and one gate that every later change reuses; checks that run the same way in
prek, Claude Code and CI.

**Non-Goals:** runtime dependencies, Docker, release automation, PyPI publishing.

## Decisions

### Layout

```
pyproject.toml                    workspace root and the `xincord` (core) project
src/xincord/core/                 import package xincord.core (no src/xincord/__init__.py)
packages/xincord-plugins/         the `xincord-plugins` project
  src/xincord/plugins/            import package xincord.plugins
tests/                            one test tree for both distributions
scripts/                          gate.sh and the commit-message check
```

- The root project is `xincord` itself, so `uv sync` installs core plus the `dev` group, and the
  `dev` group pulls in the `xincord-plugins` workspace member.
- `uv_build` with a dotted `module-name` (`xincord.core`, `xincord.plugins`) builds a module inside
  the shared `xincord` namespace without shipping `xincord/__init__.py`.
- **Amends resolution 2:** `xincord.plugins` is a regular package (it has `__init__.py`); only
  `xincord` is a namespace. uv_build documents `namespace = true` (needed for a namespace with
  several roots) as disabling its safety checks, and third-party plugins register through the
  entry-point group with their own top-level package, so they never need to write into
  `xincord.plugins`.

### Gates

- `scripts/gate.sh` runs, in order: `ruff check`, `ruff format --check`, `pyright`, `coverage run
  -m pytest`, `coverage report` (branch coverage, `fail_under = 85`) and `openspec validate --all
  --strict` (OpenSpec 1.14.1 through `npx`). The pre-push hook, the Claude Code Stop hook and CI
  all call it, so the three can never drift apart.
- Coverage runs through `coverage` directly; pytest-cov is not needed.
- pytest uses the native `[tool.pytest]` table with `strict = true` (strict config, markers,
  parametrization ids and xfail) and `xfail_strict = true` spelled out for readers.
- Ruff: `select = ["ALL"]`. Ignored everywhere: `COM812` (formatter conflict), `D203`/`D213`
  (pick `D211`/`D212`, Google convention). Tests ignore `S101` (assert), `PLR2004` (literal
  values), `D` and `INP001`. Docstring rules apply to core only (A6).
- `lint.flake8-type-checking.runtime-evaluated-decorators` lists the discord.py decorators that
  evaluate parameter annotations at import time, so ruff never moves those imports under
  `TYPE_CHECKING`.

### Hooks

- prek runs `.pre-commit-config.yaml`. Every hook is `local` with `uv run --frozen`, so tool
  versions come from `uv.lock` only.
- The CJK check is a `pygrep` hook. prek compiles pygrep patterns as bytes, so the pattern matches
  UTF-8 byte sequences: `E3-E9 xx xx` covers U+3000..U+9FFF, `EF A4-AB xx` and `EF BC-BF xx`
  cover compatibility ideographs and fullwidth forms, `F0 A0-BF xx xx` covers U+20000..U+3FFFF.
  Emoji (`F0 9F ...`) and Latin letters are not matched.
- The commit-msg check is `scripts/check_commit_msg.py`. conventional-pre-commit accepts CJK
  subjects, so it is not used.
- Claude Code: PostToolUse runs `ruff format` and `ruff check --fix` on an edited `.py` file;
  Stop runs `scripts/gate.sh` and blocks with its output until the gate passes.

### CI

GitHub Actions on push and pull request: checkout, `astral-sh/setup-uv` pinned to v10.2.0 by
commit, setup-node for OpenSpec, `uv sync --locked`, then `scripts/gate.sh`. Every action is
pinned by commit SHA.

## Risks / Trade-offs

- Stop hook latency grows with the test suite. Accepted: the suite stays small and fast by design
  (B17); revisit if it passes 30 seconds.
- `openspec validate` needs `npx`; offline runs use the npm cache (`--prefer-offline`).

## User-visible changes

None.
