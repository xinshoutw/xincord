# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-10 after `port-giveaway`, the thirteenth plugin port. Core is complete. Read
this file first, then `docs/porting/decisions.md` and `AGENTS.md`. The decisions are accepted and
binding; do not re-open them unless you find a serious problem, and then ask the owner.

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
    `user_values`, `member_values`, `guild_values`, `channel_values`, `event_values`,
    `interaction_values` with JDA's `command_string`), `placeholder_values(interaction)` (v3's
    `Placeholder.get(event)`: the acting user's keys with the bot's and the interaction's),
    `global_values(client)` (v3's global substitutor, `bot_id` and `bot_name`, for templates v3
    rendered without a user), Protocols that discord.py classes satisfy (`EventLike` and
    `ClientLike` for interactions), and JDA locale names (`resources/locales.yaml`,
    `locale_names`). A thread whose parent channel is not cached gives no `channel_category_name`
    (discord.py's `Thread.category` raises there).
  - `xincord.core.templates` (package: `base`, `schema`, `schema_v2`, `render`, `render_v2`,
    `__init__`): v1 message templates, Components V2 and modal templates, validated at load
    (`load_message`, `load_modal`, `Templates.load`) and rendered to
    `Message(content, embeds, view, files)` and `discord.ui.Modal`. V2 mode renders a
    `discord.ui.LayoutView`; `files` carries the uploads that `file_path` media need. Embed fields
    are trimmed as JDA did (Java's `trim`) and an empty name or value becomes U+200E, which Discord
    would refuse otherwise; `modal_values(data)` reads a submitted modal's text inputs by custom ID
    (inside labels or action rows), since discord.py parses submissions only for modals it
    dispatches.
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
    fetches the message, runs `upgrade_view` and edits it once. `setup_hook` sets the
    `Translator` and loads the plugins before the gateway connects; `on_ready` syncs the global
    commands and every guild's, `on_guild_join` forces the new guild's; the default
    `allowed_mentions` ping users and the replied-to user only (B19). `reload(plugin=None)`
    returns a one-line summary: without a plugin it re-reads `CORE_CONFIG`, unloads plugins that
    left the list (dependents first), reloads the loaded ones and loads new ones; with a plugin it
    reloads it and its dependents. Reloads are serialized by a lock and upload every scope with
    force when the bot is ready. `relay_gateway_event(name)` (since port-voice-logger) adds a
    parser to discord.py's parser table for a gateway event it does not parse and dispatches
    `gateway_<name in lower case>` with Discord's payload, after discord.py's own parser if any.
  - `xincord.core.admin.Xincord`: the global, guild-only `/xincord` group (administrators see it by
    default); `reload [plugin]` runs for the application owner only and replies ephemerally with
    the summary; `plugin` autocompletes loaded plugins. `setup_hook` registers it.
  - `xincord.core.cli`: the `xincord` console script. `parse_args` (`--token`, `--level`,
    `--no-online`, `--force-renew-lang-resources` with v3's short forms) returns `Options`;
    `run(options)` loads `config.yaml`, opens `data/xincord.db`, discovers `CoreConfig.plugins`
    and either checks them offline (`--no-online`: load, unload, exit 0 or 1) or connects until
    SIGINT or SIGTERM closes the bot and the store; SIGHUP runs `bot.reload()`. Logs go to stderr
    only. On a terminal (not `--no-online`), `main` sets up logging inside
    `patch_stdout(raw=True)` and `_serve` runs the console task, cancelled when the bot stops.
  - `xincord.core.console`: `run_console(bot, stop)` (prompt `console > `; `reload [plugin]`,
    `stop` / `exit` / `shutdown` and ^D call `stop`, ^C is logged) and `completer(bot)`.
  - `xincord.core.status`: `activity(entry)` and `rotate(client, activities)`; the bot keeps the
    core config (`Bot(..., config=)`), starts the rotation on ready, restarts it after a full
    reload and cancels it in `close`.
  - `xincord.core.interaction_log`: `describe(interaction)` (v3's CMD, MSG, BTN, STRING, ENTITY,
    MODAL) and `log(client, interaction, targets)`, called by `Bot.on_interaction` after routing:
    a console line, then the matching `interaction_log` targets via `get_partial_messageable`,
    never pinging.
  - `xincord.core.command_tree.CommandTree` (the bot's `tree_cls`): `interaction_check` defers
    application commands ephemerally unless `extras["defer"]` is False; `payloads()` splits
    guild commands from `extras["global"]` ones (translated when a translator is set);
    `sync_global(store)` / `sync_guild(store, guild_id, force=)` upload only when the payload's
    SHA-256 changed (stored in the `core` namespace) and log failures.
    Component and modal IDs come from a `build_id(uid_map)` callable the plugin passes in. Views
    and modals are stopped before they are returned, so discord.py never dispatches their
    interactions; the core will route them (Core change `command-tree`).
- **Deployment (`container`):** `Dockerfile` (two stages on `python:3.14.8-slim-trixie`, uv 0.12.24,
  `uv sync --locked --no-dev --all-packages --no-editable`, user `xincord` in `/bot`, entry point
  `xincord`), `.dockerignore`, and `compose.yaml` (service `bot`: `./bot` bind-mounted at `/bot`,
  named volume `data` = `xincord_data` at `/bot/data`, `stdin_open`, `tty`, `init`,
  `restart: unless-stopped`, 30 s stop grace, json-file logs 10 MB x 3).
- **Plugins (`packages/xincord-plugins`):** `xincord.plugins.example` (entry point `_Example`), the
  template: `__init__.py` (metadata constants, `setup`), `config.py`, `cog.py` (commands built in
  `setup` from the Lang with the cog's bound method as callback, `IDS = ComponentIds("example",
  ("action", "count"))` routed with `bot.route`), bundled `config.yaml` and `lang/`. Conventions
  for every port: `.claude/skills/port-plugin/SKILL.md`. Reuse in tests: `plugin_fakes.load_plugin`
  (real entry point, offline), `plugin_fakes.golden(<package>)`, `tests/support/discord_fakes.py`
  (`FakeInteraction` records `sent`; `buttons`, `embed_dict`); the `store` fixture is in
  `tests/conftest.py`. The example's `placeholder_values` moved into `xincord.core.placeholders`
  with WelcomeByeGuild.
- **BasicCalculator** (`xincord.plugins.basic_calculator`, no config): `calculator.py` is a pure
  evaluator with v3's shunting-yard pass and `BigDecimal` results (`BigDecimal(unscaled, scale)`),
  v3's defects fixed and size limits; `cog.py` runs it in `asyncio.to_thread`, posts the answer to
  the channel (`_post`: a `runtime_checkable` `Postable` protocol, fallback to the deferred
  response on `discord.HTTPException`) and edits errors into the deferred response. Reuse:
  `discord_fakes.FakeChannel`, `forbidden()` and `delete_original_response`; the golden pattern
  for recorded v3 answers with an independent evaluator (`tests/plugins/basic_calculator/
  test_golden.py`).
- **AutoRole** (`xincord.plugins.auto_role`, `INTENTS = discord.Intents(members=True)`, no lang):
  an `on_member_join` cog listener adds each configured role with its own atomic `add_roles`
  request (v3 replaced all roles), skipping and logging roles that are missing or not
  `is_assignable()`; `check()` logs config problems from `on_ready` and from `cog_load` when the
  bot is already ready. Reuse: `plugin_fakes.dispatch(bot, event, *args)` for listeners,
  `load_plugin(..., config=...)`, `discord_fakes.FakeGuild` / `FakeRole` / `FakeMember`, and the
  ready-check pattern for any plugin that needs guild data at startup.
- **BotInfo** (`xincord.plugins.bot_info`, `INTENTS = discord.Intents(members=True)` for current
  member counts): the first global command, `extras={"global": True}` with JDA's default contexts
  and install types set explicitly (`allowed_contexts`, `allowed_installs`); `counts(guilds)` is a
  pure function over `interaction.client.guilds`; the reply renders `bot-info` with values of one
  render (`guild_counts`, `member_counts`, `source_url`, v3's `bot_id` and `bot_name`).
  `config.yaml` has `source_url` (C3, default the xincord repository), validated at load as an
  http(s) URL of at most 512 characters. Reuse: `FakeGuild(member_count=...)`, a `FakeInteraction`
  whose `client` is `SimpleNamespace(user=BOT_USER, guilds=[...])`, the global payload check in
  `tests/plugins/bot_info/test_command.py`, and a `cast`-based `cog` fixture for a plugin whose
  tests load invalid configs.
- **SimpleCommand** (`xincord.plugins.simple_command`, no intents, no config, zh-TW only): five
  guild commands from the `COMMANDS` table (`command(name)` with
  `app_commands.default_permissions(administrator=True)`) share the callback `post_message`, which
  reads `interaction.command.name`, renders that template in `lang.default_locale` with v3's
  `bot_id` and `bot_name`, posts the whole message (content, embeds, view and files) through
  `_postable` (the channel as `object` against the `Postable` Protocol) and `_send`, then deletes
  the deferred response; when the channel takes no messages or refuses it, it renders again and
  edits the deferred response, with the files as `attachments`. The bundled templates hold the
  example account number `000000000000`. Reuse: `FakeInteraction(command=SimpleNamespace(name=...))`
  and `ClosingChannel` (`tests/plugins/simple_command/test_post.py`) for discord.py's closed files.
  Their v3 global keys now come from the core's `global_values` (moved there by Economy).
- **WelcomeByeGuild** (`xincord.plugins.welcome_bye_guild`, `INTENTS = discord.Intents(members=True)`,
  no config, en-US and zh-TW): the first plugin with data. `store.py` keeps v3's per-guild document
  (`{"welcomeChannelId", "byeChannelId"}`, 0 = unbound) in the key-value table under the namespace
  `WelcomeByeGuild` and the guild ID, read without writing and changed by `set_channel` under
  `store.lock("WelcomeByeGuild:<id>")`; `values.py` builds v3's `wbg@` keys from the core families
  (`command_values`, `member_event_values`) and checks text channels with a `runtime_checkable`
  Protocol; `cog.py` has four guild commands with two shared callbacks (`bind_channel`,
  `unbind_channel`, kind from the `COMMANDS` table), a `TextChannelOption` transformer that limits
  the option to text channels (`channel_types` [0]), the runtime Administrator check through
  `interaction.permissions`, replies in `interaction.guild_locale`, `on_member_join`,
  `on_raw_member_remove` (skips the bot's own removal) and `on_guild_remove`, and
  `forget_left_guilds` from `on_ready` and `cog_load`. Reuse: the per-guild data convention (skill,
  "Storage"), `FakeGuild(channels=..., preferred_locale=..., icon=..., rules_channel=...)` with
  `get_channel` and `as_guild()`, `FakeChannel(type=...)`, `FakeMember` with placeholder
  attributes, `FakeInteraction(guild=, guild_locale=, permissions=)`, `Bot.user` patched as a
  property, and the scratch probe through discord.py's own objects (skill step 7).
- **IntervalPusher** (`xincord.plugins.interval_pusher`, no intents, no lang, config
  `listeners[].url` and `interval`): the first background loop and outgoing HTTP. `pusher.py` has
  `Pusher(number, listener, get, ping, sleep)`, v3's loop with its effects passed in (push at once,
  then `interval` seconds after each attempt; a 404 ends it; failures are logged), `rest_ping`
  (times `bot.http.request(Route("GET", "/users/@me"))`, JDA's REST ping) and aiohttp's
  `open_session` and `get_status` (no redirects, v3's timeouts); `xincord-plugins` declares aiohttp.
  `cog.py` creates one task per listener in `cog_load`, each awaiting `bot.wait_until_ready()`, and
  cancels and awaits them in `cog_unload`. Reuse: `plugin_fakes.Ready` (READY for offline bots; its
  `close` cancels the tasks left running), `http_fakes.running_monitor()` (`Monitor`, a local HTTP
  server), patching `discord.http.HTTPClient.request` to record REST calls, an injected `sleep`
  with a fake clock, `bot.remove_cog` to run `cog_unload` without unloading the modules, and the
  REST probe through `Route.BASE` and `http.static_login` (skill step 7).
- **Feedbacker** (`xincord.plugins.feedbacker`, no intents, en-US and zh-TW, five config replies):
  the first port with v3 component IDs and a modal. `cog.py` has `IDS = ComponentIds("feedbacker",
  (action, user_id, star_count, submit_channel_id), legacy_prefix="feedbacker@")` routed to
  `handle`, which dispatches on the interaction type and the action; `create_form` (the command,
  with `member: discord.Member | discord.User` checked against `MemberLike` and a copy of
  WelcomeByeGuild's `TextChannelOption`), `press_star` (`form_not_you`, the `fill-form` modal
  through `render_modal` and `send_modal`, then `form.highlight` and the bot's own
  `message.edit`) and `submit_form` (`modal_values`, `response.defer()`, the review in the guild's
  locale, the form deleted only after the post, `followup.send(..., ephemeral=True)` on failure).
  `config.py` keeps v3's three required replies and adds `form_failure` and `form_submit_failure`
  (English defaults, zh-TW in the bundled file), each non-blank and at most 2000 characters.
  Reuse: `discord_fakes.FakeMessage` (edits and deletion into `sent`, fetched until deleted),
  `FakeResponse.send_message` and `send_modal`, `FakeInteraction.followup`, `not_found()`, route
  tests through `bot.on_interaction` with v3 IDs (`tests/plugins/feedbacker/test_routes.py`), and
  the HTTP-recording probe for interactions (skill step 7).
- **Economy** (`xincord.plugins.economy`, no intents, en-US and zh-TW, config `admin_id` and
  `board_user_show_limit`): the first plugin whose data must never lose an update. `wallet.py` is
  pure (`Wallet`, v3's six `OPERATIONS` on exact integers, `rank` with ties by user ID);
  `store.py` keeps v3's per-guild document (`{"<userId>": {"cost", "money"}}`, namespace
  `Economy`), reads without writing, changes one user's entry in a single `Store.update` whose
  function returns a new document and hands the wallets back through a list, raises `DataError` for
  entries that are not v3's shape without overwriting them, and keeps the wallets of guilds the bot
  left, as v3 did. `cog.py` builds v3's nine guild commands from `COMMANDS`
  (`CommandSpec(kind, ...)`: `show_balance`, `show_board`, `change_wallet`), checks `admin_id`
  (Discord's Administrator does not count), answers `no-permission` with `global_values`, renders
  the boards from the first embed's description (`_board`; `check_boards` refuses a template
  without it at load) and routes `IDS = ComponentIds("economy", ("action",),
  legacy_prefix="economy@")` to `handle`, where any Economy button shows the presser's wallet.
  `admin_id` has no default and ships empty, so the plugin waits for the operator. Reuse:
  `global_values`, the `Store.update` pattern for balances and counters, `check_boards` for row
  templates, `numbers(embed)` in `tests/plugins/economy/test_change.py` to compare amounts without
  typing non-ASCII, and operator templates written under `tmp_path / "plugins"` before
  `load_plugin` (`tests/plugins/economy/test_board.py`).
- **DynamicVoiceChannel** (`xincord.plugins.dynamic_voice_channel`, `INTENTS =
  discord.Intents(voice_states=True)`, en-US and zh-TW, no config): the first plugin with
  subcommands, voice events and channels it creates and deletes. `store.py` keeps v3's binding list
  per guild (namespace `DynamicVoiceChannel`) and the rooms per guild (`DynamicVoiceChannel.rooms`,
  `{"<room ID>": <owner ID>}`), changed under the store's data lock with `get`/`put`/`delete` so
  that no-op changes write nothing; `names.py` renders format 1 (`room_values`, `room_name` with
  JDA's 100 UTF-16 limit); `rooms.py` creates a room (clone, track once the copy exists, JDA's raw
  position PATCHes through `Route`, `set_permissions` for the member, each refusal logged and the
  other steps still sent), deletes empty tracked rooms (a 404 forgets, other refusals keep) and
  checks a guild at READY (`Room`, a runtime Protocol); `cog.py` builds the `app_commands.Group`
  with bound-method subcommands and `VoiceChannelOption`, and has `on_voice_state_update` (reads
  `voice_states` before awaiting, then `store.lock("DynamicVoiceChannel:voice:<id>")`),
  `on_guild_remove` and `check_guilds` from `on_ready` and `cog_load` (left guilds forgotten,
  unavailable ones skipped, unreadable ones skipped with an error). Reuse:
  `discord_fakes.FakeVoiceChannel` (`clone`, `delete` and `set_permissions` recording or raising,
  `cloning` and `gate` for interleavings), `voice_state(channel)`, `FakeGuild.voice_channels`,
  `FakeRest` (REST requests recorded in the channels' `sent` list), the `cast` cog fixture and the
  voice probe (skill step 7).
- **VoiceLogger** (`xincord.plugins.voice_logger`, `INTENTS = discord.Intents(voice_states=True)`,
  en-US and zh-TW, no config): the first plugin with a gateway event that discord.py drops
  (`VOICE_CHANNEL_STATUS_UPDATE`, relayed with the core's `relay_gateway_event`) and with the audit
  log. `settings.py` is pure (`Setting`, `detects`, `targets`, `list_text` bounded to 1024 UTF-16
  code units); `store.py` keeps v3's document per guild, `{"<listen channel>": {"allow_mode",
  "allow", "block"}}` (namespace `VoiceLogger`), one entry changed at a time under the guild's lock,
  no write for no change; `logs.py` is pure (`Place`, read before awaiting, `voice_change`,
  `UNKNOWN_MEMBER`); `status.py` has `parse_update`, `classify`, `match` and `find_actor` (the
  audit log reader and `sleep` passed in); `cog.py` has the group with `setting`, `handle` for the
  menu's buttons and entity select menus (each answer replaces the message with
  `response.edit_message`), `on_voice_state_update`, `on_gateway_voice_channel_status_update`
  (statuses tracked in memory per guild and forgotten at READY, on an outage and on a leave; one
  channel's logs under `store.lock("VoiceLogger:status:<id>")`; the audit log read raw through
  `Route`, entries of another status left out; `guild.fetch_member`), `_post` through
  `bot.get_partial_messageable` (a 404 forgets the listen channel), `on_guild_remove` and
  `check_guilds` (keys that are not guild IDs skipped with a warning). Reuse:
  `plugin_fakes.gateway` and `parsers`, `FakeRest.answers` and its recorded `params`,
  `FakeGuild.members` and `fetch_member`, `FakeInteraction.guild_id` and `channel_id`,
  `FakeVoiceChannel.jump_url`, the `channels` fixture (partial messageables), a dataclass fixture
  (`Scene`) when a test needs more than five fixtures, and the gateway probe (skill step 7).
  Its settings, store, menu, posts and READY checks moved into `xincord.plugins.listen_channels`
  with port-chat-logger.
- **ChatLogger** (`xincord.plugins.chat_logger`, `INTENTS = discord.Intents(guild_messages=True,
  message_content=True)`, the second privileged, en-US and zh-TW, config `log_all` and
  `retention_days`): the first plugin that stores message content and the first with a plugin
  table. The listen channel code it shares with VoiceLogger is `xincord.plugins.listen_channels`,
  a package without an entry point: `settings.py` (`Setting`, `detects(setting, channel_id,
  *parents)`, `targets`, `list_text`, `units`), `store.py` (`ListenSettings(store, namespace)`) and
  `menu.py` (`Menu`, `ListenChannels`: `show`, `handle`, `post`, `check_guilds`); both cogs keep
  their command group, `show_settings` and `handle`. `messages.py` keeps `ChatLogger_messages` in
  the core store through `Store.run` (B8 settled: one table in `data/xincord.db`, v3's columns plus
  the guild and the channel); `text.py` (`message_text`: the content and the rich embeds; `fit`:
  1024 UTF-16 code units; a member's embeds are previews and left out); `created.py`
  (`parse_created`: a new message from the `MESSAGE_CREATE` payload that `setup` relays, because
  `on_message`'s cached `Message` takes later edits in place); `logs.py` (`Place.of`,
  `author_values`, `unknown_author`, `message_url`); `cog.py`: `on_gateway_message_create` (its
  insert registers in `inserting`, and the edits and deletions of that message wait for it),
  `on_raw_message_edit`, `on_raw_message_delete`, `on_raw_bulk_message_delete` (a gone or
  refusing listen channel is tried once per purge: `ListenChannels.post` returns it), the
  retention loop (started after the checks of a ready bot; `prune` at READY and hourly, `sleep`),
  `on_guild_remove` and `check_guilds` (the shared check asks Discord about uncached IDs, so
  archived threads stay). Reuse: `tests/support/payloads.py`, `plugin_fakes.add_guild`, `gateway`
  and `burst` (frames parsed together, listeners as concurrent tasks), the `scene` fixture, a
  `config` fixture that tests parametrize by name, `Hours` for a loop's sleep and
  `discord_fakes.server_error()`.
- **Giveaway** (`xincord.plugins.giveaway`, no intents, en-US and zh-TW plus a new `text.yaml` per
  locale holding the texts v3 wrote in Kotlin, config `defaultLocale`, `autoDrawIntervalSeconds`
  and the new `timeZone` as pydantic aliases): the first plugin with state between interactions, a
  scheduled job and random draws. Pure modules: `model.py` (`Draft`, `Instance`, v3's Moshi JSON
  through `parse_instance` / `instance_json`, `draw_winners` with an injected generator, the
  transitions `join` and `draw` returning an outcome and the new instance, `new_id`), `times.py`
  (Java's `yyyy-MM-dd HH:mm` SMART parse in a zone), `inputs.py` (Kotlin's trim, `toIntOrNull`,
  `java.net.URI`'s http check, UTF-16 `clip`), `drafts.py`, `texts.py` (`language`: one locale per
  message; `Texts`; the preview, post embed and buttons, `result`). `store.py`: `Giveaways`, v3's
  documents per guild, every change a pure transition under `store.lock("Giveaway:<guild>")`,
  `draw_due`. `cog.py`: drafts per user and guild with the builder message's ID, updated through
  each interaction (`response.edit_message`, modal submissions too); the confirmation takes the
  draft before its first await and gives it back on any failure; post presses defer at once, then
  show the stored post with `edit_original_response` and reply with ephemeral follow-ups; the
  automatic draw (READY + 5 s, then each period) stores before it posts through partial
  messageables; `on_guild_remove` drops drafts only. Reuse: `scene.who(...)`, `Ticks`,
  `GatedChannel` and the `plugin_modules` autouse fixture (`tests/plugins/giveaway/`),
  `FakeInteraction.original`, `FakeChannel.send` returning a `FakeMessage` with `jump_url`,
  `FakeChannel.get_partial_message`, and the script check that every `text.yaml` fragment is in the
  Kotlin sources.
- **Still to build:** the plugins after Giveaway (section 5).

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`, `core-components-v2`, `core-component-ids`, `core-plugin-loading`,
`core-command-tree`, `core-component-routing`, `core-interaction-values`, `core-startup`,
`core-reload`, `core-console`, `core-status-log`, `container`, `port-example`,
`port-basic-calculator`, `port-auto-role`, `port-bot-info`, `port-simple-command`,
`port-welcome-bye-guild`, `port-interval-pusher`, `port-feedbacker`, `port-economy`,
`port-dynamic-voice-channel`, `port-voice-logger`, `port-chat-logger`, `port-giveaway`. Each one's
`design.md` in
`openspec/changes/archive/` records its decisions and "v3 behaved differently" notes;
`docs/porting-guide.md` has the differences table.

### Next: the plugins

Core is complete; _Example (the template), BasicCalculator, AutoRole, BotInfo, SimpleCommand,
WelcomeByeGuild, IntervalPusher, Feedbacker, Economy, DynamicVoiceChannel, VoiceLogger, ChatLogger
and Giveaway are ported. Next: **Ticket** (`port-ticket`).
The owner renamed several plugins on 2026-10-10 (_Example -> Example, BasicCalculator ->
Calculator, SimpleCommand -> CustomCommands, WelcomeByeGuild -> WelcomeGoodbye, IntervalPusher ->
UptimeHeartbeat, Feedbacker -> Feedback, TicketAddons -> TicketAwayNotice, NtustManager ->
NtustAnnouncements, NtustCourse -> NtustCourseWatch): a port of a renamed plugin uses the new name
for the entry point, `plugins/<Name>/`, the store namespace, the component ID namespace, the
package and the capability, and keeps the v3 legacy prefixes. As of `port-giveaway` the ported
ones still carry their v3 names in the repository.
Port the plugins in C1 order with the `port-plugin` skill (`.claude/skills/port-plugin/SKILL.md`),
one OpenSpec change each (`port-<plugin-kebab>`): _Example (done), BasicCalculator (done),
AutoRole (done), BotInfo (done, with the configurable AGPL source link of C3), SimpleCommand
(done), WelcomeByeGuild (done), IntervalPusher (done), Feedbacker (done), Economy (done),
DynamicVoiceChannel (done), VoiceLogger (done), ChatLogger (done), Giveaway (done), then Ticket,
TicketAddons, NtustManager, NtustCourse, MusicPlayer (with Lavalink in `compose.yaml`).
Update `docs/porting-guide.md` after each one.

### Working tips from this session

- Template tests that check rendered views must be `async`: a discord.py view created outside a
  running event loop never reports `is_finished()`.
- Core plugin tests use `FakePlugins` (`tests/support/plugin_fakes.py`, on the pytest and pyright
  paths) through the `fake_plugins` fixture in `tests/core/conftest.py` and the `store` fixture in
  `tests/conftest.py`: it writes plugin packages to a temporary `sys.path` entry and builds entry
  points; their `calls` list survives reloads. Discovery and `load_extension` both execute a plugin
  module. Real plugins load with `plugin_fakes.load_plugin` (see the port-plugin skill).
- Startup tests (`tests/core/test_startup.py`) patch `importlib.metadata.entry_points` and
  `Bot.start`, `chdir` into `tmp_path`, and send real signals with `signal.raise_signal`: the
  handlers that `run` installs turn them into `bot.close()`.
- discord.py component objects for fakes can be built from payloads (`discord.ActionRow(payload)`,
  `discord.Container(payload, None)`); `View.from_message` only reads `message.components`.
- An xfail stub for a new schema field: a property that raises `NotImplementedError` keeps pyright
  happy until the field exists.
- Test commands with `app_commands.Command(name=..., callback=...)` in a typed factory: decorated
  module-level commands are partially unknown to pyright.
- Docker: the CLI uses the OrbStack context; the engine is usually stopped. Ask before `orb start`,
  and `orb stop` afterwards. `docker compose run --rm -T bot --no-online` checks an image without a
  token; `docker compose down -v` removes the test volume.
- Run the gate and check its exit status directly. Piping it into `tail` before `&&` once hid a
  failure and let a bad commit through (it was amended before pushing).
- OpenSpec is not installed globally: `OPENSPEC_TELEMETRY=0 npx --yes @fission-ai/openspec@1.14.1
  <command> </dev/null`. Telemetry is also off in `~/.config/openspec/config.json`.
- Per change: propose, `validate --strict`, commit; xfail and implementation commits; porting-guide
  rows; push; `gh run watch <id> --exit-status`; `archive <name> --yes`; `validate --all --strict`;
  commit; push.

## 6. Open items for the owner

Answered on 2026-10-10: the license is `AGPL-3.0-or-later` (set in both `pyproject.toml` files;
the owner still adds LICENSE); OpenSpec stays on npx; the user-visible changes listed before were
accepted. For `core-startup` the owner chose: `--no-online` checks and exits; logs go to stderr
only (no log file). For `core-reload`: English copy for `/xincord`, and a full reload unloads the
plugins removed from the list. The `core-console`, `core-status-log` and `container` behavior was
accepted as listed. Still open: a run with a real token under compose (step 3 of the manual check
in `openspec/changes/archive/2026-10-10-container/design.md`).

From the plugin ports on, the owner asked for pushes without waiting for review: each port lists
its user-visible changes, the choices made without the owner and the manual checks in
`docs/porting/owner-review.md`, which the owner reviews afterwards.

1. **Review (pushed in core-plugin-loading):** plugins are enabled in the core `config.yaml`
   (`plugins: [AutoRole, ...]`) instead of each plugin's `enabled` key, and the migration script
   fills that list; plugins that are not enabled no longer create files under `plugins/<Name>/`;
   the privileged members intent is requested only when an enabled plugin needs it.
2. **Production version (F1)** is unknown; it matters only if a data migration is ever needed.
   The local copy (`XsDiscordBotKt/Server/`) runs Economy 3.2.1, whose wallets are the legacy
   single `plugins/Economy/data/data.json`; Economy reads no v3 file until that migration exists.
3. **ChatLogger** needs the Message Content intent turned on in the developer portal before the
   operator enables it, or Discord refuses the bot's connection; B8 was settled as one table in
   the shared store (see `docs/porting/owner-review.md`).
4. **Lavalink image** (arm64, compose details): verify when MusicPlayer starts. **VoiceLogger
   status events** were built in port-voice-logger (the core relays the gateway event; the audit
   log is read raw); what needs a real guild is in `docs/porting/owner-review.md`.
5. **Giveaway's time zone:** before cutover, set `timeZone: "Asia/Taipei"` in
   `plugins/Giveaway/config.yaml` (or `TZ` in `compose.yaml`): the container's zone is UTC, so typed
   end times would be read 8 hours off. v3's running giveaways are not migrated (B11).

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
- After an entry point is added to `packages/xincord-plugins/pyproject.toml`, `uv run` reinstalls
  the editable package; `uv.lock` does not change.
- uv_build wheels include the package's data files. Without Docker, check packaging with
  `uv build --package xincord-plugins` and `xincord --no-online` from a scratch venv holding both
  wheels.
- Tests must not unload or reload a real plugin: discord.py re-imports its modules and later tests'
  `isinstance` checks fail. A `setup` that raises (an invalid config) also drops the plugin's
  modules from `sys.modules`; tests that load bad files look the cog up with `cast`, and so does
  the plugin's `cog` fixture, because the tests that run after them get the new classes.
- A conditional expression on one line (`{} if bot is None else ...`) adds no branch for coverage;
  the plugins' `client.user is None` fallbacks stay on one line, so branch coverage stays at 100%.
- discord.py's `Bot.add_listener` (every cog listener) calls the deprecated
  `asyncio.iscoroutinefunction`; `pyproject.toml` ignores that DeprecationWarning from `discord.`
  modules in pytest, which otherwise turned it into a failed plugin load.
- `bot.dispatch` needs a bot that logged in (`Client.loop` is a sentinel before), and so does
  `bot.wait_until_ready()`; tests await listeners with `plugin_fakes.dispatch`.
- `str.splitlines()` also splits at U+0085 and U+2028: split JSONL with `split("\n")`. Kotlin's
  `isWhitespace()` is `str.isspace()` without U+0085.
- ruff S105 reports names like `token` compared with or assigned a string; rename them.
- Some v3 resources have CRLF line endings; git stores LF but the copied working file keeps CRLF.
- A stub whose annotations use `discord` keeps the import under `TYPE_CHECKING` until code uses it
  at runtime, or ruff's TC rules fail the gate.
- Python 3.14 accepts `except A, B:` without parentheses, and ruff formats it that way.
- ruff's TRY400 wants `logger.exception` for `logger.error` inside `except` (`# noqa: TRY400`
  where a traceback is noise), and TRY401 refuses the exception object in `logger.exception`.
- Removing a test module's last xfail marker can leave `pytest` used in annotations only: ruff's
  TC002 then wants it under `TYPE_CHECKING` (`ruff check --fix --unsafe-fixes` moves it), and
  TC004 wants it back at runtime when a marker returns.
- `Store.update` writes its function's result even when nothing changed, and stores `null` for a
  missing key when the function returns None: changes that may find nothing to do use
  `store.lock` with `get`, `put` and `delete` (DynamicVoiceChannel's `store.py`).
- Without the project's hooks, run `ruff check --fix` before `ruff format`: a fix that removes an
  import leaves a blank line that only the formatter removes, and the gate's format check fails.
- ruff counts pytest fixtures as arguments (PLR0913, PLR0917: at most five); bundle them in a
  dataclass fixture (VoiceLogger's `Scene`).
- `field(default_factory=list[X])` evaluates `X` when the dataclass is created: for a class defined
  later in the module, pass a small factory function (`discord_fakes._no_members`).
- aiohttp's `RawTestServer.close()` waits for the requests still in flight: answer them first, or
  the teardown waits for the client's timeout (`http_fakes.Monitor.close`). Autouse fixtures are
  torn down after the fixtures a test requests.
- `asyncio.CancelledError` is a `BaseException`: `except Exception` leaves cancellation alone.
  Kotlin's `catch (e: Exception)` caught `CancellationException`.
- Remove xfail markers with a script that matches the decorator's parentheses: a `sed` range
  from `@pytest.mark.xfail(` to the next `^)$` also swallowed a following `parametrize`.
- ruff's S608 refuses SQL built with f-strings: keep plugin SQL in module constants; SQLite's
  `DELETE` takes no `LIMIT` (not compiled in), so delete a batch through a subquery of IDs.
- `pytest.mark.parametrize` with a fixture's name overrides that fixture for the test, also where
  other fixtures request it (ChatLogger's `config` fixture, read by `bot`).
- A task's output file under the session's `tasks/` directory is a symlink: watch it with
  `stat -L`.
- An interaction probe records HTTP by replacing `discord.http.HTTPClient.request` and
  `discord.webhook.async_.AsyncWebhookAdapter.request` (callbacks must return
  `{"interaction": {"id": ...}}`); `discord.Interaction(data=...)` needs `attachment_size_limit`
  in the payload; `await bot.tree._call(interaction)` runs a command's whole path.

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
  `on_member_join` builds the member from the event (no member cache needed), but discord.py drops
  a join for an uncached guild or an already cached member.
- `member.add_roles(role)` is atomic by default: one `PUT .../roles/{id}` per role, keeping the
  other roles; `atomic=False` sends one PATCH computed from the cache. discord.py sends without
  JDA's client-side checks; `Role.is_assignable()` makes them.
- With the members intent, discord.py chunks every guild before `on_ready`
  (`chunk_guilds_at_startup` follows the intent). An unavailable guild (outage) is cached without
  roles or members, so `guild.me` is None there.
- `Guild.member_count` stays current only with the members intent (discord.py updates it from
  member join and leave events); it is None for a guild unavailable since the bot connected.
  `Client.guilds` keeps unavailable guilds; JDA's guild list left them out.
- A command sends `contexts` and `integration_types` only when it sets `allowed_contexts` and
  `allowed_installs`, and Discord's defaults apply otherwise; JDA always sent the guild and bot DM
  contexts and guild installs, which ported global commands set explicitly.
- `create_text_channel(overwrites=...)` does not copy the category's overwrites as JDA does.
- `tasks.loop` schedules from each start; there is no REST ping (time `GET /users/@me`).
- `app_commands.Command(callback=cog.method)` unwraps the bound method and makes the cog the
  command's binding (`cog_app_command_error` and the cog's `interaction_check` apply).
  `app_commands.rename(...)` and `describe(...)` also work on a built `Command`. discord.py
  evaluates the callback's annotations when the command is built, so `import discord` stays at
  runtime; ruff's non-strict TC rules accept a move into `TYPE_CHECKING` while other `discord`
  imports remain, and only the plugin's tests catch it.
- Unloading an extension removes the tree commands whose callback module belongs to it
  (`_remove_with_module`), including commands added in `setup` with `bot.tree.add_command`.
- `interaction.response.edit_message(view=...)` keeps the message's content and embeds.
  `Embed.to_dict()` adds `type` and `flags`.
- Components V2 classes exist: `LayoutView`, `Container`, `Section`, `TextDisplay`, `Thumbnail`,
  `MediaGallery` (`discord.MediaGalleryItem`), `Separator` (`SeparatorSpacing`), `File`,
  `ActionRow`; buttons take `sku_id`.
- `send` and the interaction edits close a message's `File` objects when they finish, even when
  Discord refused the request (`MultipartParameters.__exit__`): render again before sending the
  message elsewhere. An unclosed `discord.File` in a test fails it
  (`PytestUnraisableExceptionWarning`).
- `Messageable.send` overloads take `view: View` with content and embeds, or `view: LayoutView`
  without them; `View | LayoutView | None` matches none. `isinstance` against a Protocol keeps each
  member of `interaction.channel`'s union with its own overloads (and pyright reports an unsafe
  overlap): pass the channel as `object` first (SimpleCommand's `_postable`).
- `app_commands.default_permissions(administrator=True)` also applies to a built `Command`; the
  payload's `default_member_permissions` is then the integer 8.
- A `discord.TextChannel` option annotation sends `channel_types` [0, 5] (announcement channels
  too) and resolves the channel from the cache; a `Transformer` with `channel_types` [text] over
  `AppCommandChannel` sends [0] and takes what Discord resolved. `Transform[...] | None` works as an
  optional parameter. discord.py's `TextChannel` also stands for announcement channels: check
  `.type`.
- `Thread.category` raises `ClientException` when the parent channel is not cached, which
  `getattr(..., None)` does not catch; `interaction_values` handles it now.
- In a guild, `interaction.guild` is never None: discord.py builds a placeholder guild (no channels,
  name `''`) when it has not cached the guild. `interaction.guild_locale` and
  `interaction.permissions` come straight from the payload; the guild owner and administrators
  get every permission there.
- `on_raw_member_remove` is dispatched for every removal, even for an uncached guild; its `user` is
  the cached `Member` when there was one. JDA ignored the bot's own removal.
- At `on_ready`, `Client.guilds` holds every guild of READY, unavailable ones included (READY adds
  them before their GUILD_CREATE), so stored data of other guilds belongs to guilds the bot left.
- `wait_until_ready` raises until `login` or `async with bot` creates the READY event; the
  `--no-online` check enters `async with bot`, so loops wait for a READY that never comes, and
  `Bot.close` unloads the extensions (running `cog_unload`) before it closes the HTTP client.
- `HTTPClient.request(Route(...))` is the REST call behind discord.py's methods; it retries a 500,
  502, 504 or 524 (and a reset connection) up to five times, sleeping 1 + 2 x tries seconds, then
  raises `DiscordServerError`.
- A `discord.Member` option annotation raises a `TransformerError` before the callback when
  Discord resolved no member (a user outside the guild), leaving the deferred response
  "thinking"; `discord.Member | discord.User` passes the user instead.
- `defer()` on a modal submission sends a deferred message update (type 6); `followup.send(...,
  ephemeral=True)` still reaches the user afterwards. discord.py sends a text input inside a
  `Label` with `"label": null`.
- Discord refuses an embed field with an empty name or value; JDA sent U+200E (the core does now).
- `View.from_message` raises `ValueError` for a Components V2 message: use
  `LayoutView.from_message` when `message.flags.components_v2`.
- After a handler deletes the message of a v3 ID, the core's legacy upgrade cannot fetch it and
  logs an error (a v3-opened Feedbacker modal submitted after the switch).
- `app_commands.describe(...)` applied to a built `Command` gives every option it does not name
  an ellipsis as its description: call it once with all the options (`rename` leaves the others).
- A component interaction's `data` carries `component_type` (2 for a button); a modal
  submission's has none.
- pyright widens `dict[str, JSON] | {...}` beyond `dict[str, JSON]`; annotate the merged document
  (`updated: dict[str, JSON] = {**entries, key: value}`) before returning it from a
  `Store.update` function.
- A probe can log in offline: point `discord.http.Route.BASE` at a local server and call
  `bot.http.static_login(token)` inside `async with bot`; set `bot._ready` for READY.
- `on_voice_state_update` fires for mutes, deafens and streams too (JDA's `GuildVoiceUpdateEvent`
  only for channel changes): compare the channels' IDs. `channel.voice_states` counts a voice
  channel's members without the member cache; `VocalGuildChannel.members` needs it.
- discord.py runs listeners as tasks: the gateway events parsed before one runs, or while it
  awaits, are already in the cache it reads. Read what decides the handling before the first
  await, and check again under a lock before acting (a probe parsed a join and a leave before the
  listeners ran, and the join's listener saw the member gone).
- `GuildChannel.edit(position=...)` renumbers every channel of the guild in the channel's sorting
  bucket (voice and stage channels together), and `move(...)` those of its category, in one bulk
  `PATCH /guilds/{id}/channels` from the cached positions; JDA's `setPosition` sent the raw
  position in `PATCH /channels/{id}` (`Route` keeps it).
- `VocalGuildChannel.clone()` copies the overwrites as they are, and the NSFW flag, the video
  quality and the slowmode, which JDA's `createCopy` did not; it adds the copy to the guild's cache.
  `Guild._create_channel` (behind `create_*_channel(overwrites=...)`) sends an `Object(type=Role)`
  key as a member overwrite; `edit` gets it right.
- A bare `app_commands.Group(...)` takes its `module` from the frame that creates it: build it in
  the plugin's module, so that unloading the plugin removes it.
- `AsyncWebhookAdapter.request` gets `session` as a keyword: a probe's replacement must accept it.
- discord.py 2.7.1 drops `VOICE_CHANNEL_STATUS_UPDATE` (no parser: "Unknown event" at debug level)
  and has no `VoiceChannel.status`; its `AuditLogAction` lacks 192 and 193, so `AuditLogEntry` names
  them `unknown_192`, gives no `target` and drops their `options`. `ConnectionState.parsers` is the
  table that `DiscordWebSocket.received_message` looks events up in, the same dictionary for every
  connection. Discord documents (2026-04-20) that voice statuses are not part of channel objects.
- `on_voice_state_update`'s `after` is the cached voice state, updated in place by later events
  (`before` is a copy): a join and a leave parsed before the listener runs reach it as no change.
- `interaction.response.edit_message(...)` keeps what it is not given: `embeds=()` and `view=None`
  clear them, as JDA's `MessageEditData.fromCreateData` replaced the whole message.
- A scratch probe can drive real discord.py objects offline: set `bot._connection.user` to a
  `ClientUser`, build `discord.Interaction(data=..., state=bot._connection)` and call
  `command._invoke_with_namespace(...)` (patch `Interaction.edit_original_response`); set
  `bot.loop`, add a guild with `state._add_guild_from_data(...)` and call `state.parse_*` for
  gateway events (patch `Messageable.send`).

- discord.py makes a message's author a `Member` only when the payload's `member` has every field
  that `Member` reads, `flags` included; `Message.__init__` swallows the `KeyError` and keeps a
  `User`.
- discord.py's own parsers dispatch through the connection state's `dispatch`, bound when the
  client was created; patching `bot.dispatch` does not catch them (`plugin_fakes.gateway` patches
  both). `ConnectionState._add_guild_from_data` caches a guild from a `GUILD_CREATE` payload
  (`plugin_fakes.add_guild`).
- A message of a guild that discord.py has not cached has no `guild`; one of an uncached channel
  has a `PartialMessageable` channel. `Embed.from_dict` gives `type` None when the payload has none.
- `on_message` gets discord.py's cached `Message`, and a `MESSAGE_UPDATE` parsed before the
  listener runs changes it in place: discord.py parses the frames that arrived together without
  yielding (a scratch probe stored the edited text and lost the edit's log). Read a new message
  from the relayed `MESSAGE_CREATE` payload (`relay_gateway_event` works for events that
  discord.py parses too), and let a message's later events wait for its handling.
- discord.py drops archived threads from its cache: an uncached ID is not proof that a channel
  was deleted (`bot.http.get_channel` answers 404 for deleted ones).
- `git worktree add --detach` gives a scratch checkout for work that must not disturb a reviewer
  reading the main tree; the project's hooks do not run there (`core.hooksPath` is relative), so
  run the gate and `scripts/check_commit_msg.py` by hand, and fast-forward `main` afterwards.
- Requesting the privileged message content intent without the developer portal's permission makes
  Discord close the gateway (4014); the bot does not connect.
- A failed plugin load makes discord.py drop the plugin's modules; the next load imports new
  classes, and frozen dataclasses from the old and the new modules never compare equal: an autouse
  fixture that puts the plugin's `sys.modules` entries back after each test keeps one set
  (Giveaway's `plugin_modules`).
- `response.edit_message` answers a modal submission with type 7 when the modal came from a
  message's button; after a component's `response.defer()`, `edit_original_response` edits the
  component's message (both seen in Giveaway's probe).
- `bot.get_partial_messageable(c, guild_id=g).get_partial_message(m).edit(...)` edits a message
  without fetching it, in any channel kind.
- `datetime.fromtimestamp(ts, zone)` raises when the UTC time is past 9999, even when the zone's
  wall time is not; `strftime("%Y")` does not pad years below 1000 everywhere; a naive
  `datetime(1, 1, 1).timestamp()` raises `ValueError`.
- `zoneinfo` keys are case-insensitive on macOS (its file system) and case-sensitive on Linux. The
  python slim image ships tzdata (`ZoneInfo("Asia/Taipei")` works there); the container's own zone
  is UTC.
- `Store.put` encodes the value with `json.dumps` on the event loop: a very large document delays
  other handlers; acknowledge interactions before waiting for the store.
- ruff's PLR0913 counts keyword-only arguments too; test modules cannot import `conftest` at runtime
  (importlib mode), so a fixture's method builds its dataclasses (`scene.who(...)`).
- With OrbStack running, `docker compose build` and `docker compose run --rm -T bot --no-online`
  with a temporary `bot/config.yaml` check an image; `docker compose down -v` and removing `bot/`
  clean up.

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions.

**Exact numbers (BasicCalculator):** `decimal` defaults to 28 digits, and `Fraction` reduces with a
gcd that costs 75 to 180 ms per operation at 100,000 digits; scaled integers (v3's `BigDecimal`)
cost a few milliseconds. Python refuses `str()`/`int()` conversions over 4,300 digits and computes
`10**999999999` if asked: bound sizes first.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
