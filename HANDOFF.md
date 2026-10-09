# HANDOFF: xincord Phase 2 (implementation)

Written 2026-10-10 by the session that did Phase 0 (reading and verification) and Phase 1
(analysis and decisions). Read this file first, then `docs/porting/decisions.md`. The decisions are
accepted and binding; do not re-open them unless you find a serious problem, and then ask the owner.

Talk to the owner in Traditional Chinese. Everything written into the repository is English.

## 1. Goal

Port XsDiscordBotKt (Kotlin + JDA 6, about 20.4k lines: Core 5.9k, 21 plugin modules 13.9k) to
Python 3.14 + uv as **xincord**, managing specs with OpenSpec and building everything test-first,
starting with Core. Motivation: easier maintenance and faster iteration.

## 2. Where things are

| What | Where |
|---|---|
| This project (no git repository yet) | `/Users/xinshou/IdeaProjects/xincord` |
| Remote (private, empty) | `git@github.com:xinshoutw/xincord.git` |
| Kotlin baseline | `/Users/xinshou/IdeaProjects/XsDiscordBotKt` at `3a59607` (branch `main`) |
| Accepted decisions | `docs/porting/decisions.md`; raw submission in `docs/porting/submissions/` |
| Per-plugin inventories (acceptance-criteria source, with Kotlin `file:line`) | `docs/porting/analysis/inventory/<Plugin>.md` |
| BasicCalculator golden data (3,155 cases from the real Kotlin evaluator) | `docs/porting/analysis/inventory/fixtures/*.jsonl` |
| Version research (2026-10-08), v4 branch analysis, Core brief | `docs/porting/analysis/research/*.md` |
| Kotlin v4 design spec (summarize only, A3) | `XsDiscordBotKt/docs/specs/2026-04-07-v4-core-refactor-design.md` |
| Local data copy for a future migration test (B11, deferred) | `XsDiscordBotKt/Server/` (the GitHub source wins on conflicts) |
| Decision page | https://claude.ai/artifact/E6CCEYRv6XA7nKc5rYCwDv |

Core was read in full by the previous session; the plugin inventories were written by subagents
that read every source and resource file. The inventories quote real Discord IDs that are already
public in the old repository.

## 3. Rules (owner's global rules plus the decisions)

**Language**
- Replies to the owner: Traditional Chinese, direct and concise, no flattery.
- Code, comments, docstrings, tests, docs, OpenSpec files, commit messages: English.
- Zero CJK characters in `*.py`, tests included (A5). Assert Chinese output through lang keys,
  YAML fixtures under `tests/fixtures/`, or `\u` escapes. Lang YAML and fixture YAML are exempt.
- Commit messages are ASCII only (A5). Refer to lang keys instead of quoting UI text.

**Commits**
- Conventional Commits: `type(scope): subject`, optional bullet body. Types: feat, fix, test,
  refactor, docs, build, ci, chore. Scopes: `core`, `plugin-<name>` (for example
  `plugin-autorole`), `build`, `ci`, `docs`.
- GPG-sign every commit and tag (`git commit -S`). The owner's signing key is configured globally.
- Never add `Co-Authored-By`, Claude session lines or any tool attribution, in commits or PRs.
- Small and frequent. Every commit passes all gates.

**TDD (A11: xfail-first)**
1. Write the test for one behavior. Run it and confirm it fails for the expected reason.
2. Commit it marked `@pytest.mark.xfail(strict=True, reason="<requirement name>")`; the gates
   stay green.
3. Implement the behavior, remove the marker, run the gates, commit.
- No product code without a failing test first. Scaffolding gets a minimal smoke test.
- Before claiming anything is done, run ruff, pyright and pytest and show the output.

**OpenSpec**
- Every scenario of every requirement maps to at least one pytest test whose name or marker
  names the requirement.
- Requirements ported from Kotlin cite `XsDiscordBotKt@3a59607:<path>:<line>` in the change
  design or the test docstring (A2).
