# xincord porting decisions

Status: **accepted**. The owner submitted these through the Phase 1 decision page on 2026-10-10
(Asia/Taipei). Two conflicts were resolved in chat the same day (see "Resolutions"), and three
decisions were amended that afternoon (see "Amendments").

- Raw submission (labels and notes in Traditional Chinese): `submissions/s1791569618147.json`
- Decision page: https://claude.ai/artifact/E6CCEYRv6XA7nKc5rYCwDv
- Behavioral baseline: XsDiscordBotKt `main` @ `3a59607` (v3.4). The `refactor/modern-change`
  branch (v4 rewrite) is design input only; it does not work.

Markers: **[rec]** the owner followed the analysis recommendation; **[owner]** a deliberate
deviation from it; **[fact]** a factual answer.

## Resolutions (2026-10-10)

1. **Web-Dashboard is not ported.** F3 ticked it as "in use", B13 chose "do not port"; the owner
   confirmed B13.
2. **Two distributions.** B2 (core on PyPI, plugins via entry points) and B18
   (`xincord.plugins.<name>` naming) are combined as: distribution `xincord` (core, import
   `xincord.core`) plus distribution `xincord-plugins` (all official plugins, import
   `xincord.plugins.<snake_name>`, registered through entry points). `xincord` is a PEP 420
   namespace package (no `__init__.py`). Amended 2026-10-10 in the `project-skeleton` change:
   `xincord.plugins` is a regular package, because uv_build supports a single-root namespace
   module through a dotted `module-name` but documents `namespace = true` (several roots) as
   disabling its safety checks, and third-party plugins register through the entry-point group
   under their own top-level package anyway.
3. **Data migration is deferred** (derived from the F1 note, B11 note). The `xincord migrate` tool
   is built only if needed, after parity. The config migration script (B6) is in scope. Reversed
   on 2026-10-10 (afternoon): see Amendment 2.
4. **Component IDs follow the B9 note**, not the literal option label: new format, permanent
   legacy decoder, lazy upgrade on interaction, never a mass re-send.

## Amendments (2026-10-10, afternoon)

The owner answered the review queue (`owner-review.md`) and changed three decisions:

