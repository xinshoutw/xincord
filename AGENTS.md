# AGENTS.md

Rules for everyone who changes this repository, people and coding agents alike. There is no
CLAUDE.md on purpose: Claude Code reads this file when no CLAUDE.md exists.

xincord ports XsDiscordBotKt (Kotlin, JDA) to Python 3.14 + discord.py. Read these first:

- `docs/porting/decisions.md`: accepted decisions. Do not re-open them without asking the owner.
- `HANDOFF.md`: current state and next steps.
- `docs/porting/analysis/inventory/<Plugin>.md`: what each Kotlin module does, with `file:line`.
- `docs/porting-guide.md`: Kotlin/JDA to Python/discord.py mapping and known pitfalls.

## Commands

```sh
uv sync                       # create or update .venv from uv.lock
uv run prek install           # install the git hooks once per clone
scripts/gate.sh               # the full gate: ruff, pyright, pytest + coverage, openspec
npx --yes @fission-ai/openspec@1.14.1 <command>   # OpenSpec CLI (set OPENSPEC_TELEMETRY=0)
```

If your global git config sets `core.hooksPath`, run `git config --local core.hooksPath
.git/hooks` before `prek install`.

## Language

- Everything in the repository is English: code, comments, docstrings, tests, docs, OpenSpec.
- No CJK characters in `*.py`, tests included; a prek hook enforces it. Assert Chinese output
  through lang keys, YAML fixtures under `tests/fixtures/`, or code points such as
  `chr(0x4E2D)`. Do not type `\u` escapes through agent tools: some decode them into the real
  characters when writing the file.
- Lang YAML files and test fixture YAML are exempt.
- Commit messages are ASCII. Refer to lang keys instead of quoting UI text.

## Commits

- Conventional Commits, `type(scope): subject`, optional bullet body. Types: feat, fix, test,
  refactor, docs, build, ci, chore. Scopes: `core`, `build`, `ci`, `docs`, `plugin-<name>` where
  `<name>` is the plugin's package name in kebab case (`plugin-auto-role`).
- GPG-sign every commit and tag.
- No `Co-Authored-By`, session links or tool attribution; the commit-msg hook rejects them.
- Small and frequent. Every commit passes `scripts/gate.sh`.

## Test-driven development (xfail-first)

1. Write the test for one requirement. Run it and confirm it fails for the expected reason.
2. Commit it marked `@pytest.mark.xfail(strict=True, reason="<requirement name>")`, usually
   with `raises=NotImplementedError` against a stub. The gate stays green.
3. Implement, remove the marker, run the gate, commit.

- No product code without a failing test first. Scaffolding gets a smoke test.
- Test names or docstrings name the requirement; docstrings of ported behavior cite
  `XsDiscordBotKt@3a59607:<path>:<line>`.
- Pure logic is tested without discord.py. Cogs and views depend on narrow Protocols with
  hand-written fakes. Storage tests use SQLite `:memory:`.
- Before claiming something works, run the gate and show its output.

## OpenSpec

- One active change at a time, under `openspec/changes/<name>/`: proposal, spec deltas, design,
  tasks.
- Every scenario maps to at least one test.
- Keep each requirement's description under 500 characters; `validate --strict` fails otherwise.
- Archive right after the change is implemented and verified (`openspec archive <name> --yes`),
  then run `openspec validate --all --strict`.

## Porting rules

- Never port a known v3 defect. Record the difference as "v3 behaved differently: ..." in the
  change design and in `docs/porting-guide.md`.
- List every user-visible change (copy, commands, interaction flow) for the owner to review
  before it is pushed.
- Never commit real IDs, bank account numbers or tokens as defaults; use example values.
- discord.py evaluates the parameter annotations of app-command callbacks at import time. Keep
  those imports at runtime; add new decorators to
  `tool.ruff.lint.flake8-type-checking.runtime-evaluated-decorators` when ruff wants to move them.

## Pushing

- Pushing `main` to `origin` is allowed.
- Ask the owner first for: force pushes, deleting branches, tags, releases, PyPI publishing,
  repository settings, and anything on the XsDiscordBotKt remote.
- Do not create LICENSE; the owner adds it (AGPLv3).
