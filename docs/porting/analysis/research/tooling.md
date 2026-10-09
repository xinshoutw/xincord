# Tooling research: Kotlin Discord bot -> Python 3.14 (uv, OpenSpec, strict TDD)

Research date: 2026-10-08. Facts come from primary sources: npm registry, PyPI JSON API,
GitHub releases/changelogs/source, and official docs. "Verified" means I ran it myself in
`scratchpad/tmp/` (ephemeral `npx --yes` / `uvx`, with npm/uv/pre-commit/prek/XDG caches
redirected into the scratchpad). Nothing was installed globally and the project repo was not touched.

Docs pages without a visible date are marked "undated, fetched 2026-10-08".

---

## 0. Version snapshot

| Tool | Latest | Release date | Primary source |
|---|---|---|---|
| OpenSpec `@fission-ai/openspec` | **1.14.1** | npm 2026-10-05 23:28 UTC (GitHub release 2026-10-06 00:38 UTC) | https://registry.npmjs.org/@fission-ai/openspec , https://github.com/Fission-AI/OpenSpec/releases/tag/v1.14.1 |
| OpenSpec Node requirement | `engines.node >=20.19.0` | same | `npm view @fission-ai/openspec engines`; README "Requires Node.js 20.19.0 or higher" |
| CPython 3.14 | **3.14.8** (expedited security release) | 2026-09-30 per python.org (PEP 745 lists 2026-10-01) | https://www.python.org/downloads/release/python-3148/ , https://peps.python.org/pep-0745/ |
| CPython 3.15 | 3.15.0rc3; **3.15.0 final expected 2026-10-09** | rc3 2026-10-02 | https://peps.python.org/pep-0790/ |
| uv / uv_build | **0.12.23** | 2026-10-03 | https://github.com/astral-sh/uv/releases/tag/0.12.23 , https://pypi.org/project/uv-build/ |
| astral-sh/setup-uv | **v10.2.0** (no floating `v10` tag exists) | 2026-09-21 | https://github.com/astral-sh/setup-uv/releases/tag/v10.2.0 |
| ruff | **0.16.10** | 2026-10-01 | https://github.com/astral-sh/ruff/releases/tag/0.16.10 |
| pyright (npm + PyPI wrapper) | **1.1.414** | 2026-09-09 | https://github.com/microsoft/pyright/releases/tag/1.1.414 |
| basedpyright | **1.40.2** (merged pyright 1.1.414 in 1.40.1) | 2026-10-04 | https://github.com/DetachHead/basedpyright/releases/tag/v1.40.2 |
| ty | **0.0.85**, Beta | 2026-10-06 | https://github.com/astral-sh/ty/releases/tag/0.0.85 |
| pytest | **9.1.1** | 2026-06-19 | https://github.com/pytest-dev/pytest/releases/tag/9.1.1 |
| pytest-asyncio | **1.4.0** | 2026-05-26 | https://github.com/pytest-dev/pytest-asyncio/releases/tag/v1.4.0 |
| anyio | **4.15.1** | 2026-09-05 | https://pypi.org/project/anyio/ |
| coverage | **7.16.2** | 2026-09-27 | https://pypi.org/project/coverage/ |
| pytest-cov | **7.1.0** | 2026-03-21 | https://github.com/pytest-dev/pytest-cov/blob/master/CHANGELOG.rst |
| dpytest | **0.7.0** (Development Status: Alpha) | 2023-06-19 | https://pypi.org/project/dpytest/ |
| discord.py | **2.7.1** | 2026-03-03 | https://pypi.org/project/discord.py/ |
| pydantic | **2.13.5** (2.14.0b2 pre-release) | 2026-08-28 (b2: 2026-09-09) | https://pypi.org/project/pydantic/ |
| pre-commit | **4.6.2** | 2026-08-10 | https://github.com/pre-commit/pre-commit/blob/main/CHANGELOG.md |
| prek | **0.5.5** | 2026-10-05 | https://github.com/j178/prek/releases/tag/v0.5.5 |
| commitizen | **4.19.2** | 2026-10-07 | https://github.com/commitizen-tools/commitizen/releases/tag/v4.19.2 |
| conventional-pre-commit | **4.4.0** | 2026-02-18 | https://github.com/compilerla/conventional-pre-commit/releases/tag/v4.4.0 |
| gitlint | **0.19.1** (unmaintained: last commit 2023-09-02) | 2023-03-10 | https://pypi.org/project/gitlint/ |
| Claude Code | latest **2.1.293**, next 2.1.294, stable 2.1.285 | 2026-10-07 / 2026-10-08 / 2026-09-29 | `npm view @anthropic-ai/claude-code dist-tags time` |

Local machine (observed): node v26.5.0 (OK for OpenSpec), **uv 0.10.8 (2026-03-03, two minor
versions behind; `uv init` defaults differ, see section 3)**, Homebrew python3 3.14.6 (older than the
3.14.8 security release), Claude Code 2.1.294.

---

## 1. OpenSpec

### 1.1 Install, requirements, telemetry

- Install: `npm install -g @fission-ai/openspec@latest`, or `brew install openspec` (Homebrew formula is
  1.14.1 and depends on `node`). Node >= 20.19.0.
- **The generated skills and commands call the `openspec` binary** (`allowed-tools: Bash(openspec:*)`), so
  the CLI must be on `PATH` for the agent workflow (global npm, brew, volta or mise). `npx` is fine for CI
  and git hooks.
- Telemetry is anonymous, opt-out, and automatically off in CI: `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0`,
  or `openspec config set telemetry.enabled false`. The global config lives at
  `$XDG_CONFIG_HOME/openspec/config.json` (default `~/.config/openspec/config.json`).