1. **B18, plugin names.** These plugins take new names for their entry point (the name in the
   core config's `plugins` list), `plugins/<Name>/` directory, store namespace, new-format
   component ID namespace, package and OpenSpec capability: _Example -> Example (package
   `example`), BasicCalculator -> Calculator (`calculator`), SimpleCommand -> CustomCommands
   (`custom_commands`), WelcomeByeGuild -> WelcomeGoodbye (`welcome_goodbye`), IntervalPusher ->
   UptimeHeartbeat (`uptime_heartbeat`), Feedbacker -> Feedback (`feedback`), TicketAddons ->
   TicketAwayNotice, NtustManager -> NtustAnnouncements, NtustCourse -> NtustCourseWatch. Legacy
   component ID prefixes keep the v3 names, so that v3's messages keep working. The other plugins
   keep their names.
2. **B11 and Resolution 3, data import.** The data migration is no longer deferred: a v3 data
   import, `xincord migrate` with a dry run and per-plugin counts, is built before cutover. It
   covers Economy's wallets and the other data worth keeping, such as channel bindings. B11's test
   plan stands: test against the local copy in `XsDiscordBotKt/Server/`; where it disagrees with
   the GitHub source, the source wins.
3. **B8, ChatLogger's message log.** The log keeps messages for 5 years by default and lives in the
   plugin's own SQLite files under its data directory inside the `data/` volume, a new file
   starting automatically when the current one grows too large. This replaces `port-chat-logger`'s
   answer to B8's open question (one table in the shared store, 30 days by default); built in
   `chat-logger-split-storage` (2026-10-11).

## F. Facts

- **F1 Production version** [fact]: unknown. Owner: no data migration is needed now; the data
  set is small; migrate later only if it becomes necessary.
- **F2 Deployment host** [fact]: macOS on Apple M4 Pro. Memory and CPU are not a concern.
  Consequence: Docker (OrbStack or Docker Desktop) with arm64 images; the MongoDB/Raspberry Pi
  constraint no longer applies.
- **F3 Modules in use** [fact]: AutoRole, BasicCalculator, BotInfo, ChatLogger,
  DynamicVoiceChannel, Economy, Feedbacker, Giveaway, IntervalPusher, MusicPlayer, NtustCourse,
  NtustManager, SimpleCommand, Ticket, TicketAddons, VoiceLogger, WelcomeByeGuild.
  Not in use: RentSystem, ChannelConverter. Web-Dashboard: see Resolution 1.

## A. Repository and process

- **A1 Branching and pushing** [rec]: commit directly on `main`. Normal pushes to xincord are
  pre-authorized. Still ask first for: force push, deleting branches, tags, releases, PyPI
  publishing, repository settings. Switch to a PR flow after cutover (C2).
- **A2 Kotlin source references** [rec]: cite `XsDiscordBotKt@3a59607:<path>:<line>`. A local tag
  `port-baseline` may be created in the old repo; pushing it needs approval.
- **A3 v4 design spec** [rec]: stays in the old repo (`docs/specs/2026-04-07-v4-core-refactor-design.md`).
  Summarize the still-relevant intents in `docs/porting-guide.md` with a link.
- **A4 Documentation language** [rec]: English everywhere (OpenSpec specs and designs, porting
  guide, README, AGENTS.md).
- **A5 CJK and ASCII boundaries** [rec]: zero CJK in `*.py`, tests included. Tests assert through
  lang keys, YAML fixtures under `tests/fixtures/`, or `\u` escapes. Lang YAML and test fixture
  YAML are exempt. Commit messages are ASCII only; refer to lang keys instead of quoting UI text.
- **A6 Docstrings** [rec]: Google-style docstrings for the public core API only; comments
  explain why; ruff `D` rules enabled for core only; test docstrings name the requirement and the
  Kotlin source.
- **A7 Rules and skills** [rec + owner note]: project rules live in `AGENTS.md`. **No CLAUDE.md**:
  Claude Code reads AGENTS.md natively when no CLAUDE.md exists in the folder or its parents.
  One project skill: `.claude/skills/port-plugin/`.
- **A8 Quality gates** [rec]: ruff `select = ["ALL"]` with documented ignores and
  `runtime-evaluated-decorators` for discord.py; pyright strict on `src` and `tests`; branch
  coverage >= 85%; prek runs `.pre-commit-config.yaml` (ruff check, ruff format, pyright, CJK
  check, commit-msg ASCII + Conventional Commits; pytest on pre-push); Claude Code hooks
  (PostToolUse: ruff format/fix on edited `.py`; Stop: full gate); GitHub Actions with
  `astral-sh/setup-uv` pinned to an exact version, `uv sync --locked`, and
  `openspec validate --all --strict`.
- **A9 Name** [rec]: `xincord`. License AGPLv3; the owner creates LICENSE (do not generate it).
  The owner chose `AGPL-3.0-or-later` on 2026-10-10.
- **A10 OpenSpec init** [rec]: `--tools claude` only; telemetry off.
- **A11 TDD record** [owner]: **xfail-first**. Commit the new test marked
  `@pytest.mark.xfail(strict=True)` (gates stay green), then a second commit that implements the
  behavior and removes the marker. Configure `xfail_strict = true`.
- **A12 v3 defects** [rec]: fix them; record "v3 behaved differently: ..." in the change design and
  the porting guide; list user-visible changes (copy, commands, interaction flows) for the owner.

## B. Architecture

- **B1 Discord library** [rec]: discord.py (2.7.1 at analysis time).
- **B2 Project structure** [owner]: core publishable to PyPI, plugins through entry points. See
  Resolution 2 for the two-distribution layout. The core API becomes public: keep it small and
  version it with semver.
- **B3 Plugin contract** [rec]: one discord.py extension + Cog per plugin; metadata as module
  constants; stdlib `graphlib` orders by dependency; a failing plugin disables only itself;
  config and lang stay under `plugins/<Name>/`; hot reload via `reload_extension`, reloading
  dependents too.
- **B4 Intents** [rec]: aggregate from enabled plugins' declarations before connecting; hot reload
  refuses a plugin that needs new intents and asks for a restart.
- **B5 Commands and auto-defer** [rec]: the command tree defers ephemerally by default; commands
  that open modals opt out via `extras`; autocomplete is routed by command name; sync only when
  the hash of the command payload changes; keep the guild/global split.
- **B6 Configuration** [owner]: **new config schema**, plus a migration script from the v3 files
  (core `config.yaml` and every `plugins/<Name>/config.yaml`). Owner note: they are the only
  operator. pydantic v2; unknown keys warn; invalid values disable only that plugin.
- **B7 i18n** [rec]: keep the lang file formats (`register.yaml`, `message/*.yml`,
  `modal/*.yml`, Discord locale directory names); `app_commands.Translator` for commands;
  per-key fallback to the default locale; key sets validated at load.
- **B8 Storage** [rec]: SQLite (stdlib `sqlite3` + `asyncio.to_thread`) as the single store: a
  key-value document table plus per-plugin tables where queries need them; every write awaited;
  per-guild locks. Whether ChatLogger's large message log gets its own file is decided when that
  plugin is ported. Amended on 2026-10-10 (afternoon): it gets its own files, kept 5 years by
  default (Amendment 3).
- **B9 Component IDs** [owner, see Resolution 4]: a new versioned format (<= 100 characters). The
  v3 decoder (`{prefix}{a..z}:{value};...`, short keys in each plugin's field declaration order,
  longs in lowercase hex) stays in the code permanently. When an interaction arrives with a legacy
  ID, handle it, then edit that message so its components carry new-format IDs. Never mass
  re-send panels.
- **B10 Templates** [owner]: implement the v1 format used today (content, embeds, components with
  the `!ButtonsComponent` / `!StringSelectMenu` / `!EntitySelectMenu` tags, `uid`, `model_key`)
  **and** Components V2. Placeholders: single-level `%key%` substitution, no recursion, user input
  never parsed, a fresh substitution context per render.
- **B11 Data compatibility** [rec + Resolution 3]: approach is a one-time `xincord migrate` tool
  with dry-run and per-plugin counts, **deferred**. When built, test against the local copy in
  `XsDiscordBotKt/Server/`; where it disagrees with the GitHub source, the source wins. Amended
  on 2026-10-10 (afternoon): built before cutover (Amendment 2).
- **B12 API plugins** [rec]: none survive. SQLiteAPI is replaced by the storage layer;
  GoogleSheetAPI is dropped (Economy's dead `SheetImpl` path and its hard dependency go too);
  AudioAPI folds into MusicPlayer's declared requirements.
- **B13 Web-Dashboard** [rec, confirmed]: not ported. Use `/xincord reload`, the console and config
  files instead.
- **B14 Music** [rec]: Lavalink 4.2+ node + lavalink.py. Owner asked whether docker compose is the
  right way to run it all: yes (see B16).
- **B15 Console and CLI** [owner]: signals (SIGTERM/SIGINT graceful stop, SIGHUP reload) +
  owner-only `/xincord reload [plugin]` + a prompt_toolkit interactive console. CLI via argparse:
  `--token`, `--level`, `--no-online`, `--force-renew-lang-resources`; drop the version check and
  `--ignore-update`. Under compose the console needs `stdin_open: true` and `tty: true`
  (`docker compose attach`).
- **B16 Versioning and deployment** [owner]: one semver (0.x until cutover, 1.0.0 at cutover);
  Docker image (arm64 at least) + docker compose (bot, later Lavalink) on the macOS host.
  Keep the SQLite file in a named volume, not a host bind mount.
- **B17 Testing** [rec]: pure logic without discord.py; Cogs and Views depend on narrow Protocols
  with hand-written fakes; SQLite `:memory:` for storage tests; pytest + pytest-asyncio (auto
  mode); a manual smoke checklist per plugin for a test guild; golden fixtures for BasicCalculator.
- **B18 Package naming** [rec]: `xincord.core`, `xincord.plugins.<snake_name>`. Display names,
  `plugins/<Name>/` directories and legacy component prefixes keep the original plugin names.
  Amended on 2026-10-10 (afternoon): nine plugins are renamed (Amendment 1).
- **B19 Allowed mentions** [rec]: default allows users (and the replied user) only; @everyone,
  @here and roles are off; opt in per message.

## C. Scope

- **C1 Order** [rec]: Core -> _Example (rewritten as the template for the new API) ->
  BasicCalculator -> AutoRole -> BotInfo -> SimpleCommand -> WelcomeByeGuild -> IntervalPusher ->
  Feedbacker -> Economy -> DynamicVoiceChannel -> VoiceLogger -> ChatLogger -> Giveaway -> Ticket ->
  TicketAddons -> NtustManager -> NtustCourse -> MusicPlayer. NtustCourse is in scope (F3); move
  its hard-coded semester and go-live gate into config.
- **C2 Parity** [owner]: switch to xincord once every in-scope plugin's scenarios have passing
  tests. No soak period.
- **C3 AGPL section 13** [rec]: `/bot-info` shows a source link whose URL is configurable.

## Owner's overall note

When done, give a summary, a compact prompt and HANDOFF files so a new session can continue
(handled on 2026-10-10: see `HANDOFF.md` at the repository root).
