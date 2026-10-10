---
name: port-plugin
description: Port one XsDiscordBotKt plugin to xincord following the project's OpenSpec and xfail-first rules. Use when starting or continuing the port of a named plugin (for example "port AutoRole").
---

# Port a plugin

Work on one plugin at a time, in the order of decision C1. Follow `AGENTS.md` throughout. The
template is Example: `packages/xincord-plugins/src/xincord/plugins/example/`, its tests in
`tests/plugins/example/` and its archived change `openspec/changes/archive/*-port-example/`. Copy
its shape and the conventions below. Fix this skill when reality differs; the newest port wins.

Names: `<Plugin>` is the plugin's xincord name (`AutoRole`, `Example`), `<kebab>` its kebab case
(`auto-role`, `example`) for the change, the capability `plugin-<kebab>` and the commit scope,
`<package>` the Python package (`auto_role`, `example`). The owner renamed nine plugins
(`docs/porting/decisions.md`, Amendment 1; the table in `docs/porting-guide.md`, "Plugin names"):
the two not ported yet are NtustManager (NtustAnnouncements) and NtustCourse (NtustCourseWatch).
Their inventories, Kotlin sources and legacy component ID prefixes keep the v3 name; everything
else, the store namespace and the new ID namespace included, uses the new one, and
`xincord.core.migrate_v3.RENAMED` already maps the v3 name (TicketAwayNotice, v3 TicketAddons, was
the first port of a plugin renamed before its port).

## Steps

1. **Read.** `docs/porting/analysis/inventory/<Plugin>.md` end to end, then the Kotlin files it
   cites at `XsDiscordBotKt@3a59607` (in ranges). Note every v3 defect the inventory lists.
2. **Propose.** `openspec new change port-<kebab>`, then write:
   - `proposal.md`: scope, out of scope, cited Kotlin sources.
   - `specs/plugin-<kebab>/spec.md`: one requirement per behavior, scenarios testable without
     Discord, each requirement under 500 characters.
   - `design.md`: package, config schema, storage tables, component IDs (legacy prefix and v3 field
     order), "v3 behaved differently: ..." entries, user-visible changes, manual smoke checklist.
   - `tasks.md`: resources, one xfail task and one implementation task per requirement, then
     conventions, docs and close. Requirements that one handler implements together may share a
     pair of tasks, with one xfail mark per requirement (`port-welcome-bye-guild`'s 6.1 and 6.2).
   Run `openspec validate port-<kebab> --strict`, the gate, and commit
   (`docs(plugin-<kebab>): propose port-<kebab>`).
3. **Resources.** Copy v3's `config.yaml` and lang files into the package (fix missing final
   newlines and CRLF line endings), example values only: never real IDs, account numbers or
   tokens. A list whose v3 default held real IDs or pointed at the owner's servers ships empty,
   with placeholder values in a comment (AutoRole's `guilds`, UptimeHeartbeat's `listeners` on
   `status.example.com`); when v3 required that list to be non-empty, it has no default and the
   plugin waits for the operator with the key named (Economy's `admin_id`); a template whose v3
   text held a real account number gets an all-zero example under a comment that asks the
   operator to put theirs (CustomCommands). Copy such files with a script that replaces the value,
   and check that no real number remains, instead of reading the real values.
4. **Per requirement, xfail-first.** Test (fails for the expected reason; check with
   `pytest --runxfail`) -> commit with `xfail(strict=True)` -> implement and remove the marker ->
   commit. Tick `tasks.md` in the same commits. The project's Claude Code hooks (ruff on each edit,
   the gate on stop) run only in a session started in this repository; from elsewhere, run
   `uv run ruff check --fix` and then `uv run ruff format` on the changed files before the gate (in
   that order: a fix that removes an import leaves a blank line that only the formatter removes).