- Source: README and docs/cli.md (https://github.com/Fission-AI/OpenSpec, main pushed 2026-10-07).

### 1.2 Current workflow: OPSX (artifact-driven)

The legacy workflow is superseded. Legacy items: `/openspec:proposal|apply|archive`, `openspec/AGENTS.md`,
`openspec/project.md`, and OpenSpec marker blocks in CLAUDE.md/AGENTS.md. `openspec init` and
`openspec update` detect them and offer cleanup; they never delete your own content and never auto-delete
`project.md`.
Source: https://github.com/Fission-AI/OpenSpec/blob/main/docs/migration-guide.md (undated, fetched 2026-10-08).

| Profile | Workflows (slash commands in Claude Code) |
|---|---|
| `core` (default) | `/opsx:propose`, `/opsx:explore`, `/opsx:apply`, `/opsx:update`, `/opsx:sync`, `/opsx:archive` |
| expanded (opt in with `openspec config profile`, then `openspec update`) | adds `/opsx:new`, `/opsx:continue`, `/opsx:ff`, `/opsx:verify`, `/opsx:bulk-archive`, `/opsx:onboard` |

Typical loop:
1. `/opsx:explore`: read-only thinking partner; it writes nothing until you confirm.
2. `/opsx:propose <idea>`: creates `openspec/changes/<name>/` with proposal.md, specs/**, design.md and
   tasks.md. **It plans only and stops before writing code.**
3. `/opsx:apply`: implements tasks and ticks the `tasks.md` checkboxes.
4. `/opsx:archive`: merges the delta specs into `openspec/specs/` and moves the change to
   `changes/archive/YYYY-MM-DD-<name>/`.

The default schema is `spec-driven`, with artifacts proposal -> (specs, design) -> tasks. Custom schemas use
`openspec schema init|fork|validate|which`. Schema precedence is project `openspec/schemas/<name>/`, then user
`~/.local/share/openspec/schemas/<name>/`, then the built-in package schemas.

CLI reference (docs/cli.md, undated, fetched 2026-10-08; flags cross-checked with `openspec --help` 1.14.1):

| Command | Notes |
|---|---|
| `openspec init [path] --tools <ids\|all\|none> [--profile core\|custom] [--language <lang>] [--force] [--no-animation] [--copilot-cloud\|--no-copilot-cloud]` | Scaffolds `openspec/` and the tool integrations. `--tools` makes it non-interactive. |
| `openspec update [path] [--force]` | Regenerates skills/commands after a CLI upgrade. Generated files are OpenSpec-owned. |
| `openspec new change <kebab-name> [--description] [--goal] [--schema] [--json]` | Creates `.openspec.yaml` (schema, created date) and README.md. |
| `openspec status --change <id> [--json]` | Artifact DAG status; prints a `Next:` command. |
| `openspec instructions [<artifact>\|apply\|archive] --change <id> [--json]` | Agent instructions: template + config context/rules + dependencies. |
| `openspec list [--specs\|--changes\|--archived\|--all] [--sort] [--json]` | |
| `openspec show <item> [--type change\|spec] [--json] [--deltas-only] [--no-interactive]` | |
| `openspec validate [item] [--all\|--changes\|--specs\|--archived] [--strict] [--json] [--concurrency n] [--no-interactive]` | Exit 1 on failure. `--archived` fails if an archived change still has unchecked tasks. |
| `openspec archive <change> --yes [--skip-specs] [--no-validate]` | Without a TTY it refuses and prints the `--yes` command to rerun (verified). |
| `openspec view` | TUI dashboard. |
| `openspec schemas`, `openspec templates`, `openspec schema ...`, `openspec config ...`, `openspec store ...` (beta: a separate planning repo), `openspec version [--check --json]` | |

### 1.3 Directory layout and config

```
openspec/
  config.yaml                         # schema + context + rules + operations (replaces project.md)
  specs/<capability>/spec.md          # source of truth (current behavior)
  changes/<change>/
    .openspec.yaml                    # schema: spec-driven, created: YYYY-MM-DD (+ skip_specs / retire_capabilities)
    README.md  proposal.md  design.md  tasks.md
    specs/<capability>/spec.md        # DELTA spec
  changes/archive/YYYY-MM-DD-<change>/
```

`config.yaml` fields: `schema`; `context` (injected into every artifact instruction inside
`<project_context>`, 50 KB limit); `rules.<artifact-id>` (only for that artifact); and
`operations.apply|archive.guidance` (advisory). Since 1.14.0, `init` guides an AI-assisted move from a legacy
`project.md`, and the agents are steered to keep general project documentation out of `context`.

Verified project config. The context and rules were injected into `openspec instructions` output, and the
guidance appeared in `instructions apply --json` as `operationGuidance`:

```yaml
schema: spec-driven

context: |
  Python 3.14 Discord bot (discord.py) managed by uv; port of a Kotlin JDA bot.
  Quality gates: ruff check, ruff format --check, pyright strict, pytest.
  Code, identifiers, comments and commit messages are English, ASCII only.

rules:
  specs:
    - Each scenario maps to one pytest test; name the test after the scenario
  tasks:
    - Every task group starts with a failing test (RED) before the implementation task (GREEN)

operations:
  apply:
    guidance:
      - Before ticking a task, run uv run ruff check, uv run pyright and uv run pytest; fix failures first
```

### 1.4 Spec format

Main spec, exactly as `archive` generated it in the verified run:

```markdown
# ping-command Specification

## Purpose
Lets operators verify that the bot is online and measure its gateway round-trip latency.

## Requirements

### Requirement: Ping replies with latency
The bot SHALL reply to the `/ping` slash command with the current gateway latency in milliseconds.

#### Scenario: Healthy connection
- **WHEN** a user invokes `/ping`
- **THEN** the bot replies ephemerally with "Pong" and the latency rounded to whole milliseconds
```

Delta spec (`changes/<c>/specs/<cap>/spec.md`) sections:

- `## Purpose`: **only for a new capability**. It must be at least 50 characters, or `--strict` reports it
  as too brief. Archive copies it into the new main spec; without it you get a `TBD` placeholder.
- `## ADDED Requirements`: new behavior.
- `## MODIFIED Requirements`: copy the **entire** existing block and edit it. If the block drops scenarios,
  `validate` fails. Verified: exit 1 with "omits scenario(s) the current spec still has".
- `## REMOVED Requirements`: include `**Reason**:` and `**Migration**:`.
- `## RENAMED Requirements`: `- FROM: `### Requirement: Old Name`` / `- TO: `### Requirement: New Name``. If the
  content also changes, put it under MODIFIED using the new header.

Format rules (from `openspec instructions specs`, 1.14.1):

- Requirement headers are `### Requirement: <name>` and use SHALL/MUST.
- Scenario headers use exactly 4 hashes: `#### Scenario: <name>`, followed by `- **WHEN**` / `- **THEN**`
  bullets.
- Every requirement needs at least one scenario.
- A requirement description over 500 characters is a warning, so `--strict` fails (new in 1.14.1).

Archive semantics:

- Deltas apply in this order: RENAMED, REMOVED, MODIFIED, ADDED. Matching is by normalized header
  (`openspec/specs/openspec-conventions/spec.md` in the OpenSpec repo).
- A change with no deltas must declare `skip_specs: true` in `.openspec.yaml`.
- Deleting a capability's whole spec requires `retire_capabilities: true`.

### 1.5 Supported tools, and exactly what `init` generates

`openspec init --help` (1.14.1) accepts **50 tool IDs**: amazon-q, amp, antigravity, atomcode, auggie, bob,
claude, cline, command-code, codeartsagent, codex, dsh, devin, forgecode, codebuddy, codestudio, continue,
costrict, crush, cursor, easycode, factory, gemini, github-copilot, gigacode, grok, gsd, hermes, iflow, junie,
kilocode, kimi, kiro, lingma, minimax-code, vibe, oh-my-pi, opencode, pi, codeassistant, qoder, qwen, rovodev,
roocode, trae, veai, warp, zed, zcode, agents. `windsurf` is accepted as an alias for `devin`.
docs/supported-tools.md and docs/cli.md on main still list the pre-1.14 set, so the docs lag the CLI.

**Verified Claude Code run.** Command, run in an empty scratch git repo:
`npx --yes @fission-ai/openspec@latest init --tools claude --no-animation </dev/null`, with exit 0.

```
.claude/commands/opsx/{apply,archive,explore,propose,sync,update}.md         -> /opsx:<id>
.claude/skills/openspec-propose/SKILL.md                                     -> /openspec-propose (also model-invocable)
.claude/skills/openspec-explore/SKILL.md
.claude/skills/openspec-apply-change/SKILL.md
.claude/skills/openspec-update-change/SKILL.md
.claude/skills/openspec-sync-specs/SKILL.md
.claude/skills/openspec-archive-change/SKILL.md
openspec/config.yaml               (schema: spec-driven + commented context/rules/operations examples)
openspec/specs/.gitkeep
openspec/changes/archive/.gitkeep
```

- It generates both slash commands and skills: "6 skills and 6 commands in .claude/". It creates **no
  CLAUDE.md, no AGENTS.md block, no hooks and no settings.json**. That is about 2,650 lines in total; each
  file is 105 to 354 lines.
- Command frontmatter: `name: "OPSX: Propose"`, `description`, `allowed-tools: Bash(openspec:*)`,
  `category: "Workflow"`, `tags`.
- Skill frontmatter: `name`, `description` (with trigger phrases such as "openspec propose" / "opsx
  propose"), `allowed-tools: Bash(openspec:*)`, `license: MIT`, `compatibility: Requires openspec CLI.`,
  and `metadata.generatedBy: "1.14.1"`. `openspec update` uses that version stamp to detect drift.
  Do not hand-edit these files; put project guidance in `config.yaml`.
- The generated apply skill never tells the agent to run tests or linters. Strict TDD has to come from
  `config.yaml` rules/operations and from Claude Code hooks (section 8).

**Verified Codex run** (`--tools claude,codex`):

- Adds `.agents/skills/openspec-*/SKILL.md` (the same 6 skills) plus `.agents/skills/.openspec-target`,
  which contains `codex`.
- Writes no command or prompt files. The output says "Commands skipped for: codex (uses skills)".
- Invocation is `$openspec-propose` in the Codex CLI/IDE.
- No AGENTS.md is created or edited. supported-tools.md also states that `openspec update` strips old
  OpenSpec marker blocks from AGENTS.md.
- Not confirmed in the Claude Code docs: whether Claude Code reads `.agents/skills`. Select both
  `claude` and `codex` to get both trees.

### 1.6 Verified end-to-end lifecycle (1.14.1)

1. `new change add-ping-command`, then I wrote the four artifacts.
2. `status` showed 4/4.
3. `validate --strict` passed.
4. `show --json --deltas-only` reported 1 ADDED requirement.
5. `archive` with stdin closed exited 1 and printed `Fix: openspec archive add-ping-command --yes`.
6. `archive --yes` created `openspec/specs/ping-command/spec.md` and moved the change to
   `changes/archive/2026-10-08-add-ping-command/`.
7. `validate --all --strict` and `validate --archived` passed.

### 1.7 OpenSpec as a git hook (verified with pre-commit 4.6.2 and prek 0.5.5)

```yaml
  - repo: local
    hooks:
      - id: openspec-validate
        name: openspec validate --all --strict
        language: node
        language_version: system
        additional_dependencies: ["@fission-ai/openspec@1.14.1"]
        entry: openspec validate --all --strict --no-interactive
        pass_filenames: false
        files: ^openspec/
      - id: openspec-archived-tasks
        name: archived changes have no unchecked tasks
        language: node
        language_version: system
        additional_dependencies: ["@fission-ai/openspec@1.14.1"]
        entry: openspec validate --archived --no-interactive
        pass_filenames: false
        files: ^openspec/changes/archive/
```

### 1.8 Known pain points (GitHub issues)

| Issue | Date / state | Pain point |
|---|---|---|
| #2033 https://github.com/Fission-AI/OpenSpec/issues/2033 | 2026-10-02, open | Maintainers question deterministic archive merging. Header-name matching is brittle; failures surface late (#1112); two changes modifying one requirement silently lose scenarios (#1246); a renamed scenario reads as deleted (#1697). |
| #1387 | 2026-07-19, open | **Spec drift with parallel changes**: a delta records only the new text of a MODIFIED requirement, so the second change to archive conflicts or overwrites. A community tool, `concord`, detects this. |
| #1652 | 2026-08-14, open | **Archive discipline**: `archive --yes` archives even with unchecked tasks (warning only), and checkboxes are self-reported by the agent. |
| #2053 | 2026-10-06, open, reproduced on 1.14.1 | Archive silently drops delta text outside requirement blocks (`## Notes`, intro prose), and `validate --strict` still passes. |
| #1983 | 2026-09-25, open | Agents drift from the spec; apply never runs the project's checks, so "done" just means the tasks are ticked. |
| #1968 | 2026-09-24, open | Exploration: "OpenSpec without archive", where specs sync as tasks complete. |
| #1212 | closed 2026-06-15 | The fast path produced stale specs (fixed). |

Mitigations for this project:

- Keep one intent per change.
- Archive in the same PR as the implementation.
- Run `openspec validate --all --strict` and `--archived` in a hook and in CI.
- Avoid two open changes touching the same requirement.
- Review the `openspec/specs/` diff after archiving.
- Keep extra notes in design.md, never in delta specs.

---

## 2. Python 3.14

### 2.1 Releases

- **3.14.8**: python.org dates it Sept 30, 2026; PEP 745 lists 2026-10-01. It is "an expedited security
  release and the eighth maintenance release of 3.14", with about 354 changes. Its security fixes include
  an SSL context use-after-free, SSL `wrap_bio()` validation, zipfile memory exhaustion, a tarfile filter
  bypass, urllib credential leakage, plus bundled Expat/OpenSSL updates. It warns that tkinter/IDLE may hang
  on macOS 27.0. Source: https://www.python.org/downloads/release/python-3148/ .
- Schedule (PEP 745): bugfix releases about every 2 months. 3.14.9 is expected 2026-12-01, and the last
  regular bugfix release is 3.14.14, expected 2027-10-05. After that come source-only security fixes until
  about 2030-10.
- **3.15.0 final is expected 2026-10-09** (PEP 790). uv 0.12.23 already ships 3.15.0rc3, and uv 0.12.22
  (2026-10-01) added the 3.14.8 builds.
- Recommendation: pin `requires-python = ">=3.14"` and `.python-version` = `3.14`, and use uv-managed
  **3.14.8 or newer**. The local Homebrew 3.14.6 predates the security fixes.

### 2.2 PEP 649 / PEP 749: deferred annotations

Source: https://docs.python.org/3.14/whatsnew/3.14.html (undated, fetched 2026-10-08).

- Annotations are no longer evaluated eagerly. They are stored in annotate functions and evaluated on
  access, except under `from __future__ import annotations`, whose behavior is unchanged in 3.14.
  `from __future__ import annotations` is deprecated, but it will not be removed before 3.13 reaches EOL
  in 2029.
- The `annotationlib` module has `get_annotations(obj, format=Format.VALUE|FORWARDREF|STRING)`.
  `inspect.signature()` gained `annotation_format`. Do not read annotations from a class namespace dict;
  use `annotationlib.get_annotate_from_class_namespace()` during class construction.
- **discord.py impact (verified on 3.14.6 with discord.py 2.7.1).**
  - `app_commands.command` / `commands.command` read the callback annotations at decoration time.
  - A parameter annotated with a name imported only under `if TYPE_CHECKING:` therefore raises
    **NameError when the module is imported**. Unquoted forward references now evaluate lazily, but
    TYPE_CHECKING-only names still fail at runtime.
  - The maintainers say this is intended: issue #10501 (opened 2026-08-13, closed 2026-08-15),
    https://github.com/Rapptz/discord.py/issues/10501 . The workaround is a real runtime import, or a
    string / `ForwardRef` annotation.
  - discord.py 2.7.0 fixed "flag annotations not working under Python 3.14" (#10349) and uses the stdlib
    `compression.zstd` on 3.14.
  - PyPI classifiers only list up to 3.12, but the changelog includes the 3.14 fixes.
- **ruff interplay (verified, ruff 0.16.10).**
  - If you enable the `TC` (flake8-type-checking) rules, TC001 tells you to move `from bot.core import
    XsBot` into a TYPE_CHECKING block when it is only used in `discord.Interaction[XsBot]`. Following that
    advice breaks the command at runtime.
  - Fix: `[tool.ruff.lint.flake8-type-checking] runtime-evaluated-decorators = ["discord.app_commands.command", ...]`
    silenced it in the test. Add the other decorators you use, for example `discord.ext.commands.command`,
    `discord.ext.commands.hybrid_command`, `discord.app_commands.context_menu` and
    `discord.app_commands.CommandTree.command`. Only `discord.app_commands.command` was tested.
  - TC001-TC003 are **not** in ruff 0.16's default rule set; only TC004, TC005, TC007 and TC010 are.
- **pydantic**: 2.12 (article dated 2025-10-07) brought "initial Python 3.14 support"; the release article
  says Pydantic "still has limited support" for some lazily evaluated annotation cases. Pydantic V1 does
  not work on 3.14+, except the `pydantic.v1` shim, which matches 1.10.26.
  Source: https://pydantic.dev/articles/pydantic-v2-12-release . The exact remaining limitations are **not
  confirmed**, so test models that use forward references.
- discord.py's own `typing.TYPE_CHECKING` guidance does not change. Anything used in a command signature
  must be importable at runtime.

### 2.3 asyncio changes relevant to a bot

Each deprecation message was verified on 3.14.6:

| Change | Effect / action |
|---|---|
| `asyncio.get_event_loop()` with no running/current loop now **raises RuntimeError** ("There is no current event loop in thread 'MainThread'.") instead of creating one | Old `loop = asyncio.get_event_loop(); loop.run_until_complete(...)` templates break. Use `asyncio.run(main())` or `async with bot: await bot.start(token)`. discord.py's own `examples/basic_voice.py` still calls `asyncio.get_event_loop()`. |
| The policy system is deprecated (removal planned for 3.16): `get_event_loop_policy`, `set_event_loop_policy`, `*EventLoopPolicy` | For uvloop, use `asyncio.run(main(), loop_factory=uvloop.new_event_loop)` or `uvloop.run()`, not `set_event_loop_policy`. |
| `asyncio.iscoroutinefunction` deprecated (removal in 3.16): `DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead` | **discord.py 2.7.1 still calls it** in `Client.event`, `commands.Bot.*`, and the `ext/commands/core.py` decorators (verified in the 2.7.1 wheel, and a test caught the warning from `@client.event`). It is fixed on master (`discord/utils.py` uses `inspect.iscoroutinefunction` on 3.12+) but unreleased. With pytest `filterwarnings = ["error"]`, add `"ignore:'asyncio.iscoroutinefunction' is deprecated:DeprecationWarning:discord"`. |
| `create_task()` (asyncio, loop, TaskGroup) forwards arbitrary kwargs to the Task/task factory | Mostly transparent. |
| Introspection: `python -m asyncio ps PID` / `pstree PID`, `asyncio.capture_call_graph()` / `print_call_graph()` | Debug hung bots in production. |
| asyncio got 10-20% faster (per-thread linked list of tasks), and free-threading is supported | |
| Child watchers removed | Irrelevant unless you use subprocess watchers. |

### 2.4 Other 3.14 items for a long-running service

- **GC**: 3.14.0 through 3.14.4 shipped a new incremental GC. **It was reverted to the 3.13 generational GC
  in 3.14.5+** after "reports of significant memory pressure in production environments" (What's New). Use
  3.14.5 or newer, and preferably 3.14.8.
- PEP 765: `return`/`break`/`continue` leaving a `finally` block is a SyntaxWarning. PEP 758:
  `except A, B:` without parentheses is allowed when there is no `as` clause. Template strings (PEP 750)
  are available.
- PEP 768: `sys.remote_exec()` and `python -m pdb -p PID` can attach to a live process. Disable with
  `PYTHON_DISABLE_REMOTE_DEBUG` or `-X disable-remote-debug`.
- On Linux, multiprocessing now defaults to `forkserver`. `compression.zstd` is in the stdlib.
  `-X context_aware_warnings` makes `catch_warnings` safe across tasks.

### 2.5 Free-threaded build status

- PEP 779 says free-threading is "officially supported and no longer experimental (phase II)", but still
  optional; there is no decision on making it the default. The single-thread penalty is about 5-10%. There
  is no JIT in free-threaded builds.
- Wheel availability, checked on PyPI 2026-10-08:
  - cp314t wheels exist for aiohttp 3.14.4, yarl, multidict, frozenlist, pydantic-core 2.46.5 and
    PyNaCl 1.6.2.
  - orjson 3.13.0 has **no** cp314t wheel.
  - discord.py is pure Python.
- Recommendation: use the default GIL build. An asyncio bot runs on one event loop thread, so
  free-threading adds risk without benefit.

---

## 3. uv

- **0.12.23** was released 2026-10-03. The `uv_build` classifier is "Development Status :: 5 -
  Production/Stable".
- **0.12.0 (2026-07-28)** contains breaking changes. Verified with `uvx uv@0.12.23 init uv-init-demo --python 3.14`:
  - **`uv init` now creates a packaged project by default**: `src/<pkg>/__init__.py`,
    `[project.scripts] <name> = "<pkg>:main"`, and
    `[build-system] requires = ["uv_build>=0.12.23,<0.13.0"]`, `build-backend = "uv_build"`.
    `uv init --no-package` gives the old layout.
  - Pre-release handling now defaults to `if-necessary`.
  - sdists must be `.tar.gz` (or legacy zip).
  - `--require-hashes` directives are honored.
  - Changelog: https://github.com/astral-sh/uv/blob/main/CHANGELOG.md
- **uv_build**: `[build-system] requires = ["uv_build>=0.12.23,<0.13"]`. The expected layout is
  `src/<normalized_name>/__init__.py`, overridable with `[tool.uv.build-backend] module-name / module-root`.
  The upper bound is recommended because uv_build follows uv's versioning.
  Source: https://docs.astral.sh/uv/concepts/build-backend/ (undated, fetched 2026-10-08).
- **Lock and sync.** Source: https://docs.astral.sh/uv/concepts/projects/sync/ , plus `uv sync --help` in 0.12.23.
  - `uv run` and `uv sync` auto-lock and auto-sync by default.
  - `--locked` (env `UV_LOCKED`) errors if `uv.lock` would change. **Use it in CI and in hooks**:
    `uv sync --locked`, `uv run --locked pytest`.
  - `--frozen` (env `UV_FROZEN`) uses the lockfile without checking it.
  - `uv lock --check` is equivalent to `--locked` for lock-only checks.
  - `uv sync --check` verifies that the environment is in sync.
  - New releases on PyPI do not make a lock stale; `uv lock --upgrade` (or `--upgrade-package`) does.
  - `uv sync` removes extraneous packages; `uv run` does not.
- **Workspaces.** Source: https://docs.astral.sh/uv/concepts/projects/workspaces/
  - Declare `[tool.uv.workspace] members = ["packages/*"]` (with optional `exclude`) in the root; the root
    is also a member.
  - Members depend on each other via `[tool.uv.sources] x = { workspace = true }`; these are editable.
  - There is **one shared `uv.lock`** and one `requires-python`, which is the intersection of all members.
  - `uv run --package <m>` and `uv sync --package <m>` target one member; `uv sync --all-packages` syncs all.
  - Do **not** use a workspace if members need conflicting deps or separate venvs. In that case use path
    dependencies (`{ path = "plugins/x" }`).
  - Fit for this repo: one package per bot plugin, mirroring Kotlin `Plugins/*`, works as members if they
    share one dependency set.
- **GitHub Action astral-sh/setup-uv: latest v10.2.0** (2026-09-21), at commit
  `c18668ad3cf93ea998bef934396af7bb5c839dc7`.
  - **Since v8.0.0 (2026-03-29) there are no floating major or minor tags**, so `@v10` does not resolve
    (`git/ref/tags/v10` returns 404). Releases are immutable.
  - Pin `astral-sh/setup-uv@v10.2.0`, or better
    `astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0`.
  - v10.0.0 (2026-08-12) disabled `enable-cache: auto` for `pull_request_target`, `workflow_run` and
    `release` events, and added `version: latest-known` (checksum-verified).
  - v9.0.0 (2026-07-21) changed `prune-cache` to default to false.
  - The action reads `required-version` from uv.toml or pyproject.

Minimal CI:

```yaml
- uses: actions/checkout@<sha>
- uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
  with:
    enable-cache: true
- run: uv sync --locked --all-groups
- run: uv run --locked ruff format --check
- run: uv run --locked ruff check
- run: uv run --locked pyright
- run: uv run --locked pytest --cov
```

---

## 4. Linters and type checkers

### ruff 0.16.10 (2026-10-01)

- **0.16.0 (2026-07-23)** is a breaking release:
  - The **default rule set grew to 413 rules (from 59)**, including PYI, UP, F, RUF, PLE, B, SIM, PLW,
    FURB, C, PLR, ASYNC (10 rules), TC004/005/007/010 and others. 18 opinionated E/F rules left the
    default set, including E402, E731, E741 and F403/F405.
  - **Markdown code blocks are formatted by default.**
  - New `# ruff: ignore[CODE]` comments.
  - `format --check` supports `--output-format github`.
  - Sources: https://github.com/astral-sh/ruff/releases/tag/0.16.0 and the blog post
    https://astral.sh/blog/ruff-v0.16.0 .
- `target-version` accepts up to `"py314"`; there is no py315 yet, and the default is py310. If unset, ruff
  infers it from `requires-python`. Verified with `ruff config target-version`.
- Useful extras: `PLC2401` (non-ASCII identifier). The ambiguous-unicode rules RUF001-003 are not in the
  default set.

### pyright 1.1.414 (2026-09-09)

- 1.1.407 (2025-10-24) changed the default `pythonVersion` to 3.14.
- 1.1.402 (2025-06-11) added PEP 750 t-strings and PEP 758.
- 1.1.400 (2025-04-23) added PEP 765.
- Deferred-annotation semantics are modeled for 3.14.
- The PyPI `pyright` package is a wrapper (`nodeenv` dependency) that downloads the npm package at runtime.
  Use `pyright[nodejs]` to get bundled Node (`nodejs-wheel-binaries`), and set `PYRIGHT_PYTHON_CACHE_DIR`
  in CI.
- Verified: `uv run --locked pyright` with `typeCheckingMode = "strict"` and `pythonVersion = "3.14"`
  reported 0 errors on the demo.

### basedpyright 1.40.2 (2026-10-04)

- It is a pyright fork that follows upstream; 1.40.1 (2026-09-10) merged 1.1.414.
- The PyPI package bundles Node via `nodejs-wheel-binaries>=20.13.1`, so there is no runtime download.
  1.40.0 (2026-09-07) dropped Python 3.8/3.9 from the PyPI package.
- It adds extra rules (`recommended` and `all` modes) and baseline support. It is a drop-in option if you
  want stricter-than-strict checks.

### ty 0.0.85 (2026-10-06): Beta

- The README says: "ty is currently in beta". It uses 0.0.x versioning, "breaking changes, including changes
  to diagnostics, may occur between any two versions".
- The first Beta was 0.0.2 (2025-12-16), described as "ready to recommend to motivated users for production
  use".
- The Stable milestone is open with 102 open and 723 closed issues and no due date.
- **Use as an optional fast advisory check (or as an LSP), not as the gate.** Keep pyright strict as the
  gate. Sources: https://github.com/astral-sh/ty and https://github.com/astral-sh/ty/milestone/4

### Verified gate config (all four gates passed on CPython 3.14.6, uv 0.12.23)

```toml
[project]
requires-python = ">=3.14"

[dependency-groups]
dev = ["pytest>=9.1", "pytest-asyncio>=1.4", "pytest-cov>=7.1", "ruff>=0.16", "pyright>=1.1.414"]

[build-system]
requires = ["uv_build>=0.12.23,<0.13"]
build-backend = "uv_build"

[tool.pytest]                      # pytest 9 native TOML table
minversion = "9.0"
testpaths = ["tests"]
strict = true                      # strict_config + strict_markers + strict_parametrization_ids + strict_xfail
addopts = ["--import-mode=importlib"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
asyncio_default_test_loop_scope = "function"
# filterwarnings = ["error", "ignore:'asyncio.iscoroutinefunction' is deprecated:DeprecationWarning:discord"]

[tool.coverage.run]
branch = true
source = ["<your_pkg>"]

[tool.ruff]
target-version = "py314"

[tool.ruff.lint.flake8-type-checking]
runtime-evaluated-decorators = ["discord.app_commands.command"]

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
include = ["src", "tests"]
```

---

## 5. Testing stack

- **pytest 9.1.1 (2026-06-19).**
  - 9.0.0 (2025-11-08) added **native TOML config** (`[tool.pytest]`, `pytest.toml`), a **`strict = true`**
    mode, and built-in **subtests**.
  - Classifiers list 3.14 and 3.15.
  - 9.1 deprecations: class-scoped fixtures as instance methods, non-Collection parametrize values,
    `--pastebin`.
- **pytest-asyncio 1.4.0 (2026-05-26).** Defaults per https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html :
  - `asyncio_mode` defaults to **strict**. Async tests need `@pytest.mark.asyncio`, and async fixtures need
    `@pytest_asyncio.fixture`. Verified: in strict mode, an async `@pytest.fixture` fails with "requested an
    async fixture ... with no plugin or hook that handled it".
  - `asyncio_default_fixture_loop_scope`: when unset it falls back to the fixture's own scope and warns. The
    docs say "In future versions ... the value will default to `function`".
  - `asyncio_default_test_loop_scope` defaults to **function**.
  - `asyncio_debug` is off by default.
  - 1.4.0 added the `pytest_asyncio_loop_factories` hook (for example a uvloop factory) and deprecated
    overriding the `event_loop_policy` fixture.
  - 1.3.0 (2025-11-10) added pytest 9 support and dropped Python 3.9; 3.14t is tested.
  - Recommendation: `asyncio_mode = "auto"`, with both loop scopes set to `"function"` explicitly.
- **anyio 4.15.1 (2026-09-05): pytest plugin alternative.**
  - Mark tests with `@pytest.mark.anyio` or `pytestmark`, or set `anyio_mode = "auto"` (4.11+) or
    `--anyio-mode` (4.15.0).
  - The default `anyio_backend` fixture is **module-scoped and parametrized over every available backend**
    (asyncio, plus trio if installed). Override it with
    `@pytest.fixture def anyio_backend(): return "asyncio"`.
  - Use `("asyncio", {"use_uvloop": True})` for uvloop.
  - Fixtures and tests share one task, so contextvars propagate. The anyio docs say pytest-asyncio runs
    each async fixture's setup and teardown in a new task, which breaks contextvars, task groups and cancel
    scopes.
  - You cannot use anyio auto mode together with pytest-asyncio auto mode.
  - Sources: https://anyio.readthedocs.io/en/stable/testing.html and plugin source at tag 4.15.1.
  - Pick one plugin. For a discord.py (asyncio-only) bot, pytest-asyncio auto mode is the simpler choice;
    pick anyio if you rely on contextvars across fixture and test.
- **coverage 7.16.2 (2026-09-27).**
  - Since 7.9.1 (2025-06-13), **the "sysmon" (sys.monitoring) core is the default on 3.14+**, which lowers
    overhead. It silently falls back to ctrace when plugins, dynamic contexts or conflicting concurrency
    settings are configured.
  - It ships 3.15 wheels, and its classifiers include "Free Threading :: 3 - Stable".
- **pytest-cov 7.1.0 (2026-03-21).**
  - 7.0.0 (2025-09-09) **dropped subprocess measurement via a `.pth` file**; use coverage's
    `[run] patch = subprocess` instead. It requires coverage >= 7.10.6.
  - 7.1.0 made totals consistent across report types, which matters for `--cov-fail-under`.

---

## 6. Discord bot testing in Python

- **dpytest**:
  - PyPI 0.7.0 dates from **2023-06-19** and is marked "Development Status: 3 - Alpha", requiring
    `discord.py ~=2.3`.
  - The repo has commits on master through 2026-01-13 ("Update for discord.py 2.6, Python 3.11-3.14
    (#133)", 2025-12-12), but **none of that is released**.
  - It **does not support interactions, slash commands, views or modals**. Issue #125 has been open since
    2023-11-15; the maintainers said "no plans", and a contributor gave up because "it seemed pretty complex
    to simulate a webhook communication". Issue #92 (closed): "we will never support slash commands".
  - Verdict: **unsuitable** for an app-command-centric port of a JDA bot.
  - Sources: https://github.com/CraftSpider/dpytest , https://github.com/CraftSpider/dpytest/issues/125
- **What works in practice:**
  1. **Ports and adapters.** Keep the domain logic pure and typed. Define `typing.Protocol` ports for
     outbound effects, such as `class Replier(Protocol): async def reply(self, content: str, *, ephemeral:
     bool) -> None`, and back them with hand-written fakes that record calls. This is where most TDD tests
     should live, and it fits pyright strict because fakes type-check against the Protocol.
  2. **Thin discord.py adapters**, tested by calling `command.callback(cog, interaction, ...)` with a fake
     or `AsyncMock(spec=...)` interaction. Assert on the recorded `response.send_message` calls.
  3. **Payload-built real objects.** discord.py's own tests do this: `tests/test_app_commands_invoke.py`
     defines `MockCommandInteraction(discord.Interaction)` built from raw interaction payload dicts, plus a
     `MockTree(app_commands.CommandTree)` that runs the real argument parsing and transformers. Use this for
     a few integration tests of the command tree. Source:
     https://github.com/Rapptz/discord.py/blob/master/tests/test_app_commands_invoke.py
  4. Treat live-gateway smoke tests against a test guild as manual or nightly checks, not unit tests.

---

## 7. Git hooks

### Runners

- **pre-commit 4.6.2 (2026-08-10).**
  - 4.4.0 (2025-11-08) added `language: unsupported` and `unsupported_script` as aliases for `system` and
    `script`, which "will eventually be deprecated".
  - 4.5.0 (2025-11-22) added `pre-commit hazmat`.
  - 4.6.x fixed npm 11 and 12 node hooks.
  - **`language: pygrep` compiles the pattern as bytes** (`re.compile(args.pattern.encode())` in
    https://github.com/pre-commit/pre-commit/blob/v4.6.2/pre_commit/languages/pygrep.py ). This decides how
    to write a CJK regex; see below.
- **prek 0.5.5 (2026-10-05).** Source: https://github.com/j178/prek
  - It is a Rust single binary, "fully compatible" with `.pre-commit-config.yaml` and hook repos, and also
    accepts native `prek.toml`.
  - Built-in Rust hooks run under `repo: builtin`, including `deny-pattern` and `require-pattern`
    (since 0.4.11). It integrates with uv for Python hooks and has a monorepo workspace mode.
  - Not implemented: `hazmat`.
  - Maturity: it is still 0.x and the README says "pretty new", but CPython, Apache Airflow and FastAPI use
    it, the PyPI classifier says Production/Stable, and it has 8.5k stars.
  - Install: `uv tool install prek`, `uv add --dev prek`, or `brew install prek` (formula 0.5.5).
- **Verified: every hook below behaved identically under pre-commit 4.6.2 and prek 0.5.5.**

### Conventional-commit linters

| Tool | Latest | Hook | Notes |
|---|---|---|---|
| conventional-pre-commit | 4.4.0 (2026-02-18) | `id: conventional-pre-commit`, `stages: [commit-msg]`, `args: [--strict, --force-scope, --scopes a,b, feat, fix, ...]` | Light, no config file. `--strict` rejects `fixup!` and merge commits. **Verified: it accepts a conventional subject that contains CJK, so it does not enforce ASCII.** |
| commitizen | 4.19.2 (2026-10-07) | `id: commitizen` (commit-msg, `cz check --allow-abort --commit-msg-file`), `id: commitizen-branch` (pre-push, `--rev-range`) | Heavier: bumping and changelog generation. Configure under `[tool.commitizen]`. |
| gitlint | 0.19.1 (2023-03-10) | `gitlint` / `gitlint-ci` | **Unmaintained** (last commit 2023-09-02); avoid. |

### Rejecting non-ASCII commit messages

The commit-msg hook receives `.git/COMMIT_EDITMSG` **before** git strips comments. So it sees `#` comment
lines, which may be **localized**, such as a zh-TW git template, and with `git commit -v` it also sees the
diff below the scissors line.

- pygrep one-liner: `entry: '^(?!#).*[^\x00-\x7f]'`, `language: pygrep`, `stages: [commit-msg]`. It is
  simple, but **verified to give a false positive with `git commit -v`** when the staged diff contains
  non-ASCII.
- **Recommended**: a small script hook (verified correct in all three cases: plain, localized comments,
  and verbose diff):

```python
# scripts/check_commit_msg_ascii.py
"""Reject commit messages that contain non-ASCII characters.

Ignores git comment lines and everything below the `git commit -v` scissors line.
"""

import sys
from pathlib import Path

SCISSORS = "------------------------ >8 ------------------------"


def main(argv: list[str]) -> int:
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8", errors="replace")
    bad: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            if SCISSORS in line:
                break
            continue
        if not line.isascii():
            bad.append((lineno, line))
    for lineno, line in bad:
        print(f"{path}:{lineno}: non-ASCII character in commit message: {line!r}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

This assumes `core.commentChar` is the default `#`.

CI backstop, because hooks can be skipped with `--no-verify` (verified):

```bash
git log --format='%H %B' "${BASE_SHA}..HEAD" | python3 -I -c '
import sys
bad = [l for l in sys.stdin.buffer.read().decode("utf-8", "replace").splitlines() if not l.isascii()]
if bad:
    print(*bad, sep="\n", file=sys.stderr)
sys.exit(1 if bad else 0)'
```

### Rejecting CJK characters in `*.py`

- Because pygrep compiles **bytes** regexes, a pattern written with `\u4e00`-style escapes **crashes**
  ("bad escape \u at position 1", verified). Literal CJK characters inside a character class would be
  split into individual UTF-8 bytes, which is also wrong. **Match UTF-8 byte sequences instead (verified).**
- Coverage of the verified pattern:
  - **Flagged**: CJK ideographs (U+4E00-9FFF and Ext A), CJK punctuation such as the ideographic full stop,
    kana, bopomofo, fullwidth forms such as the fullwidth comma (U+FF0C), CJK compatibility ideographs, and
    U+20000+ supplementary ideographs.
  - **Allowed**: Latin accents, emoji, and the em dash.
  - **Excluded**: Hangul syllables. Add `\xea[\xb0-\xbf][\x80-\xbf]|[\xeb\xec][\x80-\xbf]{2}|\xed[\x80-\x9e][\x80-\xbf]`
    if you need them.

```yaml
      - id: no-cjk-in-python
        name: no CJK characters in Python files
        language: pygrep
        types: [python]
        # bytes regex: U+3000-U+9FFF | U+F900-U+FAFF, U+FF00-U+FFFF | U+20000-U+3FFFF
        entry: '[\xe3-\xe9][\x80-\xbf]{2}|\xef[\xa4-\xab\xbc-\xbf][\x80-\xbf]|\xf0[\xa0-\xbf][\x80-\xbf]{2}'
```

- Simpler policy, if you want English-only code: `entry: '[^\x00-\x7f]'` rejects any non-ASCII in `*.py`.
- prek-only native alternative (verified; fancy-regex, which supports Unicode classes). Upstream pre-commit
  cannot read this:

```yaml
  - repo: builtin
    hooks:
      - id: deny-pattern
        types: [python]
        args: ['[\p{Han}\p{Hiragana}\p{Katakana}\p{Bopomofo}\x{3000}-\x{303F}\x{FF00}-\x{FFEF}]']
```

### Full hook config (validated with `pre-commit validate-config`; run under both runners)

```yaml
default_install_hook_types: [pre-commit, commit-msg]
default_stages: [pre-commit]
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.10
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.4.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [--strict]
  - repo: local
    hooks:
      - id: no-cjk-in-python
        name: no CJK characters in Python files
        language: pygrep
        types: [python]
        entry: '[\xe3-\xe9][\x80-\xbf]{2}|\xef[\xa4-\xab\xbc-\xbf][\x80-\xbf]|\xf0[\xa0-\xbf][\x80-\xbf]{2}'
      - id: commit-msg-ascii
        name: commit message must be ASCII
        language: python
        stages: [commit-msg]
        entry: python scripts/check_commit_msg_ascii.py
      - id: pyright
        name: pyright (strict)
        language: unsupported        # alias of system (pre-commit >= 4.4, prek); needs uv on PATH
        entry: uv run --locked pyright
        pass_filenames: false
        types: [python]
      # + the two openspec hooks from section 1.7
```

Install with `pre-commit install` or `prek install`. Both honor `default_install_hook_types`, so they install
the pre-commit and commit-msg shims.

---

## 8. Claude Code

The local version is 2.1.294. Docs pages are undated, fetched 2026-10-08:
https://code.claude.com/docs/en/hooks , /skills , /memory , /discover-plugins , /plugins/cli-reference .

### 8.1 Hooks suitable for quality gates

- **Events**: SessionStart, Setup, UserPromptSubmit, UserPromptExpansion, **PreToolUse**, PermissionRequest,
  PermissionDenied, **PostToolUse**, PostToolUseFailure, **PostToolBatch**, Notification, MessageDisplay,
  SubagentStart, **SubagentStop**, TaskCreated, **TaskCompleted**, **Stop**, StopFailure, TeammateIdle,
  InstructionsLoaded, ConfigChange, CwdChanged, DirectoryAdded, FileChanged, WorktreeCreate, WorktreeRemove,
  PreCompact, PostCompact, PreModelSwitch, PostModelSwitch, Elicitation, ElicitationResult, SessionEnd.
- **Exit code 2 is the blocking code.** Exit 1 is a non-blocking error on most events.

  | Event | Behavior |
  |---|---|
  | PreToolUse | Exit 2 blocks the tool call. Or use JSON `hookSpecificOutput.permissionDecision: "deny"`. |
  | PostToolUse | Exit 2 "Shows stderr to Claude; the tool already ran". Or use JSON `decision: "block"` + `reason`, `additionalContext`, or `updatedToolOutput`. |
  | Stop / SubagentStop | Exit 2 or `decision: "block"` keeps Claude working. Input includes `stop_hook_active` ("true when Claude Code is already continuing as a result of a stop hook"). There is an **8-consecutive-continuation cap**, configurable via `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. |
  | TaskCompleted | Exit 2 prevents completion. The docs' example runs the test suite. |
  | PostToolBatch | Fires once per batch of parallel tool calls. |

- **Config locations:**
  - `~/.claude/settings.json` (user)
  - `.claude/settings.json` (project, committed)
  - `.claude/settings.local.json`
  - managed policy
  - plugin `hooks/hooks.json`
  - skill or agent frontmatter `hooks`
- **Matcher** is an exact name or a `|` list (`Edit|Write`); anything else is treated as a regex
  (`mcp__server__.*`). The optional `if` field takes permission-rule syntax, such as `"Bash(git *)"`.
- **Handler types**: `command`, `http`, `mcp_tool`, `prompt`, and `agent` (experimental).
- **Default timeouts**: 600 s for command, http and mcp_tool; 30 s for prompt; 60 s for agent.
- `"async": true` (command hooks only) runs a hook in the background. It cannot block; its output is
  delivered on the next turn.
- `${CLAUDE_PROJECT_DIR}` is the project root. For `Write`/`Edit`, `tool_input.file_path` is always an
  absolute path.
- The skills docs say: when "Claude skipped a rule that must hold every time: move the rule into a hook".
  Hooks are the right place for TDD gates.

Verified hook scripts. I simulated the stdin JSON against a uv demo project: a fixable lint returns 0 after
auto-fix, an unfixable F821 returns 2 with ruff output on stderr, the Stop hook returns 2 while pytest or
ruff fail and 0 when clean, and the hooks ignore non-`.py` files.

```bash
#!/usr/bin/env bash
# .claude/hooks/py-file-gate.sh  -- PostToolUse(Edit|Write): lint-fix + format the touched .py file
set -uo pipefail
file="$(jq -r '.tool_input.file_path // empty')"
[[ "${file}" == *.py ]] || exit 0
cd "${CLAUDE_PROJECT_DIR}" || exit 0
out="$(uv run --locked --quiet ruff check --fix --quiet "${file}" 2>&1)"
rc=$?
uv run --locked --quiet ruff format --quiet "${file}" >/dev/null 2>&1
if (( rc != 0 )); then
  printf 'ruff check failed for %s:\n%s\n' "${file}" "${out}" >&2
  exit 2
fi
exit 0
```

```bash
#!/usr/bin/env bash
# .claude/hooks/py-stop-gate.sh  -- Stop: refuse to finish while gates fail
set -uo pipefail
input="$(cat)"
cd "${CLAUDE_PROJECT_DIR}" || exit 0
[[ -n "$(git status --porcelain -- '*.py' 'pyproject.toml' 'uv.lock')" ]] || exit 0
failures=()
uv run --locked --quiet ruff format --check --quiet >/dev/null 2>&1 || failures+=("ruff format --check")
uv run --locked --quiet ruff check --quiet >/dev/null 2>&1 || failures+=("ruff check")
uv run --locked --quiet pyright >/dev/null 2>&1 || failures+=("pyright (strict)")
uv run --locked --quiet pytest -q -x >/dev/null 2>&1 || failures+=("pytest")
(( ${#failures[@]} == 0 )) && exit 0
active="$(jq -r '.stop_hook_active // false' <<<"${input}")"
printf 'Quality gates failing: %s. Run them, fix the causes, then finish. (stop_hook_active=%s)\n' "${failures[*]}" "${active}" >&2
exit 2
```

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Edit|Write",
        "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/py-file-gate.sh", "timeout": 120 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/py-stop-gate.sh", "timeout": 600 } ] }
    ]
  }
}
```

Notes:

- Running pyright on every edit is slow, so keep it in Stop or in an `async` PostToolUse hook.
- The Stop gate relies on the built-in 8-continuation cap to avoid infinite loops. If you prefer a softer
  gate, exit 0 when `stop_hook_active` is true.
- Optionally add a PreToolUse `Bash(git commit*)` hook that denies `--no-verify`.

### 8.2 Skills

- **Locations:**
  - Project: `.claude/skills/<name>/SKILL.md` (commit it). Claude Code also loads project skills from
    parent directories up to the repo root.
  - Personal: `~/.claude/skills/<name>/SKILL.md`.
  - Nested: `<subdir>/.claude/skills/...` loads on first touch of that subdirectory.
  - Plugin skills are namespaced `/plugin:skill`.
  - Precedence: enterprise > personal > project.
- **Invocation**: `/<name>`. Claude also auto-invokes a skill based on its `description`.
- **Commands vs skills**: "Custom commands have been merged into skills". `.claude/commands/x.md` and
  `.claude/skills/x/SKILL.md` both create `/x`, and the skill wins on a name clash. OpenSpec's
  `/opsx:propose` command and `openspec-propose` skill have different names, so both appear.
- **Frontmatter**: name, description, when_to_use, argument-hint, arguments, disable-model-invocation,
  user-invocable, allowed-tools, disallowed-tools, model, effort, context (`fork`), agent, background,
  hooks, paths, shell. `metadata`, `license` and `compatibility` are accepted but ignored.
- `.agents/skills` is **not mentioned** in the Claude Code docs, so treat it as unsupported (unconfirmed).

### 8.3 AGENTS.md vs CLAUDE.md

- **Claude Code reads `AGENTS.md` natively since v2.1.277** (npm publish 2026-09-18). Default setting
  `claude-md-or-agents-md`:

  | Repo contents | What Claude reads |
  |---|---|
  | AGENTS.md and no CLAUDE.md / .claude/CLAUDE.md / CLAUDE.local.md in the working directory or above | AGENTS.md |
  | AGENTS.md and a CLAUDE.md | **CLAUDE.md only** |
  | A CLAUDE.md that imports `@AGENTS.md` | Both, with no duplication |

- `~/.claude/CLAUDE.md`, the managed CLAUDE.md and `.claude/rules/` do not count for that check; they load
  alongside AGENTS.md.
- Other settings values: `claude-md-and-agents-md`, `claude-md`, `managed-only`. Set them via `/config` ->
  Project instructions, or via `pluginConfigs["cc-plugin-agents-md@builtin"].options.instructionFiles` in
  user or managed settings (the ID was `agents-md@builtin` before v2.1.285).
- Some sessions cannot read AGENTS.md: older versions, the built-in plugin disabled, or the first session
  after an upgrade.
- **Recommended way to share one file**: a `CLAUDE.md` containing `@AGENTS.md` plus Claude-only lines below
  it. This works in every session and the import is never read twice.
  - A symlink `ln -s AGENTS.md CLAUDE.md` also works, but Edit/Write refuse to write through a symlink,
    and on Windows clones it becomes a one-line file.
  - Imports use `@path` syntax with a maximum depth of 4 hops; imports outside the repo need one-time
    approval.
  - Live evidence: this Claude Code 2.1.294 session loaded `/Users/xinshou/AGENTS.md` (a parent directory)
    as project instructions. So native AGENTS.md loading works, and there is currently no CLAUDE.md in the
    repo or its parents (`~/.claude/CLAUDE.md` does not count).
  - **If the port adds a repo `CLAUDE.md`, every AGENTS.md, including `/Users/xinshou/AGENTS.md`, stops
    loading** unless that CLAUDE.md contains `@AGENTS.md` or the setting is `claude-md-and-agents-md`.

### 8.4 Removing the "superpowers" plugin

- **Observed on this machine (read-only check)**: `~/.claude/plugins/installed_plugins.json` has **no
  superpowers entry**, and no `enabledPlugins` entry exists in user or project settings. So it already
  appears to be uninstalled. The leftovers are:
  - `~/.claude/plugins/cache/superpowers-marketplace/superpowers/8560ad09fb77` (dated 2026-04-05)
  - an empty `~/.claude/plugins/data/superpowers-inline/` (dated 2026-04-13)
  - `superpowers-marketplace` is not in `known_marketplaces.json`.
- Commands, if it shows up in `claude plugin list`. Its README installs it as either
  `superpowers@claude-plugins-official` or `superpowers@superpowers-marketplace`.
  - Shell:
    - `claude plugin list`
    - `claude plugin uninstall superpowers@superpowers-marketplace` (aliases `remove`, `rm`). Add
      `--scope project|local` if it was installed at that scope (the default is user). `--keep-data`
      keeps `~/.claude/plugins/data/<id>/`.
    - `claude plugin marketplace remove superpowers-marketplace` uninstalls every plugin from that
      marketplace and deletes its cache.
    - `claude plugin disable superpowers@superpowers-marketplace` turns it off without uninstalling.
  - In a session:
    - `/plugin uninstall superpowers@superpowers-marketplace`, or
    - `/plugin` -> Tab to **Installed** -> select it -> **Uninstall**. If the project settings enable it,
      press `y` to disable it for you or `u` to uninstall it for everyone.
    - Then run `/reload-plugins`.
  - The stale cache and data directories above are not covered by any documented CLI command. Deleting
    them by hand (`rm -rf`) is a manual step, so ask the user first.

---

## 9. Not confirmed / caveats

- Whether Claude Code reads `.agents/skills/` (not in the docs).
- The exact pydantic limitations with PEP 649 on 3.14 (the release article only says "limited support").
- Python 3.14.8 date: python.org says 2026-09-30 and PEP 745 says 2026-10-01 (timezone/announcement
  difference).
- OpenSpec docs (supported-tools.md, cli.md) lag the 1.14.1 CLI's tool list. I trusted
  `openspec init --help`.
- The ruff `runtime-evaluated-decorators` exemption was tested only for `discord.app_commands.command`.
- prek `deny-pattern` uses fancy-regex in bytes mode. `\p{Han}` worked in the test, but this was not checked
  against every Unicode class.

## 10. Housekeeping

- All runs used scratchpad caches (`npm_config_cache`, `UV_CACHE_DIR`, `PRE_COMMIT_HOME`, `PREK_HOME`,
  `XDG_CONFIG_HOME`, `PYRIGHT_PYTHON_CACHE_DIR`) and wrote nothing to `$HOME`. The scratch repos are in
  `scratchpad/tmp/{openspec-claude-demo,openspec-codex-demo,hooks-demo,gate-demo,uv-init-demo,ruff-tc-probe}`.
- A pre-existing `~/.config/openspec/config.json` (created 2026-10-08 19:35:13, before this run, holding a
  telemetry anonymousId) shows that someone ran OpenSpec earlier without the XDG override.
- Another agent is writing into the same scratchpad (`tmp/pypi/`, `inventory/`, `core*.txt`). Those are not
  my files.
