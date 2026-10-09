# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-10 at the end of the session that set up the repository and ported the first Core
capabilities. Read this file first, then `docs/porting/decisions.md` and `AGENTS.md`. The
decisions are accepted and binding; do not re-open them unless you find a serious problem, and
then ask the owner.

Talk to the owner in Traditional Chinese. Everything written into the repository is English.

## 1. Goal

Port XsDiscordBotKt (Kotlin + JDA 6, about 20.4k lines: Core 5.9k, 21 plugin modules 13.9k) to
Python 3.14 + uv as **xincord**, managing specs with OpenSpec and building everything test-first,
starting with Core. Motivation: easier maintenance and faster iteration.

## 2. Where things are

| What | Where |
|---|---|
| This project | `/Users/xinshou/IdeaProjects/xincord`, branch `main`, pushed to `origin` |
| Remote (private) | `git@github.com:xinshoutw/xincord.git`; CI: `.github/workflows/ci.yml` |
| Kotlin baseline | `/Users/xinshou/IdeaProjects/XsDiscordBotKt` at `3a59607` (branch `main`) |
| Accepted decisions | `docs/porting/decisions.md`; raw submission in `docs/porting/submissions/` |
| Project rules | `AGENTS.md` (there is deliberately no CLAUDE.md) |
| Porting guide and v3 differences | `docs/porting-guide.md` |
| Specs | `openspec/specs/` (archived), `openspec/changes/` (active) |
| Per-plugin inventories (acceptance-criteria source, with Kotlin `file:line`) | `docs/porting/analysis/inventory/<Plugin>.md` |
| BasicCalculator golden data | `docs/porting/analysis/inventory/fixtures/*.jsonl` |
| Research (versions, v4 branch, Core brief) | `docs/porting/analysis/research/*.md` |
| Kotlin v4 design spec (summarized in the porting guide) | `XsDiscordBotKt/docs/specs/2026-04-07-v4-core-refactor-design.md` |
| Local data copy for a future migration test (B11, deferred) | `XsDiscordBotKt/Server/` |

## 3. Rules

`AGENTS.md` holds the full rules. The essentials:

- Language: replies to the owner in Traditional Chinese; repository content in English; zero CJK
  characters in `*.py` (a prek hook enforces it); commit messages ASCII only.
- Commits: Conventional Commits with scopes `core`, `build`, `ci`, `docs`, `plugin-<name>`;
  GPG-signed; no attribution lines (the commit-msg hook rejects them); small and frequent; every
  commit passes `scripts/gate.sh`.
- TDD (A11, xfail-first): failing test committed with `@pytest.mark.xfail(strict=True,
  raises=NotImplementedError, reason="<requirement>")` against a stub, then the implementation
  commit removes the marker. Each test names its requirement in a docstring
  (`"""Requirement: <name>."""`) or in the module docstring.
- OpenSpec: one active change at a time; archive right after verification; every scenario has a
  test; requirement descriptions stay under 500 characters (`validate --strict` fails otherwise).
- Pushing `main` to `origin` is pre-authorized. Ask first for force pushes, deleting branches,
  tags, releases, PyPI publishing, repository settings, and anything on the XsDiscordBotKt remote.
- Do not create LICENSE (the owner adds it). Never commit real IDs, bank account numbers or tokens
  as defaults.
- List user-visible changes (copy, commands, interaction flow) for the owner before pushing them.

## 4. Architecture as built so far

- **Layout (resolution 2, amended):** a uv workspace. The root project is the `xincord`
  distribution (`src/xincord/core/`, `module-name = "xincord.core"`); `packages/xincord-plugins`
  is the `xincord-plugins` distribution (`src/xincord/plugins/`). `xincord` is a PEP 420 namespace;
  `xincord.plugins` is a regular package.
- **Gate:** `scripts/gate.sh` runs ruff check, ruff format check, pyright strict, coverage + pytest
  (branch coverage >= 85%, currently 100%) and `openspec validate --all --strict`. prek runs it on
  pre-push; the Claude Code Stop hook runs it too; CI runs it on every push.