5. **Wire it up.** Entry point, `setup`, command, routes: see the conventions.
6. **Golden tests.** v3's text per locale in `golden.yaml`; v3 component IDs from the inventory
   decode and upgrade to the expected new IDs (a plugin with v3 components); every shipped template
   renders in each locale. Recorded v3 answers (Calculator's JSONL) are copied unchanged; a
   record that a fixed v3 defect changes must agree with an independent implementation in the test
   (`tests/plugins/calculator/test_golden.py`), never be edited. A plugin without text,
   templates or components (AutoRole) has no golden data.
7. **Check the package.** `uv build --package xincord-plugins -o <scratch dir>` lists `config.yaml`
   and `lang/` in the wheel. Stronger: install both wheels in a scratch venv and run
   `xincord --no-online` in an empty directory whose `config.yaml` enables the plugin (a plugin
   whose bundled config waits for the operator, as Economy's `admin_id` and TicketAwayNotice's
   `guild_id` and `user_id`, needs example values in `plugins/<Plugin>/config.yaml` there and in
   the image check's `bot/`). Then drive the
   plugin once through discord.py's own objects in a scratch script (not committed): set
   `bot._connection.user` to a `discord.ClientUser`, build `discord.Interaction(data=<payload>,
   state=bot._connection)` and call `command._invoke_with_namespace(interaction, Namespace(...))`
   with `Interaction.edit_original_response` patched; for listeners, set `bot.loop`, add a guild
   with `state._add_guild_from_data(...)` and feed `state.parse_guild_member_add(...)` and the like.
   WelcomeGoodbye's probe found a core failure (threads with an uncached parent) that the fakes
   hid. A plugin that calls Discord's REST API on its own (UptimeHeartbeat's ping) logs in against a
   local server: point `discord.http.Route.BASE` at it, call `bot.http.static_login(...)` inside
   `async with bot`, run `setup_hook`, and set `bot._ready` for READY. For interactions, record
   HTTP instead of answering it: replace `discord.http.HTTPClient.request` (the bot's REST calls)
   and `discord.webhook.async_.AsyncWebhookAdapter.request` (interaction callbacks, which must
   return `{"interaction": {"id": ...}}`, follow-ups and `@original` edits), give the payload
   `attachment_size_limit`, run commands with `await bot.tree._call(interaction)` (defer,
   transformers, callback) and components and modals with `await bot.on_interaction(interaction)`
   (Feedback's probe; it checked the modal's label payload and the core's legacy upgrade). A
   plugin that writes under `data/` is checked in the image too: `docker compose run --rm -T -v
   <probe>:/probe.py:ro --entrypoint python bot /probe.py` writes into the named volume as uid 1000
   (ChatLogger's message files).
   For voice and channel work, give `_add_guild_from_data` the category and voice channels
   (`parent_id`), feed `state.parse_voice_state_update(...)` with a `member` payload, and answer the
   recorded `POST /guilds/{id}/channels` with the body plus an `id` so that `clone()` returns a
   channel (DynamicVoiceChannel's probe). A gateway event that the plugin relays goes through
   discord.py's real gateway code: build `DiscordWebSocket(socket=None, loop=...)`, set
   `_discord_parsers = state.parsers`, `_dispatch = bot.dispatch`, `_dispatch_listeners = []`,
   `_keep_alive = None` and `shard_id = None`, and await `ws.received_message(json.dumps({"op": 0,
   "s": 1, "t": <name>, "d": <payload>}))`; answer `POST /channels/<id>/messages` with a message
   payload so that a partial messageable's `send` returns (VoiceLogger's probe). Message events go
   through the same gateway code (`MESSAGE_CREATE`, `MESSAGE_UPDATE`, `MESSAGE_DELETE`,
   `MESSAGE_DELETE_BULK`), with `state.user` set to a `discord.ClientUser` and the payloads of
   `tests/support/payloads.py` (ChatLogger's probe).
8. **Document.** `docs/porting-guide.md`: differences rows, new pitfalls, convention changes. Audit
   the inventory: each behavior is a scenario with a test, or out of scope or a v3 difference in
   `design.md`, with the reason.
9. **Close.** Gate, push, CI green; `openspec archive port-<kebab> --yes`,
   `openspec validate --all --strict`; `HANDOFF.md` (sections 4, 5, 7) and the plugin's section in
   `docs/porting/owner-review.md`; commit, push, CI green.

## Conventions

### Package

```
packages/xincord-plugins/src/xincord/plugins/<package>/
  __init__.py   DEPENDS, SOFT_DEPENDS, INTENTS, DEFAULT_LOCALE (with lang files) and setup(bot)
  config.py     class Config(Model), if the plugin has settings
  cog.py        the Cog: command builders, handlers, listeners; IDS
  config.yaml   the bundled default config
  lang/<locale>/register.yaml, message/*.yaml, modal/*.yaml (if the plugin has text)
```

- Import the plugin's own modules relatively (`from .cog import Example`). Keep every file under
  800 lines: a cog with many handlers moves a group of them into a base class of its own module
  (Ticket's `controls.ControlRow`) and `IDS` into `ids.py` when several modules build IDs. Split
  `cog.py` when it grows: pure logic in its own module (tested without discord.py, as
  `calculator/calculator.py`), storage in `store.py`. Run CPU-bound work with
  `asyncio.to_thread`.
- Entry point: `<Plugin> = "xincord.plugins.<package>"` under
  `[project.entry-points."xincord.plugins"]` in `packages/xincord-plugins/pyproject.toml`. The name
  is the plugin's xincord name (see "Names"): the `plugins:` entry, the `plugins/<Plugin>/`
  directory and the log name. `uv run` reinstalls the workspace package; `uv.lock` does not change.
- `uv_build` ships every file in the package, so bundled YAML reaches the image.
- Code that two plugins share is a package under `xincord.plugins` without an entry point, which
  both import absolutely (`xincord.plugins.listen_channels`, VoiceLogger's and ChatLogger's listen
  channels: `ListenSettings`, `ListenChannels`, `Menu`; `xincord.plugins.redaction`, UptimeHeartbeat's
  and Ticket's URL redaction). Neither plugin needs the other; discord.py
  leaves the package imported when a plugin unloads, so it holds no state, and what differs is
  passed in. Each plugin builds its command group in its own module, so that unloading removes it.

### setup

```python
async def setup(bot: Bot) -> None:
    context = bot.plugin_context(__name__)  # __name__ is the entry-point module
    lang = context.lang(DEFAULT_LOCALE)
    cog = Example(context.config(Config), lang, Templates.load(lang))
    await bot.add_cog(cog)
    bot.tree.add_command(cog.command())
    bot.route(__name__, IDS, cog.count)
```

- Discovery imports the module and `load_extension` runs it again: no work at import time.
- `setup` runs before the gateway connects (without a login under `--no-online`), so the guild
  cache is empty. Work that needs guild data runs from an `on_ready` listener and from `cog_load`
  when `self.bot.is_ready()`, because a plugin reloaded into a running bot gets no `on_ready`
  (AutoRole's `check`); it skips guilds that are `unavailable` (an outage: no roles, `guild.me` is
  None). Background loops are tasks that `cog_load` creates and that await
  `bot.wait_until_ready()` first; `cog_unload` cancels and awaits them (see "Background loops and
  HTTP").
- Unloading and reloading remove the cog, the tree commands whose callback lives in the package and
  the routes; release anything else in `cog_unload`.
- `DEFAULT_LOCALE` is v3's default locale (zh-TW in every v3 plugin so far). A plugin without text
  (AutoRole) ships no `lang/`, has no `DEFAULT_LOCALE` and never calls `context.lang`.

### Config

- `class Config(Model)` with the same defaults as the bundled `config.yaml`. Keep v3's YAML keys and
  shapes so v3 files load unchanged; v3's `enabled` only logs `unknown key enabled`. A renamed key
  needs a migration in `xincord.core.migrate_v3` (none so far).
- A plugin whose only v3 key was `enabled` ships no `config.yaml` and never calls
  `context.config`.
- Validate a value that Discord would refuse at send time (a URL, a length) in the model, so that
  the plugin fails at load with the key named (BotInfo's `source_url`; Feedback's replies are
  `Annotated[str, StringConstraints(pattern=r"\S", max_length=2000)]`).
- v3 keys without a default stay required (UptimeHeartbeat's `listeners`, Feedback's replies). A
  new key is optional, so that v3's files load; a text default is English, because Python files
  hold no CJK, and the bundled file can hold the zh-TW text (Feedback's `form_failure`). A new key
  whose default only the bundled file can hold (CustomCommands' `commands`, with zh-TW names) is
  required, and `xincord.core.migrate_v3` sets aside the plugin's v3 file when it held only
  `enabled` (`SET_ASIDE`), so that the bundled one is written.
- Checks that need several entries or the lang files run in `setup` after the config loads and
  raise one `ConfigError` with a `<file>: <key>: <problem>` line per problem, as `parse_model`
  formats them (CustomCommands' `checks.py`: unique names per locale, the room left of Discord's
  100 commands, templates that exist and render once at load with no values, ID builder or
  models, their files closed).
- A failed reload sets the previous version up again with the config, lang and templates that it
  loaded (the core replays them; `Templates.load` parses a `Lang`'s templates once); other files
  are read again, and a plugin whose previous version fails too is unloaded with its dependents
  until a full reload loads them.
- Keys of a v3 feature that is not ported (Economy's Google Sheets keys, decision B12) are not
  fields: v3's files load and warn about each of them, as about `enabled`.
- v3's camelCase keys (Giveaway's `defaultLocale`, `autoDrawIntervalSeconds`) are snake_case
  fields with `Field(alias="camelCase")`; errors name the alias. A v3 `defaultLocale` is checked
  against `discord.Locale` and passed to `context.lang(...)` after the config loads; a time zone
  key is checked with `zoneinfo.ZoneInfo` (Giveaway's `timeZone`, empty for the host's).

### Storage

- `setup` passes `context.store` to the cog; the tests' `store` fixture is the same store. A
  plugin with files of its own gets `context.data_directory` too (ChatLogger's cog takes the
  context); `plugin_fakes.load_plugin` puts it beside the plugins root, under `tmp_path`.
- Per-guild data (v3's `JsonGuildFileManager`, `plugins/<Name>/data/<guildId>.json`) is one
  document per guild in the key-value table: namespace = the plugin's name, key = the guild ID in
  decimal, value = v3's JSON document unchanged (its camelCase keys included), so that the v3 data
  import (B11, built before cutover) can copy v3's files. A missing document or field reads as
  v3's default (Moshi's); read-only paths never write (v3 created files there); read-modify-write
  runs under
  `store.lock(f"{NAMESPACE}:{guild_id}")` (WelcomeGoodbye), because discord.py runs handlers
  concurrently, or as one `Store.update(NAMESPACE, key, fn)`, a single transaction whose `fn`
  returns a new document and hands values back through a list it appends to (Economy's
  `store.change`, for balances). An entry that is not v3's shape raises and is never overwritten.
  When v3 deleted a guild's data on leave, delete it in `on_guild_remove` and, from `on_ready` and
  from `cog_load` in a ready bot, for every guild that `bot.get_guild` does not know
  (WelcomeGoodbye's `store.py` and `forget_left_guilds`); when v3 kept it, keep it (Economy).
- Amounts that v3 kept in Kotlin `Int`s are Python integers: exact, never wrapped, never floats.
- A second kind of per-guild data goes in its own namespace, `<Name>.<kind>`, keyed by the guild
  ID (DynamicVoiceChannel's `DynamicVoiceChannel.rooms`, which v3 kept in a MongoDB collection),
  so that `<Name>` keeps v3's documents only; `forget` deletes both.
- `Store.update` writes its function's result even when nothing changed, and stores `null` for a
  missing key when the function returns None: a change that may find nothing to change (an unbind,
  forgetting a room) uses `store.lock` with `get`, `put` and `delete`, and deletes the document
  with its last entry (DynamicVoiceChannel's `store.py`).
- Settings that v3 kept per channel inside a guild's file (`{"<channelId>": {...}}`) stay one
  document per guild; each change reads it under the guild's lock, rewrites the one entry in v3's
  shape and keeps the others as they were (the shared `ListenSettings._change` and `remove`).
- Data that grows with the guilds' traffic and is kept for years (ChatLogger's messages, v3's
  SQLiteAPI files) lives in the plugin's own SQLite files under `context.data_directory`
  (`data/<Name>/`, in the data volume; the core does not create it). Follow ChatLogger's
  `messages.MessageFiles`: one `ThreadPoolExecutor(max_workers=1)` made in `open` and shut down in
  `close`, one connection per file made and used on that thread only, each method one job and each
  job's work in a file one transaction (`transaction`, which commits inside the `try` that rolls
  back: a commit that fails on another program's lock would otherwise stay open for the next one);
  `cog_load` opens the files (and closes them again when its checks fail), `cog_unload` closes them
  after cancelling the loops, `close` submits its job directly and awaits it shielded (a cancelled
  `run_in_executor` await cancels a queued job), and work that comes after `close` raises. Files cover ranges of snowflakes named by their start (`files.py`);
  a new file starts once the newest file's page count reaches the limit, above every stored ID, so
  that no row moves, built under a temporary name and renamed closed. Bound it: a config key
  (`retention_days`) and a background task that deletes whole expired files, then older rows in
  batches through a subquery, at READY and every hour. SQL stays in module constants (ruff's S608
  refuses SQL built with f-strings). A snowflake gives its creation time
  (`discord.utils.time_snowflake`, `snowflake_time`). Small tables that need queries can still be
  plugin tables in the core store (`<Plugin>_<table>` through `Store.run`).
- Records that concurrent presses and a background loop change, where a press may change nothing
  (Giveaway's joins and draws), run a pure transition under the guild's `store.lock`: read the
  document, parse only the entry needed, write only when the transition changed it
  (`Giveaways.change`). Every writer of the namespace takes the same lock. v3's Moshi documents
  parse into frozen dataclasses with v3's defaults (`parse_instance`) and write back in Moshi's
  field order (`instance_json`); a broken entry raises `DataError` and stays as it is.

### Commands

- Build commands in `setup` from the Lang: `Translator` reads the Lang from each string's extras,
  and the Lang loads only in `setup`. Pattern: `Example.command()` in the template.
- The callback is the cog's bound method (`callback=self.example_command`): discord.py makes the
  cog the command's binding, so `cog_app_command_error` and the cog's `interaction_check` apply as
  for a decorated cog command. Localize the options by calling `app_commands.rename(...)` and
  `app_commands.describe(...)` on the built command, each once with every option (`describe` gives
  the options it does not name an ellipsis), with values
  `lang.command(<v3 default>, "<register.yaml key>")`. Commands with different handlers take a
  `kind` in the `COMMANDS` table (Economy's `CommandSpec`).
- Keep `import discord` (and every name in the callback's annotations) at runtime: discord.py
  evaluates the annotations when the command is built. ruff does not flag a move into
  `TYPE_CHECKING`; the plugin's tests do, because the plugin stops loading.
- Base names and descriptions are v3's `Commands.slash(...)` defaults. Limits use
  `app_commands.Range`. Guild command by default; v3 `globalCommands()` get `extras={"global":
  True}` and JDA's defaults, which discord.py does not send unless set:
  `allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True,
  private_channel=False)` and `allowed_installs=app_commands.AppInstallationType(guild=True,
  user=False)` (BotInfo). A command that opens a modal sets `extras={"defer": False}`. The tree
  defers the others ephemerally before the callback runs: answer with
  `interaction.edit_original_response(...)` or `interaction.followup.send(...)`.
- v3's `setDefaultPermissions(DefaultMemberPermissions.enabledFor(ADMINISTRATOR))` is
  `app_commands.default_permissions(administrator=True)(command)` on the built command; the payload
  then holds `default_member_permissions` 8 (Economy, Giveaway). Permissions an operator lists by
  discord.py's names become `command.default_permissions = discord.Permissions(<the flags' bits>)`,
  and None lets every member use the command (CustomCommands' `_permissions`).
- v3's `addSubcommands(SubcommandData(...))` is an `app_commands.Group(name=lang.command(...),
  description=..., default_permissions=discord.Permissions(administrator=True))` built in the
  plugin's `cog.py` (a bare `Group` takes its `module` from the frame that creates it, so unloading
  then removes it) and `group.add_command(app_commands.Command(..., callback=self.<method>))` per
  subcommand, each localized with one `rename` and one `describe` call from
  `<root>.subcommands.<name>.*` (DynamicVoiceChannel's `command` and `SUBCOMMANDS`). The tree
  defers each subcommand; `interaction.command` is the subcommand.
- Commands that only differ by the template they show share one callback, the cog's bound method,
  which reads the base name from `interaction.command.name` (CustomCommands' `post_message`, which
  looks the name up among its config's entries). Commands that differ in their options share one
  callback per signature (WelcomeGoodbye's `bind_channel` and `unbind_channel`, with a `COMMANDS`
  table of `CommandSpec(kind, description, option)`).
- Commands that the operator defines in `config.yaml` (CustomCommands since
  `custom-commands-from-config`): `setup` builds one per entry with `command(spec)`, names and
  descriptions as `localized(default, translations)` (the core's; no `register.yaml`),
  `extras["guilds"]` for a guild list (the core uploads such a command to those guilds only) and,
  for a public reply, `extras["defer"] = False` and `response.defer(thinking=True)` in the
  callback: after the tree's ephemeral deferral no reply can be public. A configured name passes
  discord.py's `validate_name` and the core's `is_command_name` (discord.py's pattern lets a final
  line break through); a response that Discord refuses is deleted with a warning.
- A channel option limited to JDA's channel types (`setChannelTypes(ChannelType.TEXT)`) is
  `app_commands.Transform[app_commands.AppCommandChannel, <Transformer>] | None` with a Transformer
  whose `type` is channel, whose `channel_types` lists the types and whose `transform` passes the
  value on (WelcomeGoodbye's `TextChannelOption`): `discord.TextChannel` would also offer
  announcement channels and need the cache. Check `channel.type` in the handler too.
- A user option that v3 read with `asMember` is `discord.Member | discord.User`: discord.py passes
  the user when Discord resolved no member, where a `discord.Member` annotation raises before the
  callback and leaves the deferred response "thinking". Check the member against `MemberLike` in
  the callback and answer (Feedback's `create_form`). One that v3 read with `asUser` takes the
  same annotation without the check: any user counts (Economy's `member`).
- v3's runtime `member.hasPermission(ADMINISTRATOR)` is `interaction.permissions.administrator`,
  checked after `interaction.guild is None` (never true in a guild: discord.py creates a placeholder
  guild). A reply v3 rendered in `event.guild.locale` uses
  `(interaction.guild_locale or interaction.locale).value` (WelcomeGoodbye's `_guild` and
  `_reply`).
- A v3 reply posted with `event.channel.sendMessage(...)` after the defer: send it to
  `interaction.channel` when that has `send` (a `runtime_checkable` Protocol, so fakes need no
  discord base class; forums and categories have none), then `delete_original_response()`; on
  `discord.HTTPException`, edit the deferred response into it instead (Calculator's `_post`).
  When the reply is a whole operator template (v3 sent the built message: components and files
  too), send `content`, `embeds`, `view` and `files`, check the channel as `object` against a
  Protocol that takes them (discord.py's `send` overloads take a `View` or a `LayoutView`, never
  their union), and render again for the fallback, with the files as `attachments`: discord.py
  closes a message's files once it sent them, even when Discord refused it (CustomCommands'
  `_postable` and `_send`).

### Listeners and intents

- Gateway events are `@commands.Cog.listener()` methods on the cog (`on_member_join`, `on_ready`);
  discord.py adds them with the cog and removes them when the plugin unloads. Check what each event
  needs cached: `on_member_join` builds the member from the event, `on_member_remove` fires only
  for cached members (use `on_raw_member_remove`: its `user` is the cached `Member` or else the
  `User`, its guild comes from `bot.get_guild(payload.guild_id)`, and JDA ignored the bot's own
  removal, so skip `bot.user`). A message sent to a guild channel goes through a
  `runtime_checkable` Protocol checked on the channel as `object`, and a refused one is a warning
  that names the guild and the channel (WelcomeGoodbye's `_postable` and `_greet`).
- `INTENTS` lists what the listeners need beyond discord.py's defaults:
  `discord.Intents(members=True)` for member events, and for `Guild.member_count`, which
  discord.py updates only from those events (BotInfo). The members intent is privileged: the
  design's smoke checklist says to allow it in the developer portal.
- A gateway event that discord.py does not parse (VoiceLogger's `VOICE_CHANNEL_STATUS_UPDATE`):
  `bot.relay_gateway_event("<Discord's name>")` in `setup`, and a cog listener
  `on_gateway_<name in lower case>(payload)` that validates the payload (`parse_update`). The relay
  lasts as long as the bot. Audit log entries of types that discord.py does not know (192, 193) are
  read raw with `bot.http.request(Route("GET", "/guilds/{guild_id}/audit-logs", ...),
  params=...)`, because `Guild.audit_logs` drops their `options`, and matched by type, channel and
  time (`status.match`), never as the guild's newest entry; `guild.fetch_member` stands for JDA's
  `retrieveMemberById`.
- Message events: a new message comes from the relayed `MESSAGE_CREATE` payload
  (`bot.relay_gateway_event("MESSAGE_CREATE")`, `on_gateway_message_create`; skip direct messages
  and the bot's own), because `on_message` gets discord.py's cached `Message`, which an edit parsed
  before the listener runs has changed in place; `on_raw_message_edit` (`payload.message` is a new
  message built from the update; `on_message_edit` needs the cached one), `on_raw_message_delete`
  and `on_raw_bulk_message_delete` wait for the message's handling under way (ChatLogger's
  `inserting`). Read the channel's place before the first await: a thread's parent and that
  channel's category come from `thread.parent`, since `Thread.category_id` raises without it
  (ChatLogger's `Place.of`). Test frames that arrive together with `plugin_fakes.burst`. A
  member's embeds are link previews (members cannot send embeds): leave them out of a member's
  text. A listed ID that discord.py has not cached (an archived thread) is asked of Discord before
  it counts as deleted (the shared READY check). `INTENTS = discord.Intents(guild_messages=True,
  message_content=True)`: the message content intent is privileged, and Discord refuses the bot's
  connection unless the developer portal allows it; the smoke checklist says so.
- State that mirrors Discord's (VoiceLogger's tracked voice statuses) is forgotten at each READY
  (`on_ready` fires for each new session) and a guild's on `on_guild_unavailable` and
  `on_guild_remove`, as JDA rebuilt its cache. Logs of one entity whose handling waits for
  different times (a second audit log read) run under a per-entity `store.lock(...)`, whose waiters
  go in arrival order.
- Messages to channels that a command set up (VoiceLogger's listen channels) go through
  `bot.get_partial_messageable(id, guild_id=...)` and a `Postable` cast (the `send` overloads take
  no view union): no cache needed, archived threads reached; a `discord.NotFound` forgets the
  channel's settings, another refusal is a warning naming the guild and the channel, and the other
  channels still get the message (the shared `ListenChannels.post`).
- Problems the operator must fix (a missing role or permission) are `logger.warning` lines from
  `logging.getLogger(__name__)` that name the plugin; Discord errors on one item are logged and the
  others still handled.
- New channels (v3's `ChannelCreateEvent`, every kind, threads too): `on_guild_channel_create` and
  `on_thread_create` (discord.py dispatches it for newly created threads only); keep the channels
  that take messages with a `runtime_checkable` Protocol that has `send` (categories and forums have
  none). Members' statuses (v3's `onlineStatus`) need `discord.Intents(members=True,
  presences=True)`: both privileged, both in the smoke checklist; a member from `fetch_member` has
  no presence and reads `Status.offline` (TicketAwayNotice).
- Voice: `on_voice_state_update(member, before, after)` also fires for mutes, deafens and streams,
  where JDA's `GuildVoiceUpdateEvent` fired for channel changes only: compare the channels' IDs.
  Count a channel's members with `channel.voice_states` (no member cache needed), and read it at
  the start of the listener, before the first await: discord.py runs listeners as tasks, and the
  events parsed meanwhile are already in the cache. `after` is the cached voice state itself, which
  later events update in place (`before` is a copy): read the channels' IDs, names and categories
  at once (VoiceLogger's `Place.of`). `INTENTS = discord.Intents(voice_states=True)` (in
  discord.py's defaults, declared anyway).
- A sequence of Discord requests that another event must not interleave with (creating a room,
  then deleting it when it empties) runs under a per-guild `store.lock("<Name>:voice:<guildId>")`,
  outside the store's data lock; re-check under the lock what the listener read before.
- Channels that the plugin creates and must clean up after a restart are tracked in the store once
  deleting them loses nothing (DynamicVoiceChannel tracks a room once the lobby's copy exists),
  forgotten on a 404, kept with a warning when a deletion is refused, and checked from `on_ready`
  and from `cog_load` in a ready bot (empty ones deleted, missing ones forgotten, unavailable guilds
  skipped). `VocalGuildChannel.clone()` copies the overwrites as they are; JDA's raw
  `setPosition` is a `Route("PATCH", "/channels/{channel_id}")` with `{"position": n}`, because
  `edit(position=...)` renumbers the guild's whole bucket; `set_permissions(member, overwrite=...)`
  replaces JDA's `putMemberPermissionOverride` (DynamicVoiceChannel's `rooms.py`).

### Background loops and HTTP

- One `asyncio` task per loop, created in `cog_load` and kept on the cog (UptimeHeartbeat's
  `tasks`), awaits `bot.wait_until_ready()` first: nothing runs before READY, `--no-online` (whose
  `async with bot` creates a READY event that never fires) cancels the waiting tasks when it
  unloads the plugin, and a plugin reloaded into a ready bot starts at once. `cog_unload` cancels
  the tasks and awaits them, so their resources close before the bot's HTTP client.
- v3's `delay(...)` after each iteration is a fixed delay: `while await step(): await
  sleep(seconds)`. `discord.ext.tasks.loop` schedules from each start (a fixed rate). Pass the
  loop's effects in (the request, the ping, `sleep`) so that tests drive it on a fake clock
  (UptimeHeartbeat's `Pusher`).
- A failed step is logged and the loop goes on, whatever failed: catch the expected errors
  (`aiohttp.ClientError`, `OSError`, timeouts included) without a traceback and any other
  `Exception` with its traceback. `asyncio.CancelledError` is no `Exception`, so cancellation stays
  quiet. A step that fails at every pass logs each kind of failure (status code, error type) once
  per episode, the rest at debug level, and one info line once it has worked three times in a row
  (UptimeHeartbeat's `Failures`, one per step on the loop's object): steady, alternating and
  flapping failures stay quiet.
- A URL that carries a secret (a push token in its path or query) appears in logs as its origin
  (`xincord.plugins.redaction.origin`, moved there from UptimeHeartbeat's `logs.py` by
  port-ticket). Redact error texts too (`xincord.plugins.redaction.redact(text, *urls)`: URLs cut
  to their origin and the secret URL's parts removed, since aiohttp's connect timeout names the
  whole URL and a malformed answer can quote the request line), log an unexpected error's
  traceback as redacted text (`format_traceback`), since `logger.exception` prints it as it is,
  and hide the input of the config's validation errors (`ConfigDict(hide_input_in_errors=True)`).
- Outgoing HTTP uses aiohttp, which discord.py installs and `xincord-plugins` declares: one
  `ClientSession` per loop, opened after READY with v3's limits as `ClientTimeout` and closed with
  the loop (`async with`); `allow_redirects=False` matches Java's `HttpClient`.
- v3's `scheduleAtFixedRate(task, delay, period)` is `wait_until_ready()`, `sleep(delay)`, then
  passes with `sleep(period)` after each (Giveaway's `_auto_draw`); the cog keeps `sleep` and
  `clock` (and `random` for draws: `random.SystemRandom()`) so tests drive them. A pass stores its
  changes before it posts, and posts through `bot.get_partial_messageable(c, guild_id=g)`
  (`get_partial_message(m).edit(...)` needs no fetch), cast to a Protocol that takes the view
  union.
- Work that an event starts and that waits (v3's `queueAfter`, TicketAwayNotice's notice): the
  listener checks what needs no await, then creates a task, kept in a set on the cog with
  `task.add_done_callback(self.<set>.discard)`; the task waits on the cog's `sleep`, checks the
  cache again when the wait ends (the channel and guild still there, the member's status) and logs
  what it does not handle with `logger.exception`, since nothing awaits it; `cog_unload` sets a
  `closed` flag that the listener checks (a listener that discord.py scheduled before the unload
  still runs after it), then cancels and awaits the set. The listener returns at once, so the wait
  holds no other event up. Threads that the bot starts itself (Ticket's archives) reach
  `on_thread_create` too: skip them by `thread.owner_id` when they are not meant.
- A Discord REST call that JDA made without a discord.py counterpart goes through
  `bot.http.request(discord.http.Route(method, path))` (UptimeHeartbeat's `rest_ping`).

### Channels, overwrites and webhooks

- A channel created for a member (Ticket's tickets) gets the whole overwrite map, since
  `create_text_channel(overwrites=...)` copies nothing from the category: the category's
  overwrites when the bot is an administrator or holds every permission they allow or deny there
  (JDA's `trySync`), `Object(type=Role)` keys left out (discord.py sends them as member
  overwrites), then the channel's own, and the bot's View Channel on top of its copied overwrite.
  Overwrite one member with `overwrites_for(member)`, the bit changed, and `set_permissions`.
- Messages sent as other users go through a webhook made in the target channel: `send(...,
  username=..., avatar_url=..., thread=..., wait=True, allowed_mentions=AllowedMentions.none())`,
  usernames that Discord takes (`forwarded_name`), texts in parts of 2000 UTF-16 code units, files
  over `guild.filesize_limit` linked, and the webhook deleted whatever happened; its URL holds its
  token, so error texts pass `xincord.plugins.redaction.redact` (Ticket's `archive.py`).
- A user's text posted publicly pings only what the plugin means to (Ticket's opener: the staff
  roles through `AllowedMentions(users=False, roles=[...])`).
- A component put on a message before its record is stored comes off again when the store fails
  (Ticket's `Panels.add(..., place)` and the view rebuilt from the fetched message), or the next
  one takes the same custom ID, which Discord refuses. A reply that repeats a string option cuts
  it: options take 6000 characters, replies 2000.

### Templates and placeholders

- `Templates.load(lang)` in `setup`, so a broken template disables the plugin at load. Render with
  `render_message(templates.message(name, interaction.locale.value), values, build_id=IDS.build)`.
- v3's `Placeholder.get(event)` is `xincord.core.placeholders.placeholder_values(interaction)`
  (`actor_values(interaction.user, bot) | interaction_values(interaction)`, moved into the core by
  WelcomeGoodbye); `Placeholder.get(member)` and `Placeholder.get(user)` are
  `actor_values(member_or_user, bot)`. v3's `putGuild`, `putUser`, `putMember`, `putEvent` and
  `putTextChannel` with a prefix are `guild_values`, `user_values`, `member_values`,
  `event_values` and `channel_values` with that prefix (WelcomeGoodbye's `values.py`).
- Plugin keys keep v3's names (`_Example@option1`, `ga@title`) so operators' templates keep working.
- The core trims embed field names and values as JDA did and gives an empty one U+200E, which
  Discord would refuse otherwise (Feedback's empty feedback): no plugin-side workaround.
- A template that v3 rendered with `getCreateBuilder(key)` and no locale, such as a public message,
  renders in `lang.default_locale` for every user (CustomCommands' posts and public replies); one
  rendered with the user's locale uses `interaction.locale.value` (CustomCommands' ephemeral
  replies). Without a substitutor, v3 used only its global keys: `bot_id` and `bot_name`,
  `xincord.core.placeholders.global_values(interaction.client)` (BotInfo, Economy's
  `no-permission`); operator templates may get `placeholder_values(interaction)` instead
  (CustomCommands).
- A template whose first embed's description is the template of rows (Economy's boards) is checked
  for every locale in `setup`, so that a broken one fails at load with the file named.
- Texts that v3 hard-coded in one language for every user (Ticket's replies, errors, control row
  and archive markers) also go in `text.yaml`: zh-TW holds v3's, en-US English ones, and v3's
  English-only strings get zh-TW translations (listed in the review queue). Replies to one user
  pass `interaction.locale.value`, which `Lang.text` falls back from to the default locale per
  key, as v3's templates did; public messages use `lang.default_locale` (Ticket's `texts` and
  `public`).
- Texts that v3 hard-coded in Kotlin (Giveaway's field names, statuses, replies, errors) go in a
  new `lang/<locale>/text.yaml` with `%ga@...%` placeholders, read with
  `Lang.text("text.<key>", locale)` and rendered in one pass (`texts.Texts`). v3 chose them by a
  `zh` prefix while templates fell back to the default locale; pick one locale for both
  (`texts.language`: the locale's own files, else zh-TW for `zh*` and en-US). Check the copied
  texts against the Kotlin sources with a script, fragment by fragment.

### Components

- `IDS = ComponentIds("<package>", fields, legacy_prefix=..., legacy_hex=...)` in `cog.py`: v3's
  fields first, in v3 declaration order (`action` first in every v3 plugin), new fields appended;
  `legacy_prefix` is v3's `component_prefix` from `info.yaml` or `<lowercase name>@`; `legacy_hex`
  lists the fields v3 declared as `FieldType.INT_HEX` or `LONG_HEX`. A plugin without v3
  components has no legacy prefix. A v3 prefix whose IDs had no fields (Economy's `economy@`) gets
  the fields `("action",)` and a handler that ignores them.
- Templates set `uid: {action: ..., ...}`; `setup` calls `bot.route(__name__, IDS, handler)`. The
  handler gets `ParsedId` (values are strings), dispatches on `action`, and may raise: the core
  logs it with the plugin's name and upgrades legacy IDs on the message afterwards.
- `interaction.response.edit_message(view=...)` changes only the components; content and embeds
  stay. To replace the whole message, as JDA's `MessageEditData.fromCreateData` did, pass the
  rendered `content`, `embeds`, `view` and `attachments` (`embeds=()` and `view=None` clear them):
  one type-7 response stands for v3's `deferEdit` and `editOriginal` (VoiceLogger's `_edit`).
- An entity select menu's choice is `interaction.data["values"]`, snowflakes as strings, with
  `component_type` 5 to 8; v3's `EntitySelectInteractionEvent` covered all four (VoiceLogger's
  `handle`).
- A plugin with v3 components routes them all to one `handle(interaction, parsed)` that dispatches
  on `interaction.type` and `parsed.fields["action"]`, as v3's `onButtonInteraction` and
  `onModalInteraction` did; other actions get no response. The core parses v3's IDs and upgrades
  the message after the handler, so the handler compares the pressed ID as it came (Feedback).
- A button that opens a modal answers `interaction.response.send_modal(render_modal(
  templates.modal(name, interaction.locale.value), values, build_id=IDS.build))`; the modal's
  `uid` keeps v3's keys, so its ID is routed like a button. Read the submission with
  `modal_values(interaction.data)` (labels and action rows). To change the button's message after
  the modal, edit `interaction.message` with the bot's token: rebuild its view with
  `View.from_message` (`LayoutView.from_message` when `message.flags.components_v2`), stop it and
  `message.edit(view=...)` (Feedback's `highlight`). A submission that posts elsewhere defers
  (`response.defer()`, a deferred message update) and reports a failure with
  `followup.send(..., ephemeral=True)`.
- A button whose handler waits for a shared lock or the store before it can answer (Giveaway's
  Join / Leave and Draw Winners) acknowledges at once with `response.defer()` (a deferred update),
  then shows its message as stored with `edit_original_response(...)` (the component's message,
  through the press's webhook, which no channel rate limit delays) on every press, refusals
  included, so that a stale message repairs itself, and tells the user with
  `followup.send(..., ephemeral=True)`; v3 edited through the REST API and replied. A burst on a
  large document otherwise runs past Discord's three seconds.
- A builder keeps a changed draft only once Discord took the edit that shows it:
  `response.edit_message` marks the response done only after Discord answered, so on
  `discord.HTTPException` the interaction is still open and `response.send_message(...,
  ephemeral=True)` gives Discord's error (Ticket's `_screen` and `_update`); Discord checks emojis,
  URLs and empty embeds that discord.py sends unchecked.
- State that a builder keeps between interactions (Giveaway's drafts) lives on the cog, keyed by
  user and guild, with the ID of the message that shows it (the message that
  `edit_original_response` returns); presses and modal submissions from another message answer
  that the session expired. Each change answers through its own interaction (`edit_message` also
  works for a modal opened from that message), never through the command's 15-minute token. A
  confirmation removes the state before its first await, so a second press finds none, and gives
  it back with `setdefault` when posting fails.

### Tests

- `tests/plugins/<package>/test_<topic>.py`. The module docstring cites the Kotlin sources; each
  test's docstring is `Requirement: <name>.`
- `tests/plugins/<package>/conftest.py`: `bot` loads the real plugin with
  `plugin_fakes.load_plugin("<Plugin>", tmp_path / "plugins", store)` (entry point, translator and
  `setup`, no network); `cog` is `bot.get_cog(...)`. To test operator edits and v3 files, pass
  `config="..."` to `load_plugin`, which writes `<root>/<Plugin>/config.yaml` first. A `setup` that
  raises (an invalid config) makes discord.py drop the plugin's modules, so a later load imports new
  classes: tests that load bad files look the cog up with `cast`, not `isinstance` (AutoRole's
  `test_config.py`), and so does the `cog` fixture of such a plugin, because the tests that run
  later get the new classes too (BotInfo's `conftest.py`).
- `tests/support/discord_fakes.py`: `FakeInteraction` records what the plugin sends in `sent`;
  `FakeChannel` records `channel.send` into a shared `sent` list or raises its `error`
  (`forbidden()`); `FakeUser`, `buttons(view)` and `embed_dict(embed)`; `FakeGuild` (roles,
  `get_role`, `me.guild_permissions`, `unavailable`, `member_count`), `FakeRole` (`is_assignable()`) and
  `FakeMember` (`add_roles` records the role IDs and `atomic`, or raises from `errors`), cast with
  `as_member()`. Extend it instead of writing new fakes. pytest runs in importlib mode, so a test
  module cannot import another one: tests that share helpers stay in one module (Calculator's
  `test_replies.py`) or become fixtures in `conftest.py` (AutoRole's `guild`).
  A callback that reads the invoked command gets `FakeInteraction(command=SimpleNamespace(
  name=...))`. Close the `discord.File`s that a test receives (Components V2 templates with a
  `file_path`), or the unclosed files fail the run. For guild placeholders and guild commands,
  `FakeInteraction` takes `guild`, `guild_locale` and `permissions`; `FakeGuild` takes `channels`
  (`get_channel`), `preferred_locale`, `icon`, `rules_channel` and the other `GuildLike`
  attributes, and `as_guild()` casts it; `FakeChannel` has `type` and `mention`; `FakeMember` has
  the user and member attributes that placeholders read (`global_name`, `nick`, `avatar`, `roles`,
  `joined_at`); a logged-in bot's user is `monkeypatch.setattr(Bot, "user",
  property(lambda _bot: BOT_USER))` (WelcomeGoodbye's `test_members.py`).
  For components and modals: `FakeMessage` (components built with `discord.ActionRow(payload)`,
  `flags`, edits and deletion into `sent`, `channel.fetch_message` until deleted, `error`),
  `FakeResponse.send_message` and `send_modal`, `FakeInteraction.followup` and `not_found()`;
  route v3 IDs through `bot.on_interaction` to see the core's upgrade (Feedback's
  `test_routes.py`).
  Call cog methods directly (`cog.example_command(...)`), check a command's wiring through
  `bot.tree.get_command(...)` (its `binding` is the cog), send components through
  `bot.on_interaction(...)`, which includes the routing, and run listeners with
  `plugin_fakes.dispatch(bot, "member_join", member.as_member())` (`bot.dispatch` needs a bot that
  logged in). For guild data, `monkeypatch.setattr(bot, "get_guild", guilds.get)`; for a load into a
  ready bot, patch `Bot.is_ready` and `Bot.get_guild` before `load_plugin` (AutoRole's
  `test_check.py`).
- Loops (UptimeHeartbeat's `conftest.py`): an autouse `ready` fixture builds
  `plugin_fakes.Ready(monkeypatch)`, which patches `Bot.wait_until_ready` (discord.py's raises
  before a login) and offers `set()`, `waiters(n)` and `close()`, which cancels the tasks left
  running at teardown; an autouse fixture patches `discord.http.HTTPClient.request` to record REST
  calls; `http_fakes.running_monitor()` runs `Monitor`, a local HTTP server that answers each path
  with a status, can leave requests unanswered (answered when it closes, or its teardown waits for
  the client's timeout) and records them. Never sleep in real time: inject the clock, and wait on
  events (`monitor.received(n)`, `ready.waiters(n)`, `plugin_fakes.until(...)` for a log line) under
  a timeout. `test_pusher.py`'s `Fakes` answer the pushes and the pings in turn (`answers`,
  `pings`); a local `asyncio.start_server` that answers garbage gives aiohttp's real error for a
  malformed answer (`test_request.py`). `bot.remove_cog(name)` runs
  `cog_unload` without unloading the plugin's modules.
- `tests/fixtures/plugins/<package>/golden.yaml`, loaded with `plugin_fakes.golden("<package>")`:
  v3's text per locale. Compare rendered embeds and buttons, and the command payload from
  `CommandTree.payloads()`, with it; no CJK text is typed in Python.
- A test that loads the plugin cannot reach a stub that raises without breaking the load: mark it
  `xfail(strict=True, reason=...)` without `raises`. Give handlers that tests call directly a stub
  and `raises=NotImplementedError`. A test that would already pass (such as "no response") must
  call a stub. To refine a handler that already works (AutoRole's skipped roles), route the new
  cases to a stub in the xfail commit. A stub whose annotations need `discord` keeps that import
  under `TYPE_CHECKING`
  and plain types (ruff's TC rules); the imports move to runtime with the code that uses them.
- Pure functions get one requirement each when they can be stubbed separately (Calculator:
  trimming, reading, results, powers, then `calculate` with the golden files), so that each xfail
  commit fails for its own stub.
- Never unload or reload the real plugin in a test without an autouse `plugin_modules` fixture
  that puts its `sys.modules` entries back after each test (Giveaway's, CustomCommands'): discord.py
  re-imports its modules, and later tests compare against classes from the old ones. With it, a
  test may reload the real plugin and look the new cog up by name (CustomCommands'
  `test_reload.py`); the core's reload tests use fake plugins.
- Voice and channels (DynamicVoiceChannel's `conftest.py`): `discord_fakes.FakeVoiceChannel` (a
  `FakeChannel` with `guild`, `category_id`, `voice_states`, and `clone`, `delete` and
  `set_permissions` that record into `sent` or raise from `errors`; `clone` sets `cloning` and
  waits for `gate`), `FakeGuild.voice_channels`, `voice_state(channel)` for `before` and `after`,
  and `FakeRest`, whose `install(monkeypatch)` records discord.py's REST requests as
  `("<method> <path>", {"json": body})` into the same `sent` list as the channels, or raises from
  `errors`. Test interleavings with `gate` and `cloning` (wait on the event or on the task's
  failure), never with sleeps. The bot's user for `bot_*` values is an autouse fixture patching
  `Bot.user`.
- Relayed gateway events (VoiceLogger's `test_status.py`): `plugin_fakes.gateway(bot, name,
  payload)` hands the payload to discord.py's parser table, as its gateway does, and awaits the
  listeners it dispatched; `plugin_fakes.parsers(bot)` is that table. `FakeRest.answers` answers a
  `"<method> <path>"` with successive payloads and records query `params`; `FakeGuild.members` and
  `fetch_member` stand for Discord's members; `FakeInteraction` gives `guild_id` and `channel_id`;
  a `channels` fixture patches `bot.get_partial_messageable` with `FakeChannel`s by ID. ruff counts
  fixtures as arguments (PLR0913, PLR0917, at most five): bundle them in a dataclass fixture
  (`Scene`) with helper methods.
- When the new behavior runs from a listener that earlier tests already trigger (`on_ready` for the
  checks at READY), a stub would break those tests: mark the new tests `xfail(strict=True,
  reason=...)` without `raises`, failing on their assertions. A plugin whose `cog_load` can raise
  in such a test is re-imported by discord.py, so its `cog` fixture uses `cast`.
- Message events go through discord.py's own parsers: `tests/support/payloads.py` builds the
  payloads (a member carries `flags`, or discord.py keeps the author a `User`),
  `plugin_fakes.add_guild(bot, payloads.guild(...))` caches a guild with its channels and threads,
  and `plugin_fakes.gateway(bot, "MESSAGE_CREATE", payload)` runs the listeners that the parser
  dispatched. ChatLogger's `scene` fixture bundles the bot, the store, the REST recorder, the cached
  guild and the posts per listen channel; a `config` fixture that the `bot` fixture reads lets a
  test load the plugin with another `config.yaml` through `pytest.mark.parametrize("config", ...)`.
- A plugin that holds files or threads unloads in each test what it loaded: ChatLogger's `load`
  fixture removes the cog at the end (its `cog_unload` closes the files), because Python warns
  about a `sqlite3` connection collected unclosed and pytest fails whichever test is running then.
  `Scene.rows` reads the message files through connections of the test's own, and `write_file`
  writes one as an earlier run left it. Assert `plugin_fakes.unclosed() == []` where a leak would
  show (a warning left to the collector fails a later test), after dropping the references that a
  cancelled task's traceback keeps.
- ruff, pyright, pytest and coverage already cover `packages/` and `tests/`; nothing to configure
  per plugin.
- A plugin whose tests load invalid configs and compare its frozen dataclasses needs an autouse
  fixture that puts its `sys.modules` entries back after each test (Giveaway's `plugin_modules`):
  a failed load makes discord.py import new classes, which never equal the old ones.
- Test modules cannot import `conftest` at runtime: a dataclass of the conftest (Giveaway's `Who`,
  who presses, in which locale, on which message) is built through a fixture's method
  (`scene.who(locale="zh-TW")`). `discord_fakes`: `FakeInteraction.original` is what
  `edit_original_response` returns; `FakeChannel.send` returns a `FakeMessage` (with `jump_url`)
  and `get_partial_message` gives its messages, whose edits raise `message_error`.
- Ticket's `scene` (`tests/plugins/ticket/conftest.py`) adds `click(action, who, **fields)` for a
  plugin's own buttons and `refuse_edit` for refused builder edits; `discord_fakes` has
  `FakeCategory` (overwrites, `permissions_for`, `create_text_channel` recording into `sent`),
  hashable `FakeMember`s (overwrite keys), `FakeGuild.default_role`, `get_member` and
  `filesize_limit`, `FakeChannel.delete`, `overwrites_for` and `set_permissions`, `bad_request()`
  and `button_rows(view)`.
- Keep each xfail reason a literal string in its decorator: a script then strips the markers of
  one requirement at once.
- TicketAwayNotice's `scene` (`tests/plugins/ticket_away_notice/conftest.py`) feeds
  `CHANNEL_CREATE`, `THREAD_CREATE` (with `newly_created`), `PRESENCE_UPDATE`, `CHANNEL_DELETE`,
  `GUILD_DELETE` and `GUILD_MEMBER_REMOVE` to discord.py's parsers and lets `FakeRest` answer each
  new channel's `POST /channels/{id}/messages` with a message payload, which `Messageable.send`
  needs; its `Clock` is the injected `sleep`: each wait is recorded and lasts until the test wakes
  it (`asleep(n)` waits for n waits), so a test changes the cache during the wait. `payloads.guild`
  takes `members` and `presences` (`payloads.presence`), `payloads.channel` a `guild_id`, and
  `FakeRest` keeps a multipart upload's parts as `form`.
- A loop with a first delay and a period runs on `Ticks` (Giveaway's `test_auto_draw.py`): each
  sleep is recorded, waits for the test, and moves the injected clock. A press that must be caught
  in the middle (a double confirmation) uses a fake whose `send` waits on a gate; wait with
  `asyncio.wait({sending, task}, return_when=FIRST_COMPLETED)` so an xfail stub fails at once.