- Keep one active change at a time. Archive right after implementation and verification, then run
  `openspec validate --all --strict`. Known archive problems: header-matched requirements break
  easily (#2033), parallel changes to one requirement drift (#1387), `archive --yes` ignores
  unchecked tasks (#1652), text outside requirement blocks is dropped (#2053), and `apply` never
  runs project checks (#1983).

**v3 defects (A12)**
- Fix them; never port a known bug. Write "v3 behaved differently: ..." in the change design and
  in `docs/porting-guide.md`.
- List every user-visible change (copy, commands, interaction flow) for the owner to review.

**Pushing (A1)**
- Normal pushes of xincord `main` to `origin` are pre-authorized.
- Ask first for: force push, deleting branches, tags, releases, PyPI publishing, repository
  settings, and anything touching the XsDiscordBotKt remote.
- Owner's global rule still applies: list user-visible copy changes for review before pushing
  them.

**Files and repository**
- Do **not** create LICENSE. The owner adds it (AGPLv3). README states the license is GNU AGPL v3.
- No CLAUDE.md in this repository (A7). Project rules go in `AGENTS.md`, which Claude Code reads
  natively when no CLAUDE.md exists in the folder or its parents.
- Never commit real IDs, bank account numbers or tokens as defaults. In the Kotlin repo the
  SimpleCommand templates, the AutoRole default config and NtustManager's code contain real
  values; use example values instead.

**Shell and tooling**
- The shell is zsh: quote variables as `"${VAR}"`; build JSON with `jq -n --arg`.
- Pass non-interactive flags, or redirect stdin from `/dev/null`.
- Check that "read" commands have no side effects before running them.
- Cross-review with a subagent has not been done for this project yet; ask the owner before doing
  one on a large change.

## 4. Architecture at a glance

- **Packages (B2, B18, resolution 2):** a uv workspace with two distributions.
  - `xincord` (core). Module `xincord.core`: `src/xincord/core/__init__.py`, no
    `src/xincord/__init__.py`, `[tool.uv.build-backend] module-name = "xincord.core"`. Publishable
    to PyPI (the name was unclaimed on 2026-10-08), but publishing needs the owner's approval.
  - `xincord-plugins`. Module `xincord.plugins`: `src/xincord/plugins/__init__.py` plus one
    subpackage per plugin, `module-name = "xincord.plugins"`. Plugins are registered through an
    entry-point group (for example `xincord.plugins`), so third-party distributions can add their
    own.
  - The dotted `module-name` support for PEP 420 namespaces was checked against the uv 0.12 docs.
    The core API becomes public: keep it small and version it with semver.
- **Plugin contract (B3):** one discord.py extension + Cog per plugin; metadata as module
  constants (name, version, dependencies, required intents, legacy component prefix);
  `graphlib.TopologicalSorter` for the load order; a failing plugin disables only itself; config
  and lang live under `plugins/<Name>/`; hot reload via `reload_extension`, reloading dependents
  too.
- **Intents (B4):** aggregated before connecting from the enabled plugins' declarations. A hot
  reload that needs new intents is refused with a "restart required" message.
- **Commands (B5):** the command tree defers ephemerally before the handler runs; commands that
  open a modal opt out through `extras`. Autocomplete is routed by command name. Sync only when the
  hash of the command payload changes. Keep the guild/global split.
- **Config (B6):** a new schema (pydantic v2 + YAML), plus a script that migrates the v3 files
  (core `config.yaml` and each `plugins/<Name>/config.yaml`). Unknown keys warn; an invalid value
  disables only that plugin. Move hard-coded values into config, for example NtustCourse's semester
  and go-live gate, and NtustManager's guild and channel IDs.
- **i18n (B7):** keep `lang/<Discord locale>/register.yaml`, `message/*.yml` and `modal/*.yml`.
  Command names go through `app_commands.Translator`. Fall back to the default locale per key, and
  validate key sets at load.
- **Templates and placeholders (B10):** implement the v1 format used today (content, embeds,
  components with the `!ButtonsComponent`, `!StringSelectMenu` and `!EntitySelectMenu` YAML tags,
  `uid`, `model_key`) and Components V2. Placeholders are a single level of `%key%`: no recursion,
  user input is never parsed, and every render gets a fresh context.
- **Component IDs (B9):** a new versioned format (100 characters max). Keep a permanent decoder
  for the v3 format: `{prefix}{a..z}:{value};...`, short keys assigned in each plugin's field
  declaration order, longs in lowercase hex. On an interaction with a legacy ID, handle it, then
  edit that message so its components carry new-format IDs. Never mass re-send panels. Pin every
  plugin's legacy field order with golden tests taken from the Kotlin source.
- **Storage (B8):** SQLite through stdlib `sqlite3` + `asyncio.to_thread`. A key-value document
  table, plus per-plugin tables where queries need them. Every write is awaited, with per-guild
  locks. Tests use `:memory:`.
- **Data migration (B11):** deferred until after parity, and built only if needed (F1 note).
- **Removed:** the API plugins (B12; GoogleSheetAPI and Economy's dead `SheetImpl` path go too)
  and the Web-Dashboard (B13).
- **Runtime (B15, B19, C3):**
  - Signals: SIGTERM and SIGINT stop gracefully, SIGHUP reloads.
  - Owner-only `/xincord reload [plugin]` and a prompt_toolkit interactive console.
  - argparse CLI: `--token`, `--level`, `--no-online`, `--force-renew-lang-resources`. There is no
    version check.
  - `AllowedMentions` defaults to users and the replied user only.
  - `/bot-info` shows a configurable source link.
  - Port Core's built-ins too: the status changer, which also fixes the STREAMING parse bug, and
    the console logger that forwards interactions to channels.
- **Music (B14):** a Lavalink 4.2+ node + lavalink.py, run with docker compose.
- **Deployment (B16):**
  - Version: one semver, `0.x` until cutover, `1.0.0` at cutover.
  - Host: a Docker image (arm64 at least) with docker compose on the owner's macOS M4 Pro, using
    OrbStack or Docker Desktop.
  - Storage: keep SQLite in a named volume.
  - Console: the service needs `stdin_open: true` and `tty: true` (`docker compose attach`).
- **Testing (B17):** pure logic without discord.py; Cogs and Views depend on narrow Protocols with
  hand-written fakes; pytest + pytest-asyncio in auto mode; a manual smoke checklist per plugin for
  a test guild. dpytest is unusable (no slash commands or interactions).
- **Cutover (C2):** switch once every in-scope plugin's scenarios have passing tests.

## 5. Next steps, in order

1. **Toolchain.**
   - The local uv is 0.10.8. Ask the owner to upgrade it to at least 0.12.23, which uses a `src/`
     layout and `uv_build` by default.
   - Node v26.5 is installed. Run OpenSpec 1.14.1 through
     `npx --yes @fission-ai/openspec@1.14.1`, or ask before installing it globally.
   - Disable telemetry: `openspec config set telemetry.enabled false` or `OPENSPEC_TELEMETRY=0`.
2. **Repository.** `git init -b main`, then add `origin`. Do not touch LICENSE.
3. **OpenSpec.** `openspec init --tools claude`. Fill `openspec/config.yaml` with the project
   context: stack, rules, and a pointer to `docs/porting/decisions.md`.
4. **Change 1: project skeleton** (build/ci/docs). Contents:
   - uv workspace with the two packages from section 4; `requires-python = ">=3.14"`.
   - **Ruff:** `select = ["ALL"]` with documented ignores. Also set
     `lint.flake8-type-checking.runtime-evaluated-decorators` for discord.py command decorators.
   - **Pyright:** strict on `src` and `tests`.
   - **pytest 9:** use the `[tool.pytest]` table with `strict = true` and `xfail_strict = true`;
     pytest-asyncio `asyncio_mode = "auto"`; branch coverage `fail_under = 85`.
   - **`.pre-commit-config.yaml`, run with prek:**
     - ruff check and ruff format, pyright.
     - A CJK check on `*.py` using the UTF-8 byte regex in section 7.
     - A commit-msg script enforcing ASCII and Conventional Commits.
     - pytest on pre-push.
   - **`.claude/settings.json` hooks:** PostToolUse runs ruff format and fix on edited `.py` files;
     Stop runs the full gate and blocks until it passes.
   - **`.github/workflows/ci.yml`:**
     - `astral-sh/setup-uv` pinned to v10.2.0 by commit `c18668ad3cf93ea998bef934396af7bb5c839dc7`
       (there is no floating `@v10` tag).
     - `uv sync --locked`, ruff, pyright, pytest with coverage, `openspec validate --all --strict`.
   - **Docs and skills:**
     - `AGENTS.md`: the rules from section 3.
     - `README.md`: what xincord is, plus the AGPLv3 note.
     - `docs/porting-guide.md`: a Kotlin/JDA to Python/discord.py mapping table, the v4 design
       intents still worth keeping, and the pitfalls in section 7.
     - `.claude/skills/port-plugin/SKILL.md`: the per-plugin checklist (inventory, spec, xfail
       test, implementation, porting-guide update, archive).
   - **Smoke tests:** both packages import; the entry-point group resolves; the CJK checker and the
     commit-msg checker reject bad samples.
   - Then archive the change.
5. **Core changes**, one capability per change, roughly in this order:
   1. config: new schema plus the v3 migration script.
   2. storage: the SQLite key-value store.
   3. i18n: loaders and Translator.
   4. placeholders.
   5. templates: v1 and Components V2.
   6. component-ids: the new format, the legacy decoder and the lazy upgrade.
   7. plugin-loading: entry points, ordering, isolation, intents.
   8. command-tree: defer opt-out, autocomplete routing, hash sync.
   9. runtime: client setup, CLI, signals, console, `/xincord reload`, status changer, interaction
      forwarding.
   10. container: Dockerfile and compose.
6. **Plugins**, in C1 order: _Example (as the new template), BasicCalculator, AutoRole, BotInfo,
   SimpleCommand, WelcomeByeGuild, IntervalPusher, Feedbacker, Economy, DynamicVoiceChannel,
   VoiceLogger, ChatLogger, Giveaway, Ticket, TicketAddons, NtustManager, NtustCourse,
   MusicPlayer.
   - Update `docs/porting-guide.md` after each plugin.
   - The first two or three plugins calibrate the guide.
   - The later ones may run as parallel workflows, but only if the owner asks; they follow the
     same rules.

## 6. Open items

1. **Production version (F1)** is unknown. It matters only if a data migration is ever needed.
2. **New component-ID format:** design it in the component-ids change. It must fit 100 characters,
   carry a version marker, and coexist with the permanent legacy decoder.
3. **Lavalink image:** verify the arm64 Lavalink image and the compose details when MusicPlayer
   starts. The bot does not need `davey`, because Lavalink handles DAVE.
4. **VoiceLogger status events:** voice-channel status events (audit types 192/193) may need raw
   gateway handling in discord.py; verify when that plugin starts.
5. **Owner actions, not ours:**
   - Set `XSBOT_DASHBOARD_ENABLED=false` on the running Kotlin bot. Its dashboard has no auth, is
     exposed to DNS rebinding, and may allow path traversal to the token file (unverified).
   - Decide whether to push the one unpushed commit `3a59607` in XsDiscordBotKt.
   - Delete the leftover Superpowers cache directories if wanted.
6. **Analysis files:** confirm with the owner whether `docs/porting/analysis/` is committed as
   reference material. The inventories quote IDs that are already public in the old repo.

## 7. Verified facts and pitfalls (checked 2026-10-08)

**Versions**
- Runtime: Python 3.14.8 latest (local: Homebrew 3.14.6, uv-managed 3.14.3).
- Tooling: uv 0.12.23, ruff 0.16.10 (413 default rules), pyright 1.1.414, ty 0.0.85 (beta; never a
  gate), pytest 9.1.1, pytest-asyncio 1.4.0, coverage 7.16.2, pytest-cov 7.1.0, prek 0.5.5,
  pre-commit 4.6.2, OpenSpec 1.14.1 (Node >= 20.19).
- discord.py 2.7.1:
  - aiohttp < 4; `audioop-lts` on Python 3.13+.
  - `[voice]` adds PyNaCl and `davey`.
  - Components V2 since 2.6; DAVE since 2.7.
  - Its PyPI classifiers stop at 3.12, but it runs on 3.14.
- Libraries: pydantic 2.13.5 (cp314 wheels), PyYAML 6.0.3 (cp314 wheels), prompt_toolkit 3.0.53.
- Music: Lavalink 4.2.2 (DAVE since 4.2.0, Java 17+), youtube-source 1.18.2, lavalink.py 5.11.1.
- Discord rejects non-DAVE voice connections outside stage channels with close code 4017 since
  2026-03-02.

**Pitfalls**
- **discord.py decorators evaluate annotations at import** (PEP 649/749). Never move command
  parameter types under `TYPE_CHECKING`; ruff's TC rules would do exactly that unless
  `runtime-evaluated-decorators` is set.
- **Deprecation warnings:** discord.py 2.7.1 calls `asyncio.iscoroutinefunction` (deprecated), so
  add a `filterwarnings` ignore when warnings are errors.
- **CJK check:** pre-commit/prek `pygrep` compiles patterns as bytes, so `\u` escapes crash it. Use
  `'[\xe3-\xe9][\x80-\xbf]{2}|\xef[\xa4-\xab\xbc-\xbf][\x80-\xbf]|\xf0[\xa0-\xbf][\x80-\xbf]{2}'`.
- **Commit messages:**
  - conventional-pre-commit accepts CJK subjects, so a small script is required. It must skip `#`
    comment lines and the `git commit -v` diff.
  - `openspec archive <change> --yes` is needed when there is no terminal.
- **Member removal:** `on_member_remove` only fires for cached members; use `on_raw_member_remove`.
- **Channel overwrites:** discord.py `create_text_channel(overwrites=...)` does not copy the
  category's overwrites the way JDA does, so merge them manually (Ticket).
- **IntervalPusher:**
  - `tasks.loop` schedules from each start, not after each completion as Kotlin did.
  - discord.py has no REST ping: time `GET /users/@me` to keep `%ping%`.
- **BasicCalculator:**
  - Python `decimal` defaults to 28 digits, so use `Fraction` or exact decimal arithmetic.
  - The golden files decide; read its inventory before porting.
- **Do not reproduce these v3 behaviors:**
  - Loading plugins in reverse dependency order.
  - Non-atomic JSON writes that silently reset corrupt files.
  - Recursive placeholder expansion.
  - Shared mutable placeholder caches.
  - `asTextChannel()` failures in threads, voice chat and announcement channels.
  - Allow-all mentions.
- **Kotlin lookup keys:** `StringLocalizer` uses Kotlin camelCase property paths; Python uses the
  YAML keys directly.