- **Core modules (all archived and green):**
  - `xincord.core.config`: `load_config`, `parse_model`, `unknown_keys`, `Model`, `ConfigError`,
    the core schema `CoreConfig` (`token`, `status.activities`, `interaction_log`) and the default
    `resources/config.yaml`. `xincord.core.migrate_v3` converts the v3 core config
    (`python -m xincord.core.migrate_v3 <dir>`).
  - `xincord.core.storage`: `Store` over one SQLite connection on one worker thread; JSON values by
    namespace and key; `update` (atomic read-modify-write), `run` (plugin tables), `lock(key)`.
  - `xincord.core.i18n`: `export_lang`, `Lang.load` (locales, flattened YAML keys, Discord name
    rules, key-set warnings), `Lang.text` / `Lang.template` (fallback), `Lang.localization` (no
    fallback), `Lang.command` and `Translator`.
  - `xincord.core.placeholders`: single-pass `render`, the v3 key families (`actor_values`,
    `user_values`, `member_values`, `guild_values`, `channel_values`, `event_values`), Protocols
    that discord.py classes satisfy, and JDA locale names (`resources/locales.yaml`).
  - `xincord.core.templates` (package: `base`, `schema`, `render`, `__init__`): v1 message
    templates and modal templates, validated at load (`load_message`, `load_modal`,
    `Templates.load`) and rendered to `Message(content, embeds, view)` and `discord.ui.Modal`.
    Component and modal IDs come from a `build_id(uid_map)` callable the plugin passes in. Views
    and modals are stopped before they are returned, so discord.py never dispatches their
    interactions; the core will route them (Core change `command-tree`).
