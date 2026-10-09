# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-10 after the `core-component-routing` change was archived. Read this file first, then `docs/porting/decisions.md` and `AGENTS.md`. The
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
    the core schema `CoreConfig` (`token`, `plugins`, `status.activities`, `interaction_log`) and
    the default `resources/config.yaml`. `xincord.core.migrate_v3` converts the v3 core config and
    lists the plugins whose v3 config had `enabled: true` (`python -m xincord.core.migrate_v3 <dir>`).
  - `xincord.core.storage`: `Store` over one SQLite connection on one worker thread; JSON values by
    namespace and key; `update` (atomic read-modify-write), `run` (plugin tables), `lock(key)`.
  - `xincord.core.i18n`: `export_lang`, `Lang.load` (locales, flattened YAML keys, Discord name
    rules, key-set warnings), `Lang.text` / `Lang.template` (fallback), `Lang.localization` (no
    fallback), `Lang.command` and `Translator`.
  - `xincord.core.placeholders`: single-pass `render`, the v3 key families (`actor_values`,
    `user_values`, `member_values`, `guild_values`, `channel_values`, `event_values`), Protocols
    that discord.py classes satisfy, and JDA locale names (`resources/locales.yaml`).
  - `xincord.core.templates` (package: `base`, `schema`, `schema_v2`, `render`, `render_v2`,
    `__init__`): v1 message templates, Components V2 and modal templates, validated at load
    (`load_message`, `load_modal`, `Templates.load`) and rendered to
    `Message(content, embeds, view, files)` and `discord.ui.Modal`. V2 mode renders a
    `discord.ui.LayoutView`; `files` carries the uploads that `file_path` media need.
  - `xincord.core.component_ids`: `ComponentIds(namespace, fields, legacy_prefix=, legacy_hex=)`
    builds `{namespace}:1:{letter}={value};...` (percent-encoded, 100 characters max; `build` is
    the templates' `build_id`), parses new and v3 IDs into text fields (`ParsedId.legacy`), and
    `upgrade` / `upgrade_view` rewrite legacy IDs in a view rebuilt with `from_message`.
  - `xincord.core.plugins`: `discover(enabled)` reads entry points (group `xincord.plugins`, name =
    plugin name) and the module constants `DEPENDS`, `SOFT_DEPENDS`, `INTENTS`, drops broken
    plugins, missing dependencies and cycles, and orders the rest with `graphlib`;
    `required_intents`; `PluginContext` (`directory`, `store`, `config(Model)`, `lang(locale)`).
  - `xincord.core.bot.Bot(commands.Bot)`: created from the discovered plugins with their intents;
    `load_plugins()` (isolated failures, dependents skipped), `plugin_context(__name__)` for a
    plugin's `setup(bot)`, `load_plugin(info)` (hot load: refuses new intents or missing
    dependencies), `reload_plugin(name)` (with dependents; discord.py keeps the old version on
    failure), `route(__name__, ids, handler)` and `on_interaction`, which sends component and
    modal interactions to the owning plugin's handler with a `ParsedId` and, after a legacy ID,
    fetches the message, runs `upgrade_view` and edits it once. Runtime will extend this class.
  - `xincord.core.command_tree.CommandTree` (the bot's `tree_cls`): `interaction_check` defers
    application commands ephemerally unless `extras["defer"]` is False; `payloads()` splits
    guild commands from `extras["global"]` ones (translated when a translator is set);
    `sync_global(store)` / `sync_guild(store, guild_id, force=)` upload only when the payload's
    SHA-256 changed (stored in the `core` namespace) and log failures.
    Component and modal IDs come from a `build_id(uid_map)` callable the plugin passes in. Views
    and modals are stopped before they are returned, so discord.py never dispatches their
    interactions; the core will route them (Core change `command-tree`).
- **Still to build:** see section 5. The plugin contract (B3), intents (B4), command tree and
  auto-defer (B5), component IDs (B9), runtime (B15, B19, C3), Docker (B16) and all plugins.

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`, `core-components-v2`, `core-component-ids`, `core-plugin-loading`,
`core-command-tree`, `core-component-routing`. Each one's `design.md` in
`openspec/changes/archive/` records its decisions and "v3 behaved differently" notes;
`docs/porting-guide.md` has the differences table.

### Next Core changes, in order

1. **core-interaction-values:** the interaction placeholder keys left out of core-placeholders,
   as v3's `Placeholder.get(event)` built them (`Placeholder.kt:59-142`): `command_name`,
   `full_command_name`, `command_string` (JDA's `/name sub option: value` format, also needed by
   the interaction log), `subcommand_name`, `language` (native name via `locale_names`),
   `channel_id`, `channel_name`, `channel_category_name`, and for components `component_id`,
   `component_label`, `component_style`, `component_url`, `component_emoji`,
   `component_emoji_name`, `component_min`, `component_max`, `component_placeholder` (looked up
   in `interaction.message.components`). No shipped template uses them; keep it small and test
   with Protocol fakes.
2. **runtime (B15, B19, C3):** extend `xincord.core.bot.Bot` (discover from `CoreConfig.plugins`,
   `load_plugins` and `tree.set_translator(Translator())` in `setup_hook`; `sync_global` and
   `sync_guild` for every guild on ready, `sync_guild(force=True)` on guild join), argparse CLI
   (`--token`, `--level`, `--no-online`, `--force-renew-lang-resources`), signals,
   prompt_toolkit console, owner-only `/xincord reload` (through `reload_plugin` and
   `load_plugin`), status rotation from `status.activities`, interaction log from
   `interaction_log` (`cl_type`, `cl_interaction_string`), `AllowedMentions` for users only,
   database location.
3. **container (B16):** Dockerfile (arm64) and compose (bot; Lavalink later), SQLite in a named
   volume, `stdin_open` and `tty` for the console.

Then the plugins in C1 order (_Example first, as the template for the new API), using the
`port-plugin` skill. Update `docs/porting-guide.md` after each one.

### Working tips from this session

- Template tests that check rendered views must be `async`: a discord.py view created outside a
  running event loop never reports `is_finished()`.
- Run the gate and check its exit status directly. Piping it into `tail` before `&&` once hid a
  failure and let a bad commit through (it was amended before pushing).
- OpenSpec is not installed globally: `OPENSPEC_TELEMETRY=0 npx --yes @fission-ai/openspec@1.14.1
  <command> </dev/null`. Telemetry is also off in `~/.config/openspec/config.json`.
- Per change: propose, `validate --strict`, commit; xfail and implementation commits; porting-guide
  rows; push; `gh run watch <id> --exit-status`; `archive <name> --yes`; `validate --all --strict`;
  commit; push.

## 6. Open items for the owner

Answered on 2026-10-10: the license is `AGPL-3.0-or-later` (set in both `pyproject.toml` files;
the owner still adds LICENSE); OpenSpec stays on npx; the user-visible changes listed so far are
accepted.

1. **Production version (F1)** is unknown; it matters only if a data migration is ever needed.
2. **Lavalink image** (arm64, compose details) and **VoiceLogger status events** (audit types
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
