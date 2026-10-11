# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-11 after `port-ntust-announcements`, the sixteenth plugin port (v3 NtustManager:
NTUST's announcement boards read from READY, new articles converted by Gemini and posted to
configured channels; the first plugin that scrapes HTML and calls an LLM API), which followed
`port-ticket-away-notice` (v3 TicketAddons: a notice in new ticket channels while the shop's owner
is offline, the first plugin with the presences intent), `port-ticket` (ticket panels, ticket
channels with their overwrites, and archives through webhooks), `chat-logger-split-storage`
(the owner's third follow-up change: ChatLogger keeps 5 years of messages by default in its own
SQLite files under `data/ChatLogger/`; with it, a data directory per plugin in the core and a core
fix that rolls back a failed commit), `custom-commands-from-config`,
`uptime-heartbeat-keep-pushing`, `rename-plugins` (the owner's plugin renames) and
`port-giveaway`.
Core is complete. Read this file first, then `docs/porting/decisions.md` and `AGENTS.md`. The
decisions are accepted and binding; do not re-open them unless you find a serious problem, and then
ask the owner.

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
| Calculator golden data | `docs/porting/analysis/inventory/fixtures/*.jsonl` |
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
- List user-visible changes (copy, commands, interaction flow) for the owner in
  `docs/porting/owner-review.md`; pushes do not wait for the owner's review (section 6).

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
  `restart: unless-stopped`, 30 s stop grace, json-file logs 10 MB x 3).
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
  `ChatLogger_messages` table of `data/xincord.db`. The design of that change plans the import of
  v3's message files (`xincord migrate`: an empty directory, copies of v3's files, a merge of
  sorted cursors). `text.py` (`message_text`: the content and the rich embeds; `fit`: 1024 UTF-16
  code units; a member's embeds are previews and left out); `created.py` (`parse_created`: a new
  message from the `MESSAGE_CREATE` payload that `setup` relays, because `on_message`'s cached
  `Message` takes later edits in place); `logs.py` (`Place.of`, `author_values`, `unknown_author`,
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
  `controls.py` (`ControlRow`: lock, unlock, delete, save and its select), `ids.py`, `cog.py`
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
  and TicketAwayNotice and NtustAnnouncements were ported under their new names. Reuse: the
  capability rename recipe and the image check with every plugin (section 7).
- **NtustAnnouncements** (v3 NtustManager; `xincord.plugins.ntust_announcements`, no intents, no
  lang, config `fetch-interval`, `api-keys`, `prompt` (v3's keys), `boards` and `model`; the bundled
  file holds v3's prompt, v3's example key and v3's 18 boards with 0 for every channel, so the
  plugin waits for the operator): the first plugin that scrapes pages and calls an LLM. Pure
  modules: `markup.py` (a tree over `html.parser`: omitted end tags in tables and lists, the
  implied `tbody`, v3's selectors, jsoup's `text()`, a serializer), `pages.py` (v3's three layouts,
  `complete_url` keeping v3's exact URL strings, `is_article`, the container, v3's minifier with
  `re.ASCII`, Kotlin's `trim`), `messages.py` (v3's header and split in UTF-16 code units, title
  links escaped and cut), `gemini.py` (`fill_prompt` in one pass, `KeyRing`, `backoff`,
  `Gemini.convert` with v3's ten attempts), `store.py` (v3's `TypedListWrapper` per board under
  namespace `NtustAnnouncements`, `remember` keeping up to 100 links that left the page).
  `web.py`: aiohttp, pages through `page_context` (Python 3.13+'s `VERIFY_X509_STRICT` refuses
  NTUST's certificates), Gemini's REST `generateContent` with the key in a header. `watch.py`:
  `Watcher`, one board's passes (posted links stored after each post, failures retried at the next
  pass, unconvertible articles posted as title links, `Failures` per step; since the cross-review,
  refused messages wait in `ready` so that Gemini converts an article once, links posted while
  the store refused them wait in `delivered`, each announcement is guarded, and pages are parsed
  in `asyncio.to_thread` with walks that need no recursion). `cog.py`: one task that
  waits for READY and runs a loop per board in a `TaskGroup`, five fetches at a time, posts through
  partial messageables without mentions, the ready check. Reuse: `xincord.plugins.failures`
  (`Failures`, moved from UptimeHeartbeat), `page_context` and `markup.py` (move them into shared
  packages when NtustCourseWatch needs them), the conftest's `offline` guard (aiohttp refuses every
  host but this machine's), `FakeWeb`, the `Clock` whose `wake` ends the waits started so far, and
  trimmed copies of live pages as fixtures.
- **Still to build:** the plugins after NtustAnnouncements and the owner's follow-up changes
  (section 5).

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`, `core-components-v2`, `core-component-ids`, `core-plugin-loading`,
`core-command-tree`, `core-component-routing`, `core-interaction-values`, `core-startup`,
`core-reload`, `core-console`, `core-status-log`, `container`, `port-example`,
`port-basic-calculator`, `port-auto-role`, `port-bot-info`, `port-simple-command`,
`port-welcome-bye-guild`, `port-interval-pusher`, `port-feedbacker`, `port-economy`,
`port-dynamic-voice-channel`, `port-voice-logger`, `port-chat-logger`, `port-giveaway`,
`rename-plugins`, `uptime-heartbeat-keep-pushing`, `custom-commands-from-config`,
`chat-logger-split-storage`, `port-ticket`, `port-ticket-away-notice`,
`port-ntust-announcements`. Each one's
`design.md` in
`openspec/changes/archive/` records its decisions and "v3 behaved differently" notes;
`docs/porting-guide.md` has the differences table.

### Next: the plugins

Core is complete; Example (the template), Calculator, AutoRole, BotInfo, CustomCommands,
WelcomeGoodbye, UptimeHeartbeat, Feedback, Economy, DynamicVoiceChannel, VoiceLogger, ChatLogger,
Giveaway, Ticket, TicketAwayNotice and NtustAnnouncements are ported. Next: **NtustCourseWatch**
(`port-ntust-course-watch`, v3 NtustCourse, `docs/porting/analysis/inventory/NtustCourse.md`): a
course-seat watcher with slash commands that polls NTUST's course query API (`POST
https://querycourse.ntust.edu.tw/QueryCourse/api//courses`) about every 1.5 seconds and posts to the
channels that registered a course when it has seats; C1 moves its hard-coded semester and go-live
time into config. Its host's certificate fails Python's strict X.509 checks like NTUST's other
hosts (checked on 2026-10-11): move NtustAnnouncements' `web.page_context` into a shared package
and use it there. Its loop follows NtustAnnouncements' (a task from READY,
`xincord.plugins.failures` for repeated failures, the conftest's `offline` guard in its tests).
The owner renamed nine plugins on 2026-10-10 (`docs/porting/decisions.md`, Amendment 1; the table
in `docs/porting-guide.md`, "Plugin names"), and `rename-plugins` applied the renames to the ported
ones. A port of a renamed plugin uses the new name for the entry point, `plugins/<Name>/`, the
store namespace, the component ID namespace, the package, the capability and the change
(`port-ticket-away-notice`, `port-ntust-announcements`), and keeps the v3 name in the legacy
prefix; the inventories and the Kotlin sources keep the v3 names.
Port the plugins in C1 order with the `port-plugin` skill (`.claude/skills/port-plugin/SKILL.md`),
one OpenSpec change each (`port-<plugin-kebab>`): Example (done), Calculator (done),
AutoRole (done), BotInfo (done, with the configurable AGPL source link of C3), CustomCommands
(done), WelcomeGoodbye (done), UptimeHeartbeat (done), Feedback (done), Economy (done),
DynamicVoiceChannel (done), VoiceLogger (done), ChatLogger (done), Giveaway (done), Ticket (done),
TicketAwayNotice (done, v3 TicketAddons), NtustAnnouncements (done, v3 NtustManager), then
NtustCourseWatch (v3 NtustCourse), MusicPlayer (with Lavalink in `compose.yaml`). Update
`docs/porting-guide.md` after each one.

The owner also asked for follow-up changes (section 6). Done: UptimeHeartbeat logs URLs as origins
only and never stops a listener (`uptime-heartbeat-keep-pushing`); CustomCommands defines its
commands in its config file (`custom-commands-from-config`); ChatLogger keeps 5 years by default in
its own files, starting a new file when one grows too large (`chat-logger-split-storage`). Not
started yet: the v3 data import (`xincord migrate`) before cutover, which must read a renamed
plugin's v3 data from `plugins/<new name>/` once `migrate_v3` moved it (or from both places), write
the new store namespaces (`WelcomeGoodbye`), and import ChatLogger's message files as
`chat-logger-split-storage`'s design plans ("Migration").

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
- Docker: the CLI uses the OrbStack context. The owner allows Claude to start OrbStack and use it
  (2026-10-10); never `orb stop`. `docker compose run --rm -T bot --no-online` checks an image
  without a token; `docker compose down -v` removes the test volume.
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

Answered on 2026-10-10 (afternoon), from the review queue (the answered items were deleted there):

- **BotInfo:** `source_url` keeps its default, `https://github.com/xinshoutw/xincord`. The
  repository stays private until the port is finished; then the owner makes it public.
- **IntervalPusher:** failure logs will show only the host, and a failed push will never stop a
  listener (it keeps pushing at its interval). Both come in a follow-up change. Done in
  `uptime-heartbeat-keep-pushing` (2026-10-10), with a log policy chosen there and listed in the
  review queue: a failure is logged when it starts or changes kind, then once when pushing works
  again.
- **BasicCalculator:** the defect fixes and the answers they change are accepted (negation after
  an operator, `^` grouping from the right, integer exponents, division by zero, negative
  exponents), and so is the golden-test approach.
- **SimpleCommand:** the commands will be defined in the config file, with as much customization
  as practical (a follow-up change). The example account number is accepted, and so is copying
  v3's `lang/` files (with the real account numbers) into the plugin's directory at cutover. Done
  in `custom-commands-from-config` (2026-10-11); its choices are in the review queue.
- **WelcomeByeGuild:** binding the welcome and bye channels again at cutover is accepted, and so
  are the two zh-TW typo fixes.
- **Feedbacker:** `form_failure`, `form_submit_failure` and their copy are accepted.
- **Server Members intent:** enabled in the developer portal.
- **OrbStack:** Claude may start it and use it.
- **ChatLogger:** the message log keeps 5 years by default and moves to its own files, starting a
  new file automatically when the current one grows too large (a follow-up change). This replaces
  the shared-table answer to B8 and the 30-day default (`decisions.md`, Amendment 3). Done in
  `chat-logger-split-storage` (2026-10-11); its choices are in the review queue.
- **Data:** a v3 data import (`xincord migrate`, with a dry run and per-plugin counts) is built
  before cutover, covering Economy's wallets and the other data worth keeping, such as channel
  bindings. This reverses the deferral of Resolution 3 and B11 (`docs/porting/decisions.md`,
  "Amendments").
- **Plugin names:** _Example becomes Example, BasicCalculator Calculator, SimpleCommand
  CustomCommands, WelcomeByeGuild WelcomeGoodbye, IntervalPusher UptimeHeartbeat, Feedbacker
  Feedback, TicketAddons TicketAwayNotice, NtustManager NtustAnnouncements and NtustCourse
  NtustCourseWatch. This reverses B18's "display names and `plugins/<Name>/` keep the original
  names" for these plugins (`docs/porting/decisions.md`, "Amendments").
- **Pushes** go on without prior review; everything the owner should see goes to the review queue.

1. **Review (pushed in core-plugin-loading):** plugins are enabled in the core `config.yaml`
   (`plugins: [AutoRole, ...]`) instead of each plugin's `enabled` key, and the migration script
   fills that list; plugins that are not enabled no longer create files under `plugins/<Name>/`;
   the privileged members intent is requested only when an enabled plugin needs it.
2. **Production version (F1)** is unknown. The v3 data import must handle the local copy
   (`XsDiscordBotKt/Server/`), which runs Economy 3.2.1: its wallets are the legacy single
   `plugins/Economy/data/data.json`, which v3.4 would have moved into the only guild's file, and
   the import must do the same. Economy reads no v3 file until the import exists. `migrate_v3`
   counts a plugin as enabled only with `enabled: true`, a key v3 added in 3.3.0 (`ea14fbf`), so
   on a 3.2.x directory its `plugins` list is almost empty (found in `rename-plugins`' review).
3. **ChatLogger** needs the Message Content intent turned on in the developer portal before the
   operator enables it, or Discord refuses the bot's connection.
4. **Lavalink image** (arm64, compose details): verify when MusicPlayer starts. **VoiceLogger
   status events** were built in port-voice-logger (the core relays the gateway event; the audit
   log is read raw); what needs a real guild is in `docs/porting/owner-review.md`.
5. **Giveaway's time zone:** before cutover, set `timeZone: "Asia/Taipei"` in
   `plugins/Giveaway/config.yaml` (or `TZ` in `compose.yaml`): the container's zone is UTC, so typed
   end times would be read 8 hours off. Whether v3's running giveaways come along is up to the v3
   data import.
6. **Ticket** (review queue, "Ticket"): whether ticket channels should take a `ticket-` prefix so
   that TicketAwayNotice's default prefixes match them; the Message Content intent for the archive;
   `TZ` for the archive's times; the v3 data import before anyone uses `/add-ticket` on v3 panels
   (until then a new button takes index 0, the v3 button's, and both open the new entry).
7. **TicketAwayNotice** (review queue, "TicketAwayNotice"): the Presence intent must be allowed in
   the developer portal before the plugin is enabled, or Discord refuses the bot's connection; at
   cutover, `guild_id` must be the shop's guild, since the guild filter now applies (the READY check
   names a wrong one).

8. **NtustAnnouncements** (review queue, "NtustAnnouncements"): at cutover, run the v3 data
   import (`current_announcement_lists` from v3's MongoDB, design "Storage and the v3 data
   import") before enabling the plugin, or its first pass posts every board's first page; add
   `boards` with the 18 channel IDs to the migrated `plugins/NtustAnnouncements/config.yaml`;
   `{{now}}` is UTC in the container unless `TZ` is set.

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
  overlap): pass the channel as `object` first (CustomCommands' `_postable`).
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
  logs an error (a Feedback modal that v3 opened, submitted after the switch).
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
  clean up. With every ported plugin enabled, Economy needs `bot/plugins/Economy/config.yaml` with
  an example `admin_id`, or the check exits 1.
- OpenSpec 1.14.1 cannot rename a capability: ADD the requirements to the new one (the delta's `##
  Purpose` seeds its spec), REMOVE them from the old one with a reason and a migration, and set
  `retire_capabilities: true` in the change's `.openspec.yaml`, so that `archive` deletes the
  emptied spec instead of refusing it. A requirement's header changes through RENAMED
  (`FROM:`/`TO:`) plus MODIFIED under the new header. A trial archive in a detached worktree shows
  the result first.
- `git mv` of a package leaves its untracked `__pycache__` behind, and the old directory then
  imports as a namespace package: delete it after the move.
- zsh expands a word that starts with `=` as a command's path (`echo =====` fails with "not
  found"): quote such separators.
- CI's `astral-sh/setup-uv` step is pinned by SHA but has no `version` input, so it installs the
  newest uv (0.13.0 on 2026-10-10, before this session's changes too), and `uv sync` warns that
  `uv_build>=0.12.24,<0.13` does not include it; the gate still passes.
- aiohttp 3.14.4's error texts name the whole URL: `ConnectionTimeoutError` (`Connection timeout to
  host <url>`), a malformed answer's `ClientResponseError` (`..., url='<url>'`, without the user
  info, after the server's bad line, which can be the request line sent back) and
  `InvalidUrlClientError`; `ServerDisconnectedError` carries the partial answer; a refused
  connection or a failed DNS lookup names `host:port` only, and the 30-second total limit raises a
  bare `TimeoutError`. Redact URLs that carry secrets out of such texts before logging them
  (UptimeHeartbeat's `redact`) and format tracebacks yourself: `logger.exception` prints the text
  as it is.
- pydantic's `ValidationError` text shows each invalid input (`input_value=...`, up to about 50
  characters), and the core logs it chained to its `ConfigError`: a model with secrets sets
  `ConfigDict(hide_input_in_errors=True)` (merged with `Model`'s config) and fixed messages.
- ruff's BLE001 accepts `except Exception` only when the handler re-raises or logs with
  `logger.exception` or `exc_info`; a handler that logs a redacted traceback as text needs
  `# noqa: BLE001`.
- PyYAML's syntax errors quote a snippet of the faulty line (about 30 characters after the error),
  and the core's `ConfigError` passes it on, so a URL on that line can show in the log.

- discord.py's `reload_extension` sets the previous version up again when the new one fails, and
  that setup reads the plugin's files again; it runs while the plugin's modules are out of
  `sys.modules` (2.7.1), which the core uses to hand it a replaying context. When it fails too,
  discord.py leaves nothing registered and the core must forget the plugin (`_drop`).
- discord.py's `validate_name` refuses an apostrophe, which Discord takes, and its pattern ends in
  `$`, so a final line break passes it; Discord then refuses the guild's whole upload. Discord's
  names take letters, numbers, `-`, `_`, `'` and the Devanagari and Thai scripts
  (`is_command_name`).
- discord.py's command tree holds at most 100 commands in its global table, and the core keeps
  every plugin's commands there (guild lists are a filter of each guild's upload): a 101st, or a
  name that another plugin took first, fails the plugin that loads second.
- A deferred response keeps the deferral's flags: after the command tree's ephemeral defer, no
  reply can be public; a public reply opts out (`extras={"defer": False}`) and defers itself.
- `default_member_permissions`: None lets every member use a command; `Permissions(0)` leaves it to
  administrators.
- A `WeakKeyDictionary` whose values reference their keys never drops an entry; keep data that is
  derived from an object with the object (`Lang.parsed`).
- A scratch pytest file outside the repository runs with the project's settings through `uv run
  pytest -c pyproject.toml --rootdir=. <file>` from the repository root.

- Python 3.13+ `sqlite3` warns (`ResourceWarning`) when it collects a connection that nothing
  closed; under `filterwarnings = error` the warning becomes an unraisable warning that fails
  whichever test runs then, after the call phase that xfail watches. A cancelled task keeps its
  exception, whose traceback keeps frames and their locals (the object that holds the connections)
  alive. Assert `plugin_fakes.unclosed() == []`, or record the connections and check each:
  `connection.total_changes` raises `ProgrammingError` on a closed connection, from any thread.
- A commit that cannot get its lock (another connection reading past `timeout`, 5 s by default)
  raises and leaves the write transaction open; the next commit on that connection applies it.
  Commit inside the `try` that rolls back (`Store.run`, ChatLogger's `transaction`).
- Cancelling the await of `loop.run_in_executor(...)` cancels the job if it has not started:
  submit a job that must run with `executor.submit` and await it through `asyncio.shield`.
  `ThreadPoolExecutor.shutdown(wait=False)` still runs the jobs queued before it.
- SQLite names a file's journal after the path its connection opened: rename a database file only
  while no connection has it open. `PRAGMA page_count` times `page_size` is the file's size in
  constant time; deleted rows leave free pages that only `VACUUM` gives back.
- discord.py's `Cog._inject` runs `cog_load` before anything else and does not call `cog_unload`
  when `cog_load` raises: a `cog_load` that opens resources closes them itself on failure. A setup
  that fails after `add_cog` makes discord.py remove the cog, which runs `cog_unload`.
- `docker compose run --rm -T -v <script>:/probe.py:ro --entrypoint python bot /probe.py` runs a
  scratch script in the image as uid 1000 against the named volume (`docker compose down -v`
  afterwards).

- `TextChannel.create_thread(name=...)` without a message creates a private thread unless
  `type=discord.ChannelType.public_thread` is given (JDA's `createThreadChannel(name)` was public).
- `InteractionResponse.edit_message` marks the response done only after Discord answered: when it
  raises `HTTPException`, `response.send_message` still answers (Ticket's refused drafts).
- `View.from_message` gives each item its row and `add_item` appends to `children`; `to_components`
  sorts by row when sending, so check the payload's order.
- A `@dataclass` with `eq=True` is unhashable: a fake used as an overwrite key needs `__hash__`
  (`FakeMember`). `discord.Object(id, type=discord.User)` hashes and compares equal to the member.
- `Guild._create_channel` sends an `Object(type=Role)` key as a member overwrite; drop such keys
  when copying a category's overwrites. Without the members intent only the bot's member is
  cached: `guild.get_member` misses and `fetch_member` costs a request.
- `Attachment.to_file()` downloads through `HTTPClient.get_from_cdn` (patch it in probes) and reads
  the whole file into memory; a recorded webhook answer needs whole attachment objects.
- `Message.edit()` sends `suppress_embeds` as its `suppress` argument, False by default: the core's
  upgrade of v3 IDs shows embeds that were suppressed.
- Discord refuses a webhook message's username with `@`, `#`, `:`, three backticks, `discord` or
  `clyde`, `everyone` or `here`, or over 80 characters; a string option takes up to 6000
  characters, a reply at most 2000.

- With the presences intent, discord.py does not chunk a guild that is not large: its
  `GUILD_CREATE` carries the members and their presences (`_guild_needs_chunking`); large guilds are
  chunked without presences. `PRESENCE_UPDATE` updates cached members only, so a plugin that reads
  statuses declares the members intent too. A member from `fetch_member` has no presence:
  `member.status` is `Status.offline`, as JDA's default.
- `on_thread_create` fires only for a `THREAD_CREATE` marked `newly_created`; a thread that the bot
  did not cache otherwise arrives as `on_thread_join`.
- `Messageable.send` builds a `Message` from Discord's answer: a REST recorder that answers `{}`
  makes it raise `KeyError`, so tests give `FakeRest.answers` a message payload per post.
- `Cog._eject` removes the cog's listeners before it calls `cog_unload`, and logs instead of raising
  what `cog_unload` raises: a stub there cannot fail a test with `raises=NotImplementedError`. A
  listener that discord.py scheduled as a task before the unload still runs afterwards on the old
  cog: a cog that starts work from listeners sets a `closed` flag in `cog_unload` (TicketAwayNotice,
  found in its cross-review).
- A thread that the bot starts reaches `on_thread_create` like any other; `thread.owner_id` names
  its creator (Ticket's archive threads take the ticket channel's name).
- `Templates.load` already refuses a static `color_code` that is not a color; only a rendered one (a
  placeholder) fails at render time, where a load-time render with no values catches a `uid` or a
  `model_key` that the plugin cannot give.
- An image check or `xincord --no-online` with every plugin enabled needs example values in
  `plugins/Economy/config.yaml` (`admin_id`), `plugins/TicketAwayNotice/config.yaml` (`guild_id`,
  `user_id`) and `plugins/NtustAnnouncements/config.yaml` (a key other than v3's example, and every
  `channel-id`), whose bundled files wait for the operator.

- Python 3.13+ adds `VERIFY_X509_STRICT` to `ssl.create_default_context()`, which aiohttp uses:
  NTUST's hosts (`student`, `www.academic`, `lc`, `querycourse`) fail it with `Missing Subject Key
  Identifier`, in the image too (OpenSSL 3.5.7); clear only that flag for them. The academic host
  also leaves out TWCA's intermediate (`unable to get local issuer certificate`): the package
  ships it (`twca-secure-ssl-ca.pem`, until 2030-10-16) and `ntust_announcements.web.page_context`
  loads it.
- pydantic's `min_length` on a list counts the items that validated: invalid items also read as an
  empty list. Check emptiness in an after-validator.
- `monkeypatch.setattr("pkg.module.name", ...)` walks the attributes from the top package, which
  can reach a stale module after discord.py executed a plugin's package again; patch
  `importlib.import_module("pkg.module")`. A test that loaded NtustAnnouncements into a ready bot
  once reached NTUST that way; its conftest now refuses every host but 127.0.0.1 (`offline`).
- aiohttp's `ClientConnectorError` shows its `OSError`'s `strerror`: raise `OSError(errno, text)`
  in fakes, or the text reads `[None]`.
- Java's `\s` is ASCII and its multiline `^`/`$` also break at `\r`, U+0085, U+2028 and U+2029;
  jsoup's `text()` collapses spaces, tabs, line breaks and no-break spaces, drops U+200B and U+00AD
  and separates blocks and `br` (NtustAnnouncements' `markup.py` and `pages.minify`).

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions, guild filters that never applied, and delayed messages that nothing could cancel or check
again (the porting guide has the full list).

**Exact numbers (Calculator):** `decimal` defaults to 28 digits, and `Fraction` reduces with a
gcd that costs 75 to 180 ms per operation at 100,000 digits; scaled integers (v3's `BigDecimal`)
cost a few milliseconds. Python refuses `str()`/`int()` conversions over 4,300 digits and computes
`10**999999999` if asked: bound sizes first.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
