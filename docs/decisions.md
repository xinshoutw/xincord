# Decisions

Status: **accepted**. The owner made these on 2026-10-10 and changed some of them up to
2026-10-12; this page holds the current state. Do not re-open a decision without asking the owner.
Code and docs cite the IDs, which stay stable: a retired decision leaves its number unused.

Markers: **[rec]** the owner followed Claude's recommendation; **[owner]** the owner's own choice.

## A. Repository and process

- **A1 Branching and pushing** [owner]: commit directly on `main` and push it; there is no PR
  flow (the owner's choice of 2026-10-12). Normal pushes to `main` are pre-authorized.
  Ask first for force pushes, deleting branches, tags, releases, PyPI publishing and repository
  settings.
- **A4 Documentation language** [rec]: English everywhere (OpenSpec specs and designs, README,
  AGENTS.md, docs); the owner reads replies in Traditional Chinese.
- **A5 CJK and ASCII boundaries** [rec]: zero CJK in `*.py`, tests included. Tests assert through
  lang keys, YAML fixtures under `tests/fixtures/`, or `chr(...)`. Lang YAML and test fixture YAML
  are exempt. Commit messages are ASCII only; refer to lang keys instead of quoting UI text.
- **A6 Docstrings** [rec]: Google-style docstrings for the public core API only; comments explain
  why; ruff `D` rules for the core only; test docstrings name the requirement they cover.
- **A7 Rules** [rec + owner]: project rules live in `AGENTS.md`. **No CLAUDE.md**: Claude Code
  reads AGENTS.md when no CLAUDE.md exists in the folder or its parents.
- **A8 Quality gates** [rec]: ruff `select = ["ALL"]` with documented ignores and
  `runtime-evaluated-decorators` for discord.py; pyright strict on `src` and `tests`; branch
  coverage of at least 85%; prek runs `.pre-commit-config.yaml` (ruff check, ruff format, pyright,
  the CJK check, ASCII Conventional Commits; the gate on pre-push); Claude Code hooks (PostToolUse:
  ruff on edited `.py`; Stop: the gate); GitHub Actions with pinned actions, `uv sync --locked`,
  `openspec validate --all --strict` and an image build. Dependabot opens security updates only;
  Renovate opens version updates as `build:` commits and automerges patch updates and lock-file
  maintenance after CI passes, while minor and major updates wait for the owner. The repository has
  secret scanning with push protection, private vulnerability reporting, CodeQL's default setup and
  a ruleset that keeps `main` from force pushes and deletion.
- **A9 Name and license** [rec]: `xincord`, `AGPL-3.0-or-later`. The owner creates LICENSE; do not
  generate it.
- **A10 OpenSpec** [rec]: initialized with `--tools claude` only; telemetry off; the pinned CLI
  runs through npx.
- **A11 TDD record** [owner]: **xfail-first**. Commit the new test marked
  `@pytest.mark.xfail(strict=True)` (the gate stays green), then a second commit that implements
  the behavior and removes the marker. `xfail_strict = true`.

## B. Architecture

- **B1 Discord library** [rec]: discord.py.
- **B2 Distributions** [owner]: `xincord` (the core, import `xincord.core`) for PyPI, and
  `xincord-plugins` (the bundled plugins, import `xincord.plugins.<snake_name>`, registered through
  the `xincord.plugins` entry-point group). `xincord` is a namespace package without
  `__init__.py`; `xincord.plugins` is a regular package, and third-party plugins register through
  the entry-point group under their own top-level package. The core API is public: keep it small
  and version it with semver (`docs/plugin-api.md`). `xincord-plugins` requires its own release of
  `xincord`.
- **B3 Plugin contract** [rec]: one discord.py extension and Cog per plugin; metadata as module
  constants; stdlib `graphlib` orders by dependency; a failing plugin disables only itself; config
  and lang stay under `plugins/<Name>/`; hot reload via `reload_extension`, reloading dependents
  too.
- **B4 Intents** [rec]: aggregated from the enabled plugins' declarations before connecting; a
  hot reload refuses a plugin that needs new intents and asks for a restart.
- **B5 Commands and auto-defer** [rec]: the command tree defers ephemerally by default; commands
  that open modals opt out via `extras`; autocomplete is routed by command name; commands upload
  only when the hash of their payload changes; guild and global commands stay apart.
- **B6 Configuration** [owner]: one schema for the core config and one per plugin, with pydantic
  2; unknown keys warn; an invalid value disables only that plugin. The owner is the only
  operator.
- **B7 i18n** [rec]: lang files `register.yaml`, `message/*.yml` and `modal/*.yml` under Discord
  locale directory names; `app_commands.Translator` for commands; per-key fallback to the default
  locale; key sets validated at load.
- **B8 Storage** [rec]: SQLite (stdlib `sqlite3` on a thread) as the store: a key-value document
  table plus per-plugin tables where queries need them; every write awaited; per-guild locks.
  ChatLogger's message log lives in the plugin's own SQLite files under its data directory, a new
  file starting when the current one grows too large, and keeps messages for 5 years by default.
- **B9 Component IDs** [owner]: a versioned format (at most 100 characters). The legacy decoder
  (`{prefix}{a..z}:{value};...`, letters in each plugin's field order, user IDs in lowercase hex)
  stays in the code permanently. An interaction with a legacy ID is handled, then its message is
  edited so that its components carry new IDs. Panels are never re-sent in bulk.
- **B10 Templates** [owner]: the message format with content, embeds and components (the
  `!ButtonsComponent`, `!StringSelectMenu` and `!EntitySelectMenu` tags, `uid`, `model_key`)
  **and** Components V2. Placeholders: single-level `%key%` substitution, no recursion, user input
  never parsed, a fresh substitution context per render.
- **B13 No web dashboard** [rec]: `/xincord reload`, the console and the config files instead.
- **B14 Music** [rec]: a Lavalink 4.2+ node and lavalink.py, in docker compose (B16), in the
  compose profile `music` (`COMPOSE_PROFILES` in `.env`); a bot without MusicPlayer runs no node.
- **B15 Console and CLI** [owner]: signals (SIGTERM and SIGINT stop gracefully, SIGHUP reloads),
  the owner-only `/xincord reload [plugin]` and a prompt_toolkit console in a terminal. Under
  compose the bot runs without a TTY: the console stays off and the log holds plain lines. The CLI
  (argparse) takes `--level`, `--no-online` and `--force-renew-lang-resources`; the token comes
  from `XINCORD_TOKEN` (compose passes it from `.env`) or `config.yaml`.
- **B16 Versioning and deployment** [owner]: one semver; the Docker image (amd64 and arm64) on
  GHCR, run with docker compose on the macOS host (Apple
  M4 Pro, OrbStack). The SQLite file lives in a named volume, not a host bind mount. A release
  starts from a GPG-signed `v*` tag that the owner pushes, or that Claude pushes with the owner's
  approval; both distributions are on PyPI since 1.0.0 (2026-10-12), each publish waiting for
  the owner's approval, and TestPyPI is not used. `python -m xincord.core.backup` copies `data/` while the bot runs into `backups/` beside
  `compose.yaml`; the host runs it daily and keeps the newest 7.
- **B17 Testing** [rec]: pure logic without discord.py; Cogs and Views depend on narrow Protocols
  with hand-written fakes; SQLite `:memory:` for storage tests; pytest and pytest-asyncio (auto
  mode); a manual smoke checklist per plugin for a test guild; golden fixtures for Calculator.
- **B18 Package naming** [rec]: `xincord.core`, `xincord.plugins.<snake_name>`. The plugin's name
  is its entry point, its `plugins/<Name>/` directory, its store namespace and its new-format
  component ID namespace; legacy component prefixes keep their legacy names.
- **B19 Allowed mentions** [rec]: by default users (and the replied user) only; @everyone, @here
  and roles are off; a message opts in.

## C. Scope

- **C3 AGPL section 13** [rec]: `/bot-info` shows a source link whose URL is configurable.
