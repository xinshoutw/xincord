# Architecture

How xincord is built: the core, the plugin conventions and each port, as recorded while porting
(moved from `HANDOFF.md` on 2026-10-12). Each archived change's `design.md` holds the decisions.

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
    the default `resources/config.yaml`. YAML syntax errors give the line and the column without
    PyYAML's snippet of the line, which could hold a secret (since port-ntust-announcements).
    `xincord.core.migrate_v3` converts the v3 core config, lists the plugins whose v3 config had
    `enabled: true` (renamed ones under their new names,
    `RENAMED`), moves each renamed plugin's v3 directory to its new name and, last, sets aside as
    `config.v3.yaml` the v3 `config.yaml` of a `SET_ASIDE` plugin (CustomCommands) that held only
    `enabled` (`python -m xincord.core.migrate_v3 <dir>`).
  - `xincord.core.storage`: `Store` over one SQLite connection on one worker thread; JSON values by
    namespace and key; `update` (atomic read-modify-write), `run` (plugin tables), `lock(key)`.
    `run` rolls back when the commit itself fails (another connection's lock held past
    `BUSY_TIMEOUT`, 5 s), since `chat-logger-split-storage`.
  - `xincord.core.i18n`: `export_lang`, `Lang.load` (locales, flattened YAML keys, Discord name
    rules, key-set warnings), `Lang.text` / `Lang.template` (fallback), `Lang.localization` (no
    fallback), `Lang.command` and `Translator`; `is_command_name` (Discord's name rules: letters,
    numbers, `-`, `_`, `'`, the Devanagari and Thai scripts) and `localized(default,
    translations)`, a command string that `Translator` resolves from its own table (no fallback),
    since `custom-commands-from-config`. `Lang.parsed` keeps what is parsed from the files once.
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
    (`load_message`, `load_modal`, `Templates.load`, which parses a `Lang`'s templates once) and
    rendered to `Message(content, embeds, view, files)` and `discord.ui.Modal`. V2 mode renders a
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
    `required_intents`; `PluginContext` (`directory`, `store`, `data_directory` = `<data>/<Name>/`
    for files a plugin keeps itself, never created by the core, `config(Model)`, `lang(locale)`;
    `reads` keeps what those returned, which a `replaying()` copy hands back).
  - `xincord.core.bot.Bot(commands.Bot)`: created from the discovered plugins with their intents,
    `root` (`plugins/`) and the required keyword `data` (the plugins' data directories);
    `load_plugins()` (isolated failures, dependents skipped), `plugin_context(__name__)` for a
    plugin's `setup(bot)`, `load_plugin(info)` (hot load: refuses new intents or missing
    dependencies), `reload_plugin(name)` (with dependents; on a failure discord.py sets the
    previous version up again, and `plugin_context` gives it a replaying context while the
    plugin's modules are out of `sys.modules`, so that the config, lang and templates that broke
    the new version cannot break it; when it fails anyway, `_drop` unloads it with its modules and
    dependents, the reload uploads the commands, and a full reload loads them again; a plugin whose
    entry point moved fails its reload), `route(__name__, ids, handler)` and `on_interaction`,
    which sends component and
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
    `run(options)` loads `config.yaml`, opens `data/xincord.db` (`DATA / "xincord.db"`; the bot
    gets `DATA`, `data/`, for the plugins' data directories), discovers `CoreConfig.plugins`
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
    application commands ephemerally unless `extras["defer"]` is False; `payloads(guild_id=None)`
    splits guild commands from `extras["global"]` ones (translated when a translator is set) and,
    for a guild, leaves out the guild commands whose `extras["guilds"]` lists other guilds (each
    guild gets its own payload);
    `sync_global(store)` / `sync_guild(store, guild_id, force=)` upload only when the payload's
    SHA-256 changed (stored in the `core` namespace) and log failures.
    Component and modal IDs come from a `build_id(uid_map)` callable the plugin passes in. Views
    and modals are stopped before they are returned, so discord.py never dispatches their
    interactions; the core will route them (Core change `command-tree`).
- **Deployment (`container`):** `Dockerfile` (two stages on `python:3.14.8-slim-trixie`, uv 0.12.24,
  `uv sync --locked --no-dev --all-packages --no-editable`, user `xincord` in `/bot`, entry point
  `xincord`), `.dockerignore`, and `compose.yaml` (service `bot`: `./bot` bind-mounted at `/bot`,
  named volume `data` = `xincord_data` at `/bot/data`, `stdin_open`, `tty`, `init`,
  `restart: unless-stopped`, 30 s stop grace, json-file logs 10 MB x 3). Since port-music-player,
  service `lavalink` (`ghcr.io/lavalink-devs/lavalink:4.2.2`, `lavalink/application.yml`
  read-only with youtube-source 1.18.2 and LavaSrc 4.8.3 pinned, `LAVALINK_SERVER_PASSWORD` from
  `LAVALINK_PASSWORD` in an untracked `.env` (`.env.example` holds an example; `${VAR:?}` makes
  every compose command need it), Spotify from `.env`, a `curl` healthcheck of `/version`, no
  published port, no member's query in its logs); the bot `depends_on` it with
  `condition: service_started`.
- **Plugins (`packages/xincord-plugins`):** `xincord.plugins.example` (entry point `Example`, v3's
  _Example), the template: `__init__.py` (metadata constants, `setup`), `config.py`, `cog.py`
  (commands built in `setup` from the Lang with the cog's bound method as callback, `IDS =
  ComponentIds("example", ("action", "count"))` routed with `bot.route`), bundled `config.yaml` and
  `lang/`. Conventions for every port: `.claude/skills/port-plugin/SKILL.md`. Reuse in tests:
  `plugin_fakes.load_plugin` (real entry point, offline), `plugin_fakes.golden(<package>)`,
  `tests/support/discord_fakes.py` (`FakeInteraction` records `sent`; `buttons`, `embed_dict`); the
  `store` fixture is in `tests/conftest.py`. The example's `placeholder_values` moved into
  `xincord.core.placeholders` with WelcomeGoodbye.
- **Calculator** (v3 BasicCalculator; `xincord.plugins.calculator`, no config): `calculator.py` is
  a pure evaluator with v3's shunting-yard pass and `BigDecimal` results (`BigDecimal(unscaled,
  scale)`), v3's defects fixed and size limits; `cog.py` runs it in `asyncio.to_thread`, posts the
  answer to the channel (`_post`: a `runtime_checkable` `Postable` protocol, fallback to the
  deferred response on `discord.HTTPException`) and edits errors into the deferred response.
  Reuse: `discord_fakes.FakeChannel`, `forbidden()` and `delete_original_response`; the golden
  pattern for recorded v3 answers with an independent evaluator
  (`tests/plugins/calculator/test_golden.py`).
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
- **CustomCommands** (v3 SimpleCommand; `xincord.plugins.custom_commands`, no intents, zh-TW
  templates, config `commands` since `custom-commands-from-config`): `config.py` models each entry
  (`CommandSpec`: `name`, checked by discord.py's `validate_name` and `is_command_name`;
  `description`; `localizations` per Discord locale; `template`, by default the name;
  `permissions` by discord.py's flag names, by default `administrator`, `[]` for everyone; `reply`:
  `channel`, `public` or `ephemeral`; `guilds`), and `commands` is required: the bundled file holds
  v3's five with their zh-TW names (`register.yaml` is gone). `checks.py` raises one `ConfigError`
  for what needs several entries or the lang files: names unique in every locale, the room left of
  Discord's 100 commands, and templates that exist in zh-TW and render once at load (no `uid`,
  `model_key`, missing file or sixth row). `cog.py`: `command(spec)` (`localized` names,
  `default_permissions`, `extras["guilds"]`, `extras["defer"] = False` for a public reply);
  `post_message` posts in the channel (v3's way, with the fallback into the deferred response),
  defers publicly and edits, or edits the ephemeral deferral in the user's locale, with
  `placeholder_values`, and deletes a response that Discord refuses. The bundled templates hold
  the example account number `000000000000`. Reuse: `Operator` (`tests/plugins/custom_commands/
  conftest.py`: an operator's templates and config, then a load), the `plugin_modules` fixture for
  tests that reload the real plugin (`test_reload.py`), `checks.check` for config checks across
  entries, `FakeInteraction(edit_error=...)`, and `ClosingChannel` (`test_post.py`) for
  discord.py's closed files.
- **WelcomeGoodbye** (v3 WelcomeByeGuild; `xincord.plugins.welcome_goodbye`, `INTENTS =
  discord.Intents(members=True)`, no config, en-US and zh-TW): the first plugin with data.
  `store.py` keeps v3's per-guild document (`{"welcomeChannelId", "byeChannelId"}`, 0 = unbound) in
  the key-value table under the namespace `WelcomeGoodbye` and the guild ID, read without writing
  and changed by `set_channel` under `store.lock("WelcomeGoodbye:<id>")`; `values.py` builds v3's
  `wbg@` keys from the core families (`command_values`, `member_event_values`) and checks text
  channels with a `runtime_checkable` Protocol; `cog.py` has four guild commands with two shared
  callbacks (`bind_channel`, `unbind_channel`, kind from the `COMMANDS` table), a
  `TextChannelOption` transformer that limits the option to text channels (`channel_types` [0]), the
  runtime Administrator check through `interaction.permissions`, replies in
  `interaction.guild_locale`, `on_member_join`, `on_raw_member_remove` (skips the bot's own removal)
  and `on_guild_remove`, and `forget_left_guilds` from `on_ready` and `cog_load`. Reuse: the
  per-guild data convention (skill, "Storage"), `FakeGuild(channels=..., preferred_locale=...,
  icon=..., rules_channel=...)` with `get_channel` and `as_guild()`, `FakeChannel(type=...)`,
  `FakeMember` with placeholder attributes, `FakeInteraction(guild=, guild_locale=, permissions=)`,
  `Bot.user` patched as a property, and the scratch probe through discord.py's own objects (skill
  step 7).
- **UptimeHeartbeat** (v3 IntervalPusher; `xincord.plugins.uptime_heartbeat`, no intents, no lang,
  config `listeners[].url` and `interval`): the first background loop and outgoing HTTP. `pusher.py`
  has `Pusher(number, listener, get, ping, sleep)`, v3's loop with its effects passed in (push at
  once, then `interval` seconds after each attempt; no failure ends it, a 404 included, since
  `uptime-heartbeat-keep-pushing`), `rest_ping` (times `bot.http.request(Route("GET",
  "/users/@me"))`, JDA's REST ping) and aiohttp's `open_session` and `get_status` (no redirects,
  v3's timeouts); `xincord-plugins` declares aiohttp and yarl. `logs.py` holds the owner's log
  rules: `origin(url)` (scheme, host and port, all that a line shows of a URL), `redact(text,
  *urls)` (URLs in error texts and tracebacks cut to their origin, and the listener URL's
  `private_parts` removed wherever they appear; these three live in `xincord.plugins.redaction`,
shared with Ticket since port-ticket) and `Failures` (one for the pushes, one for the
  pings: each kind of failure is logged once per episode, the rest at debug level, and an episode
  ends after three successes in a row with one info line). `config.py`'s models hide their input
  in validation errors. `cog.py` creates one task per listener in `cog_load`, each awaiting
  `bot.wait_until_ready()`, and cancels and awaits them in `cog_unload`; its `sleep` attribute is
  the loops' delay, which tests replace. Reuse:
  `plugin_fakes.Ready` (READY for offline bots; its `close` cancels the tasks left running),
  `http_fakes.running_monitor()` (`Monitor`, a local HTTP server), patching
  `discord.http.HTTPClient.request` to record REST calls, an injected `sleep` with a fake clock,
  `bot.remove_cog` to run `cog_unload` without unloading the modules, the REST probe through
  `Route.BASE` and `http.static_login` (skill step 7), and `Failures` and `redact` for any loop that
  fails repeatedly or whose URLs carry secrets (a cross-review found the gaps that the design's
  "Cross-review" lists).
- **Feedback** (v3 Feedbacker; `xincord.plugins.feedback`, no intents, en-US and zh-TW, five config
  replies, `/feedback`): the first port with v3 component IDs and a modal. `cog.py` has `IDS =
  ComponentIds("feedback", (action, user_id, star_count, submit_channel_id),
  legacy_prefix="feedbacker@")` routed to `handle`, which dispatches on the interaction type and the
  action; `create_form` (the command, with `member: discord.Member | discord.User` checked against
  `MemberLike` and a copy of WelcomeGoodbye's `TextChannelOption`), `press_star` (`form_not_you`,
  the `fill-form` modal through `render_modal` and `send_modal`, then `form.highlight` and the bot's
  own `message.edit`) and `submit_form` (`modal_values`, `response.defer()`, the review in the
  guild's locale, the form deleted only after the post, `followup.send(..., ephemeral=True)` on
  failure). `config.py` keeps v3's three required replies and adds `form_failure` and
  `form_submit_failure` (English defaults, zh-TW in the bundled file), each non-blank and at most
  2000 characters. Reuse: `discord_fakes.FakeMessage` (edits and deletion into `sent`, fetched until
  deleted), `FakeResponse.send_message` and `send_modal`, `FakeInteraction.followup`, `not_found()`,
  route tests through `bot.on_interaction` with v3 IDs (`tests/plugins/feedback/test_routes.py`),
  and the HTTP-recording probe for interactions (skill step 7).
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
  message_content=True)`, the second privileged, en-US and zh-TW, config `log_all`,
  `retention_days` (1826, 5 years) and `max_file_size_mb` (256)): the first plugin that stores
  message content and the first with files of its own.
  The listen channel code it shares with VoiceLogger is `xincord.plugins.listen_channels`, a package
  without an entry point: `settings.py` (`Setting`, `detects(setting, channel_id, *parents)`,
  `targets`, `list_text`, `units`), `store.py` (`ListenSettings(store, namespace)`) and `menu.py`
  (`Menu`, `ListenChannels`: `show`, `handle`, `post`, `check_guilds`); both cogs keep their command
  group, `show_settings` and `handle`. Since `chat-logger-split-storage`, the stored messages are in
  `data/ChatLogger/messages-<UTC second>.db` (`context.data_directory`; no file before the first
  message): `files.py` names the files and routes an ID to the one whose range holds it (`route`,
  `next_start`, `expired`); `messages.MessageFiles` keeps one connection per file on a thread of
  its own (`open` in `cog_load`, `close` in `cog_unload` after the work under way and shielded from
  cancellation, every method one job, each job's work in a file one `transaction` that rolls back a
  failed commit), starts a new file after the newest stored ID once the newest file's page count
  reaches the limit (built as `.tmp` and renamed closed; one error per failing episode), and
  `prune` deletes expired files whole, then older rows in batches; `setup` drops the old
  `ChatLogger_messages` table of `data/xincord.db`. The design of that change describes how to
  import v3's message files (an empty directory, copies of v3's files, a merge of sorted cursors),
  which the one-off migration at cutover follows (section 5). `text.py` (`message_text`: the
  content and the rich embeds; `fit`: 1024 UTF-16 code units; a member's embeds are previews and
  left out); `created.py` (`parse_created`: a new message from the `MESSAGE_CREATE` payload that
  `setup` relays, because `on_message`'s cached `Message` takes later edits in place); `logs.py`
  (`Place.of`, `author_values`, `unknown_author`,
  `message_url`); `cog.py`: `on_gateway_message_create` (its insert registers in `inserting`, and
  the edits and deletions of that message wait for it), `on_raw_message_edit`,
  `on_raw_message_delete`, `on_raw_bulk_message_delete` (a gone or refusing listen channel is tried
  once per purge: `ListenChannels.post` returns it), the retention loop (started after the checks
  of a ready bot; `prune` at READY and hourly, `sleep`), `on_guild_remove` and `check_guilds` (the
  shared check asks Discord about uncached IDs, so archived threads stay). Reuse:
  `tests/support/payloads.py`, `plugin_fakes.add_guild`, `gateway` and `burst` (frames parsed
  together, listeners as concurrent tasks), the `scene` fixture, a `config` fixture that tests
  parametrize by name, `Hours` for a loop's sleep, `discord_fakes.server_error()`, the `load`
  fixture (unloads what a test loaded, closing its files), `write_file` (a message file as an
  earlier run left it), `plugin_fakes.unclosed()` (leaked connections as an assertion) and
  `MessageFiles` for any plugin whose data is kept for years.
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
- **Ticket** (`xincord.plugins.ticket`, no intents, no config, en-US and zh-TW plus `text.yaml`):
  the first plugin that creates channels for members, sets overwrites and posts through webhooks.
  Pure modules: `model.py` (`Draft`, `Entry`, `Controls`, v3's Moshi entry, colors), `drafts.py`
  (defaults and the builder's changes), `texts.py` (`Texts`, `units`, `clip`, `chunks`,
  `readable_error`), `tickets.py` (`category_of`, `can_copy` = JDA's `trySync`, `overwrites`,
  `opener`), `views.py`. `store.py`: `Panels`, v3's `{"<message ID>": [entry, ...]}` per guild,
  appended under the guild's lock after a `place` callback puts the button on the message (and
  takes it off again when the store fails). `targets.py` (the `/add-ticket` checks), `archive.py`
  (thread, webhook, forwarding, flattening, failures over Protocols in `channels.py`),
  `controls.py` (`ControlRow`: lock, unlock, delete, save and its select; since
  `ticket-staff-controls`, the owner's request, the four buttons share one check, `_staff`, for
  the entry's staff roles or Administrator, @everyone left out of a member's roles (`_role_ids`),
  and `_refuse` answers the others before any request to Discord: v3's acknowledgement for a user
  who is no member, else `error.not-found` or `error.admin-only`, ephemerally; the labels are the
  owner's `control.*`), `ids.py`, `cog.py`
  (commands, builder sessions per user and guild with the builder message's ID, confirmation,
  tickets, routes, left guilds). A changed draft is kept only once Discord took the builder that
  shows it (`_screen`). Channel names are the member's username, TicketAwayNotice's contract
  (the archived design, "Channel names"). Reuse: `xincord.plugins.redaction`, the overwrite map
  of `tickets.overwrites`, the webhook pattern of `archive.py`, `discord_fakes.FakeCategory`,
  hashable `FakeMember`, `bad_request()`, `button_rows()`, the scene's `click` and `refuse_edit`.
- **TicketAwayNotice** (v3 TicketAddons; `xincord.plugins.ticket_away_notice`, `INTENTS =
  discord.Intents(members=True, presences=True)`, both privileged, zh-TW `message/not-online.yaml`
  only, config `guild_id`, `user_id`, `prefix`, `delay_millis` without defaults; the bundled file
  holds 0 for both IDs, so the plugin waits for the operator): the first plugin that reads members'
  statuses and the first with delayed work started by an event. `config.py`'s `Config.watches` is
  the pure filter (the guild, case-sensitive prefixes); `cog.py`: `on_guild_channel_create` and
  `on_thread_create` call `watch`, which checks without awaiting, keeps the channels that take
  messages (`Postable`, a Protocol with `send`) and skips the bot's own threads (Ticket's archives),
  then starts a notice task kept in `notices`; the task checks `_due` (the channel and the guild
  still cached, the owner offline: the cache, else `fetch_member`, whose member has no presence and
  reads offline), waits on the cog's `sleep`, checks `_due` again and posts `not-online` in the
  default locale with `global_values`, logging what it does not handle with `logger.exception`.
  `cog_unload` sets `closed` (a listener that discord.py scheduled before the unload starts nothing)
  and cancels the notices; `check()` from `on_ready` and `cog_load` in a ready bot warns about a
  missing guild or owner; `check_notice` in `setup` refuses a template that can never be posted (a
  `uid`, more than ten embeds, an empty message). Numbers in `prefix` read as text, as v3's kaml
  did. Reuse: the scene's `Clock` (an injected `sleep` that waits until the test wakes it), the
  gateway scene through discord.py's parsers with `FakeRest` answering `POST
  /channels/{id}/messages`, `payloads.guild(members=, presences=)`, `payloads.presence`,
  `payloads.channel(guild_id=)`, and `FakeRest`'s `form` for uploads.
- **Plugin names** (`rename-plugins`): the six ported plugins that the owner renamed carry their new
  names everywhere but the inventories, Kotlin citations, legacy component ID prefixes and
  placeholder keys (porting guide, "Plugin names"); `migrate_v3.RENAMED` maps all nine v3 names,
  and TicketAwayNotice, NtustAnnouncements and NtustCourseWatch were ported under their new names.
  Reuse: the capability rename recipe and the image check with every plugin (section 7).
- **NtustAnnouncements** (v3 NtustManager; `xincord.plugins.ntust_announcements`, no intents, no
  lang, config `fetch-interval`, `api-keys`, `prompt` (v3's keys), `boards`, `model` and, since
  `ntust-announcements-model-config` (the owner's request), every model setting: `api-format`
  (`gemini` or an OpenAI-compatible `openai`), `endpoint`, `temperature`, `max-output-tokens`,
  `request-timeout`, `connect-timeout`, `rate-limit`, `rate-window`, `max-attempts` and
  `retry-waits`, v3's values by default, applied by a reload; the bundled file holds v3's prompt,
  v3's example key and v3's 18 boards with 0 for every channel, so the plugin waits for the
  operator): the first plugin that scrapes pages and calls an LLM. Pure modules: `markup.py` (a
  tree over `html.parser`: omitted end tags in tables and lists, the implied `tbody`, v3's
  selectors, jsoup's `text()`, a serializer), `pages.py` (v3's three layouts, `complete_url`
  keeping v3's exact URL strings, `is_article`, the container, v3's minifier with `re.ASCII`),
  `strings.py` (Kotlin's `trim`, importing nothing of the plugin), `messages.py` (v3's header and
  split in UTF-16 code units, title links escaped and cut), `api.py` (`ApiFormat`, `Api`: each
  format's URL, key header and body from the settings, null settings left out; `answer_text`,
  `error_message`), `conversion.py` (was `gemini.py`: `fill_prompt` in one pass, `Limits`,
  `KeyRing`, `backoff`, `Converter.convert` with the configured attempts and waits, `hide`
  cutting URLs to their origins and removing the endpoint's path and the keys), `store.py` (v3's
  `TypedListWrapper` per board under namespace `NtustAnnouncements`, `remember` keeping up to 100
  links that left the page). `config.py` builds `Config.api` and `Config.limits`; validators that
  read another key are field validators declared after it, the numbers are strict (YAML's `yes` is
  no 1) and the endpoint is read with yarl, as aiohttp reads it. `web.py`: aiohttp, pages through
  `xincord.plugins.ntust_tls.ntust_context` (Python 3.13+'s `VERIFY_X509_STRICT` refuses NTUST's
  certificates; `web.page_context` until port-ntust-course-watch moved it), the model's request
  from the `Api` with its timeouts. Log lines name no product; a READY line names the format, the
  model and the endpoint's origin. `watch.py`:
  `Watcher`, one board's passes (posted links stored after each post, failures retried at the next
  pass, unconvertible articles posted as title links, `Failures` per step; since the cross-review,
  refused messages wait in `ready` so that the model converts an article once, links posted while
  the store refused them wait in `delivered`, each announcement is guarded, and pages are parsed
  in `asyncio.to_thread` with walks that need no recursion). `cog.py`: one task that
  waits for READY and runs a loop per board in a `TaskGroup`, five fetches at a time, posts through
  partial messageables without mentions, the ready check. Reuse: `xincord.plugins.failures`
  (`Failures`, moved from UptimeHeartbeat), `markup.py` (move it into a shared package when
  another plugin parses HTML), the conftest's `offline` guard (aiohttp refuses every host but this
  machine's), `FakeWeb` (its `apis` record the settings of each session, `error` fails every
  attempt), the `Clock` whose `wake` ends the waits started so far, trimmed copies of live pages
  as fixtures, and `BeforeValidator` stubs for new config keys (porting guide, "Validators that
  read other keys").
- **NtustCourseWatch** (v3 NtustCourse; `xincord.plugins.ntust_course_watch`, no intents, en-US
  default locale holding v3's English with zh-TW translations, config `semester`, `start`,
  `interval` and `alert-interval` with v3's values as defaults, so v3's file loads): the first
  plugin that watches items that members register on an external API. Pure modules: `courses.py`
  (`course_code`: NFKC, trimmed, upper case, 9 to 20 letters and digits, since the course query
  matches codes as prefixes; `request_text`, the course query site's body for one code;
  `read_course`, the answer's last entry for the code; `to_int_or_none`, Kotlin's `toIntOrNull`
  over a whole Int and BMP digits; v3's `isFull`), `store.py` (`Registrations`: v3's document
  `{code: {channel: [user]}}` under namespace `NtustCourseWatch` and key `user_record_map`, codes
  read as `/course-add` reads them, changed under one lock with `get` and `put`, deleted with its
  last registration), `texts.py` (`text.yaml` in one pass, the list reply cut to fit) and
  `alerts.py` (`Alerts`: the throttle per channel and course and the full alerts owed; v3's alert
  texts split between their mentions, 100 users a post at most). `web.py`: `POST
  .../QueryCourse/api//courses` over aiohttp with the shared NTUST TLS context. `watch.py`:
  `Watcher.step`, one registered code per step in sorted turn, nothing before `start` or with
  nothing registered, a course's state kept over a failed or empty answer, failures once per code,
  kind and episode. `cog.py`: the three guild commands, one task from READY stepping every
  `interval` seconds (a done callback logs an error that ends it), posts as tasks through partial
  messageables with `AllowedMentions` for the members, a 404 forgetting the channel. Reuse:
  `xincord.plugins.ntust_tls` (NTUST's TLS context, moved from NtustAnnouncements), the scene's
  `Clock` (a wake moves the fake clocks on), `FakeApi`, and `scene.steps(n)`, which fails at once
  when the loop died.
- **MusicPlayer** (`xincord.plugins.music_player`, `INTENTS = discord.Intents(voice_states=True)`,
  zh-TW default with en-US, config `lavalink` (host, port, a required string password, hidden in
  errors; the bundled file waits for it), v3's `player.default_volume`, `player.auto_leave_timeout`
  (now applied; 0 never), `messages.show_detailed_errors` and `emojis` (four new button names)):
  the first plugin that plays audio. Pure modules: `audio.py` (`Track`, `Loaded`, `EndReason` and
  the Protocols `Player`, `Listener`, `Link`), `history.py` (v3's history: a song added while idle
  starts, 240 songs with played ones dropped first, `ended(loop, failed=)`), `display.py` (v3's
  identifier rule, times, bar, thumbnails, the `music_player@` values, the bounded queue embed),
  `emojis.py` (Unicode fallbacks, `resolve`), `texts.py`. `session.py`: a guild's history on its
  player under a lock that also orders the decisions (songs without a player are refused, the
  pause toggle), a start number per song so that stale node events are dropped, `changed` for the
  idle leave. `node.py`: the only lavalink.py importer: `open_link` at READY (15-second request
  timeout), a `DefaultPlayer` subclass without its queue that reports ends and stuck songs,
  `LavalinkVoice(discord.VoiceProtocol)` (voice updates to the node, the `channelId` after a move,
  one release that tells the plugin first and leaves a newer connection alone, an earlier
  connection's late leave ignored), `leave_lost` (READY again) and `close` leaving voice.
  `panels.py`: one self-refreshing panel per member (5 s, deleted 60 s after its last interaction,
  a press renews it). `replies.py`, `commands.py` (the eleven commands, the autocompletes,
  `cog_app_command_error`), `buttons.py` (v3's `musicplayer@` IDs and the new ones) and `cog.py`
  (READY, the emojis, the idle leave, `on_guild_remove`, `cog_unload`). Reuse:
  `tests/support/lavalink_fakes.py` (a local Lavalink v4 node, `hold` for slow answers),
  `tests/support/music_fakes.py` (`FakeLink`, `FakePlayer` with `hold`, `FakeVoice`, `Clock` with
  `advance` and `asleep`), the scene's `who()` and `press()`, `FakeVoiceChannel.connect(cls=...)`,
  `FakeGuild.voice_client` and `change_voice_state`, `FakeMember.voice`,
  `FakeInteraction.delete_error` and `delete_gate`, `FakeResponse.autocomplete`.
- **Still to build:** the owner's follow-up changes (section 5), then the cutover (C2).