- **Still to build:** see section 5. The plugin contract (B3), intents (B4), command tree and
  auto-defer (B5), component IDs (B9), runtime (B15, B19, C3), Docker (B16) and all plugins.

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`. Each one's `design.md` in `openspec/changes/archive/` records its decisions and
"v3 behaved differently" notes; `docs/porting-guide.md` has the differences table.

### In progress: `core-components-v2` (decision B10)

- Committed: proposal, spec delta (MODIFIED capability `core-templates`), design and tasks;
  xfail tests for loading (`tests/core/test_templates_v2_load.py`) with v3's full example as
  `tests/fixtures/templates/components_v2_example.yml`.
- `MessageTemplate` (in `templates/schema.py`) has a temporary validator that raises
  `NotImplementedError` for any V2 input, which keeps those xfail tests failing for the expected
  reason. Replace it with the V2 mode rules.
- A local, untested draft of the V2 schema is in `git stash` as
  `wip(core): components v2 schema draft` (`src/xincord/core/templates/schema_v2.py`: pydantic
  models with callable discriminators that normalize `type`, map the select aliases and infer
  section accessories). To continue:
  1. `git stash pop`.
  2. Move `COLOR` from `templates/schema.py` to `templates/base.py` (the draft imports it there).
  3. Type `MessageTemplate.components_v2` as `tuple[TopLevelV2, ...]` and replace the temporary
     validator: with `is_components_v2`, content and embeds empty and at least one component;
     without it, only action rows (or bare model references) in `components_v2`.
  4. Gate, remove the xfail marker, commit (task 1.2).
  5. Tasks 2.1 to 2.4: render a stopped `discord.ui.LayoutView` (text display, section,
     thumbnail, media gallery, separator, file, container, action rows), `files` on `Message` for
     `file_path`, style names and premium buttons, select defaults, disabled containers, models,
     and the embed-to-container conversion (`v2/builder/MessageBuilder.kt:414-471`).
  6. Close: porting-guide row, push, CI, archive, `validate --all --strict`.

### Next Core changes, in order

1. **component-ids (B9):** a new versioned format (100 characters max) plus the permanent v3
   decoder (`{prefix}{a..z}:{value};...`, short keys in each plugin's field declaration order,
   longs in lowercase hex); lazy upgrade by editing the message after handling a legacy ID; never
   mass re-send. The codec provides the `build_id` that templates take. Golden tests per plugin
   come with each plugin.
2. **plugin-loading (B3, B4):** entry-point group `xincord.plugins`, metadata as module constants,
   `graphlib` ordering, missing-dependency check, per-plugin isolation, config and lang under
   `plugins/<Name>/` (use `load_config`, `export_lang`, `Lang.load`, `Templates.load`), intents
   aggregated before connecting, enabled-plugin list in the core config.
3. **command-tree (B5):** ephemeral auto-defer with opt-out through `extras`; autocomplete by
   command name; hash-based sync; guild/global split; `Translator` on the tree; routing of
   component and modal interactions (new and legacy IDs); the interaction placeholder keys left out
   of core-placeholders (`command_name`, `full_command_name`, `command_string`, `subcommand_name`,
   `language`, `channel_category_name`, `component_*`).
4. **runtime (B15, B19, C3):** client setup, argparse CLI (`--token`, `--level`, `--no-online`,
   `--force-renew-lang-resources`), signals, prompt_toolkit console, owner-only `/xincord reload`,
   status rotation from `status.activities`, interaction log from `interaction_log` (`cl_type`,
   `cl_interaction_string`), `AllowedMentions` for users only, database location.
5. **container (B16):** Dockerfile (arm64) and compose (bot; Lavalink later), SQLite in a named
   volume, `stdin_open` and `tty` for the console.

Then the plugins in C1 order (_Example first, as the template for the new API), using the
`port-plugin` skill. Update `docs/porting-guide.md` after each one.

### Working tips from this session

- Run the gate and check its exit status directly. Piping it into `tail` before `&&` once hid a
  failure and let a bad commit through (it was amended before pushing).
- OpenSpec is not installed globally: `OPENSPEC_TELEMETRY=0 npx --yes @fission-ai/openspec@1.14.1
  <command> </dev/null`. Telemetry is also off in `~/.config/openspec/config.json`.
- Per change: propose, `validate --strict`, commit; xfail and implementation commits; porting-guide
  rows; push; `gh run watch <id> --exit-status`; `archive <name> --yes`; `validate --all --strict`;
  commit; push.

## 6. Open items for the owner

1. **License metadata:** `pyproject.toml` has no `license` field yet. Decide between
   `AGPL-3.0-only` and `AGPL-3.0-or-later` when adding LICENSE.
2. **OpenSpec CLI:** optional global install (`npm i -g @fission-ai/openspec@1.14.1`) if the
   `/opsx` commands should work without npx.
3. **User-visible changes so far:** names, nicknames and channel names containing `%...%` are
   shown literally instead of being expanded (core-placeholders); the core `config.yaml` uses a new
   format with a migration script (core-config); a broken lang or template file now disables its
   plugin at startup instead of failing at click time.
4. **Production version (F1)** is unknown; it matters only if a data migration is ever needed.
5. **Lavalink image** (arm64, compose details) and **VoiceLogger status events** (audit types
   192/193, maybe raw gateway handling): verify when those plugins start.

## 7. Verified facts and pitfalls

**Versions in use (2026-10-10):** Python 3.14.8 (uv-managed), uv 0.12.24, ruff 0.16.10, pyright
1.1.414, pytest 9.1.1, pytest-asyncio 1.4.0, coverage 7.16.2, prek 0.5.5, OpenSpec 1.14.1,
discord.py 2.7.1, pydantic 2.14.0, PyYAML 6.0.3. Actions are pinned by SHA: checkout v7.0.1,
setup-uv v10.2.0, setup-node v7.1.0.

**Tooling pitfalls**
- Agent tools may decode a typed `\u` escape followed by hex digits into the real character.
  Build non-ASCII test data with `chr(0x4E2D)` or YAML fixtures; the CJK hook catches mistakes.
- prek refuses to install while a global `core.hooksPath` is set; this clone uses
  `git config --local core.hooksPath .git/hooks`. The owner's global commit-msg hook (which strips
  attribution lines) therefore does not run here; the project hook rejects such lines instead.
- prek `pygrep` compiles patterns as bytes: match UTF-8 byte ranges, never `\u` escapes.
- `importlib.import_module("xincord")` instead of `import xincord`: pyright reports the namespace
  package as a missing stub.
- Long Kotlin citations in docstrings exceed the line limit; put each path on its own line.
- Annotate `@asynccontextmanager` functions as returning `AsyncGenerator` (typeshed deprecates
  `AsyncIterator` there).
- YAML 1.1 reads a bare `no` as false: quote locale keys (`"no": ...`).
- `openspec/config.yaml` rules containing `: ` must be quoted.

**discord.py 2.7.1 facts**
- Decorators evaluate app-command annotations at import time; keep those imports at runtime
  (`runtime-evaluated-decorators` in `pyproject.toml`).
- `send`, interaction replies and `send_modal` store a view or modal for dispatch only if it is
  not finished; templates stop theirs.
- `TextInput(label=...)` is deprecated; wrap inputs in `discord.ui.Label` (as JDA 6's `Label.of`).
  discord.py's own deprecation helper can bypass `filterwarnings = ["error"]`, so watch pytest's
  "N warnings" line.
- `PartialEmoji.from_str` treats `<:name:id>` as custom only when the ID has 13 to 20 digits.
- `discord.ChannelType` has no 14 (JDA's `GUILD_DIRECTORY`).
- `isinstance` rejects subscripted generics such as `discord.ui.Button[View]`; check the bare
  class and `cast`.
- `on_member_remove` only fires for cached members; use `on_raw_member_remove`.
- `create_text_channel(overwrites=...)` does not copy the category's overwrites as JDA does.
- `tasks.loop` schedules from each start; there is no REST ping (time `GET /users/@me`).
- Components V2 classes exist: `LayoutView`, `Container`, `Section`, `TextDisplay`, `Thumbnail`,
  `MediaGallery` (`discord.MediaGalleryItem`), `Separator` (`SeparatorSpacing`), `File`,
  `ActionRow`; buttons take `sku_id`.

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions.

**BasicCalculator:** `decimal` defaults to 28 digits; use `Fraction` or exact decimal arithmetic.
The golden files decide.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
