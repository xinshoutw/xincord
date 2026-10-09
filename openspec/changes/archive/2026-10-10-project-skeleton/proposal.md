## Why

xincord has no code yet. Before any behavior is ported from XsDiscordBotKt, the repository needs the
package layout chosen in the decisions (B2, B18, resolution 2) and the quality gates (A5, A8, A11)
so that every later commit is checked the same way locally, in Claude Code and in CI.

## What Changes

- A uv workspace with two distributions: `xincord` (import package `xincord.core`) and
  `xincord-plugins` (import package `xincord.plugins`), sharing the `xincord` namespace.
- Ruff (`select = ["ALL"]`), pyright strict, pytest 9 with strict mode and strict xfail,
  pytest-asyncio auto mode, and branch coverage of at least 85%.
- One gate script used by the pre-push hook, the Claude Code Stop hook and CI.
- A pre-commit configuration run with prek, including a CJK check for Python files and a
  commit-message check (ASCII, Conventional Commits).
- Claude Code hooks, a GitHub Actions workflow, `AGENTS.md`, `README.md`,
  `docs/porting-guide.md` and the `port-plugin` skill.

Out of scope: any bot behavior, runtime dependencies (each Core change adds its own), the
Dockerfile (Core change `container`) and LICENSE (the owner adds it).

## Capabilities

### New Capabilities

- `project-tooling`: package layout and the repository checks every commit must pass.

### Modified Capabilities

None.

## Impact

New files only. No Kotlin behavior is ported, so no `XsDiscordBotKt@3a59607` sources apply.
