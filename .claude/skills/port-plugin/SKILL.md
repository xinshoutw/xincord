---
name: port-plugin
description: Port one XsDiscordBotKt plugin to xincord following the project's OpenSpec and xfail-first rules. Use when starting or continuing the port of a named plugin (for example "port AutoRole").
---

# Port a plugin

Work on one plugin at a time, in the order of decision C1. Follow `AGENTS.md` throughout. The
template is _Example: `packages/xincord-plugins/src/xincord/plugins/example/`, its tests in
`tests/plugins/example/` and its archived change `openspec/changes/archive/*-port-example/`. Copy
its shape and the conventions below. Fix this skill when reality differs; the newest port wins.

Names: `<Plugin>` is the v3 name (`AutoRole`, `_Example`), `<kebab>` its kebab case (`auto-role`,
`example`) for the change and the commit scope, `<package>` the Python package (`auto_role`,
`example`).

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
     pair of tasks, with one xfail mark per requirement (WelcomeByeGuild's 6.1 and 6.2).
   Run `openspec validate port-<kebab> --strict`, the gate, and commit
   (`docs(plugin-<kebab>): propose port-<kebab>`).
3. **Resources.** Copy v3's `config.yaml` and lang files into the package (fix missing final
   newlines and CRLF line endings), example values only: never real IDs, account numbers or
   tokens. A list whose v3 default held real IDs or pointed at the owner's servers ships empty,
   with placeholder values in a comment (AutoRole's `guilds`, IntervalPusher's `listeners` on
   `status.example.com`); a template whose v3 text held a real account number gets an all-zero
   example under a comment that asks the operator to put theirs (SimpleCommand). Copy such files
   with a script that replaces the value, and check that no real number remains, instead of
   reading the real values.
4. **Per requirement, xfail-first.** Test (fails for the expected reason; check with
   `pytest --runxfail`) -> commit with `xfail(strict=True)` -> implement and remove the marker ->
   commit. Tick `tasks.md` in the same commits. The project's Claude Code hooks (ruff on each edit,
   the gate on stop) run only in a session started in this repository; from elsewhere, run
   `uv run ruff format` and `uv run ruff check` on the changed files before the gate.
5. **Wire it up.** Entry point, `setup`, command, routes: see the conventions.
6. **Golden tests.** v3's text per locale in `golden.yaml`; v3 component IDs from the inventory
   decode and upgrade to the expected new IDs (a plugin with v3 components); every shipped template
   renders in each locale. Recorded v3 answers (BasicCalculator's JSONL) are copied unchanged; a
   record that a fixed v3 defect changes must agree with an independent implementation in the test
   (`tests/plugins/basic_calculator/test_golden.py`), never be edited. A plugin without text,
   templates or components (AutoRole) has no golden data.
7. **Check the package.** `uv build --package xincord-plugins -o <scratch dir>` lists `config.yaml`
   and `lang/` in the wheel. Stronger: install both wheels in a scratch venv and run
   `xincord --no-online` in an empty directory whose `config.yaml` enables the plugin. Then drive the
   plugin once through discord.py's own objects in a scratch script (not committed): set
   `bot._connection.user` to a `discord.ClientUser`, build `discord.Interaction(data=<payload>,
   state=bot._connection)` and call `command._invoke_with_namespace(interaction, Namespace(...))`
   with `Interaction.edit_original_response` patched; for listeners, set `bot.loop`, add a guild
   with `state._add_guild_from_data(...)` and feed `state.parse_guild_member_add(...)` and the like.
   WelcomeByeGuild's probe found a core failure (threads with an uncached parent) that the fakes
   hid. A plugin that calls Discord's REST API on its own (IntervalPusher's ping) logs in against a
   local server: point `discord.http.Route.BASE` at it, call `bot.http.static_login(...)` inside
   `async with bot`, run `setup_hook`, and set `bot._ready` for READY. For interactions, record
   HTTP instead of answering it: replace `discord.http.HTTPClient.request` (the bot's REST calls)
   and `discord.webhook.async_.AsyncWebhookAdapter.request` (interaction callbacks, which must
   return `{"interaction": {"id": ...}}`, follow-ups and `@original` edits), give the payload
   `attachment_size_limit`, run commands with `await bot.tree._call(interaction)` (defer,
   transformers, callback) and components and modals with `await bot.on_interaction(interaction)`
   (Feedbacker's probe; it checked the modal's label payload and the core's legacy upgrade).
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

- Import the plugin's own modules relatively (`from .cog import Example`). Split `cog.py` when it
  grows: pure logic in its own module (tested without discord.py, as
  `basic_calculator/calculator.py`), storage in `store.py`. Run CPU-bound work with
  `asyncio.to_thread`.
- Entry point: `<Plugin> = "xincord.plugins.<package>"` under
  `[project.entry-points."xincord.plugins"]` in `packages/xincord-plugins/pyproject.toml`. The name
  is the v3 name: the `plugins:` entry, the `plugins/<Plugin>/` directory and the log name. `uv run`
  reinstalls the workspace package; `uv.lock` does not change.
- `uv_build` ships every file in the package, so bundled YAML reaches the image.

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
  the plugin fails at load with the key named (BotInfo's `source_url`; Feedbacker's replies are
  `Annotated[str, StringConstraints(pattern=r"\S", max_length=2000)]`).
- v3 keys without a default stay required (IntervalPusher's `listeners`, Feedbacker's replies). A
  new key is optional, so that v3's files load; a text default is English, because Python files
  hold no CJK, and the bundled file can hold the zh-TW text (Feedbacker's `form_failure`).

### Storage

- `setup` passes `context.store` to the cog; the tests' `store` fixture is the same store.
- Per-guild data (v3's `JsonGuildFileManager`, `plugins/<Name>/data/<guildId>.json`) is one
  document per guild in the key-value table: namespace = the plugin's name, key = the guild ID in
  decimal, value = v3's JSON document unchanged (its camelCase keys included), so that the deferred
  migration (B11) can copy v3's files. A missing document or field reads as v3's default (Moshi's);
  read-only paths never write (v3 created files there); read-modify-write runs under
  `store.lock(f"{NAMESPACE}:{guild_id}")`, because discord.py runs handlers concurrently. Delete a
  guild's data in `on_guild_remove` and, from `on_ready` and from `cog_load` in a ready bot, for every
  guild that `bot.get_guild` does not know (WelcomeByeGuild's `store.py` and `forget_left_guilds`).

### Commands

- Build commands in `setup` from the Lang: `Translator` reads the Lang from each string's extras,
  and the Lang loads only in `setup`. Pattern: `Example.command()` in the template.
- The callback is the cog's bound method (`callback=self.example_command`): discord.py makes the
  cog the command's binding, so `cog_app_command_error` and the cog's `interaction_check` apply as
  for a decorated cog command. Localize the options by calling `app_commands.rename(...)` and
  `app_commands.describe(...)` on the built command, with values
  `lang.command(<v3 default>, "<register.yaml key>")`.
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
  then holds `default_member_permissions` 8 (SimpleCommand).
- v3 commands that only differ by the template they show share one callback, the cog's bound
  method, which reads the base name from `interaction.command.name`; `setup` adds one command per
  name of a module-level table (SimpleCommand's `COMMANDS` and `command(name)`). Commands that
  differ in their options share one callback per signature (WelcomeByeGuild's `bind_channel` and
  `unbind_channel`, with a `COMMANDS` table of `CommandSpec(kind, description, option)`).
- A channel option limited to JDA's channel types (`setChannelTypes(ChannelType.TEXT)`) is
  `app_commands.Transform[app_commands.AppCommandChannel, <Transformer>] | None` with a Transformer
  whose `type` is channel, whose `channel_types` lists the types and whose `transform` passes the
  value on (WelcomeByeGuild's `TextChannelOption`): `discord.TextChannel` would also offer
  announcement channels and need the cache. Check `channel.type` in the handler too.
- A user option that v3 read with `asMember` is `discord.Member | discord.User`: discord.py passes
  the user when Discord resolved no member, where a `discord.Member` annotation raises before the
  callback and leaves the deferred response "thinking". Check the member against `MemberLike` in
  the callback and answer (Feedbacker's `create_form`).
- v3's runtime `member.hasPermission(ADMINISTRATOR)` is `interaction.permissions.administrator`,
  checked after `interaction.guild is None` (never true in a guild: discord.py creates a placeholder
  guild). A reply v3 rendered in `event.guild.locale` uses
  `(interaction.guild_locale or interaction.locale).value` (WelcomeByeGuild's `_guild` and
  `_reply`).
- A v3 reply posted with `event.channel.sendMessage(...)` after the defer: send it to
  `interaction.channel` when that has `send` (a `runtime_checkable` Protocol, so fakes need no
  discord base class; forums and categories have none), then `delete_original_response()`; on
  `discord.HTTPException`, edit the deferred response into it instead (BasicCalculator's `_post`).
  When the reply is a whole operator template (v3 sent the built message: components and files
  too), send `content`, `embeds`, `view` and `files`, check the channel as `object` against a
  Protocol that takes them (discord.py's `send` overloads take a `View` or a `LayoutView`, never
  their union), and render again for the fallback, with the files as `attachments`: discord.py
  closes a message's files once it sent them, even when Discord refused it (SimpleCommand's
  `_postable` and `_send`).

### Listeners and intents

- Gateway events are `@commands.Cog.listener()` methods on the cog (`on_member_join`, `on_ready`);
  discord.py adds them with the cog and removes them when the plugin unloads. Check what each event
  needs cached: `on_member_join` builds the member from the event, `on_member_remove` fires only
  for cached members (use `on_raw_member_remove`: its `user` is the cached `Member` or else the
  `User`, its guild comes from `bot.get_guild(payload.guild_id)`, and JDA ignored the bot's own
  removal, so skip `bot.user`). A message sent to a guild channel goes through a
  `runtime_checkable` Protocol checked on the channel as `object`, and a refused one is a warning
  that names the guild and the channel (WelcomeByeGuild's `_postable` and `_greet`).
- `INTENTS` lists what the listeners need beyond discord.py's defaults:
  `discord.Intents(members=True)` for member events, and for `Guild.member_count`, which
  discord.py updates only from those events (BotInfo). The members intent is privileged: the
  design's smoke checklist says to allow it in the developer portal.
- Problems the operator must fix (a missing role or permission) are `logger.warning` lines from
  `logging.getLogger(__name__)` that name the plugin; Discord errors on one item are logged and the
  others still handled.

### Background loops and HTTP

- One `asyncio` task per loop, created in `cog_load` and kept on the cog (IntervalPusher's
  `tasks`), awaits `bot.wait_until_ready()` first: nothing runs before READY, `--no-online` (whose
  `async with bot` creates a READY event that never fires) cancels the waiting tasks when it
  unloads the plugin, and a plugin reloaded into a ready bot starts at once. `cog_unload` cancels
  the tasks and awaits them, so their resources close before the bot's HTTP client.
- v3's `delay(...)` after each iteration is a fixed delay: `while await step(): await
  sleep(seconds)`. `discord.ext.tasks.loop` schedules from each start (a fixed rate). Pass the
  loop's effects in (the request, the ping, `sleep`) so that tests drive it on a fake clock
  (IntervalPusher's `Pusher`).
- A failed step is logged and the loop goes on: catch the expected errors (`aiohttp.ClientError`,
  `OSError`, timeouts included) without a traceback and any other `Exception` with
  `logger.exception`. `asyncio.CancelledError` is no `Exception`, so cancellation stays quiet.
- Outgoing HTTP uses aiohttp, which discord.py installs and `xincord-plugins` declares: one
  `ClientSession` per loop, opened after READY with v3's limits as `ClientTimeout` and closed with
  the loop (`async with`); `allow_redirects=False` matches Java's `HttpClient`.
- A Discord REST call that JDA made without a discord.py counterpart goes through
  `bot.http.request(discord.http.Route(method, path))` (IntervalPusher's `rest_ping`).

### Templates and placeholders

- `Templates.load(lang)` in `setup`, so a broken template disables the plugin at load. Render with
  `render_message(templates.message(name, interaction.locale.value), values, build_id=IDS.build)`.
- v3's `Placeholder.get(event)` is `xincord.core.placeholders.placeholder_values(interaction)`
  (`actor_values(interaction.user, bot) | interaction_values(interaction)`, moved into the core by
  WelcomeByeGuild); `Placeholder.get(member)` and `Placeholder.get(user)` are
  `actor_values(member_or_user, bot)`. v3's `putGuild`, `putUser`, `putMember`, `putEvent` and
  `putTextChannel` with a prefix are `guild_values`, `user_values`, `member_values`,
  `event_values` and `channel_values` with that prefix (WelcomeByeGuild's `values.py`).
- Plugin keys keep v3's names (`_Example@option1`, `ga@title`) so operators' templates keep working.
- The core trims embed field names and values as JDA did and gives an empty one U+200E, which
  Discord would refuse otherwise (Feedbacker's empty feedback): no plugin-side workaround.
- A template that v3 rendered with `getCreateBuilder(key)` and no locale, such as a public message,
  renders in `lang.default_locale` for every user (SimpleCommand); one rendered with the user's
  locale uses `interaction.locale.value`. Without a substitutor, v3 used only its global keys:
  `bot_id` and `bot_name` (`_bot_values` in BotInfo and SimpleCommand; a third plugin that needs
  them moves the helper into `xincord.core.placeholders`).

### Components

- `IDS = ComponentIds("<package>", fields, legacy_prefix=..., legacy_hex=...)` in `cog.py`: v3's
  fields first, in v3 declaration order (`action` first in every v3 plugin), new fields appended;
  `legacy_prefix` is v3's `component_prefix` from `info.yaml` or `<lowercase name>@`; `legacy_hex`
  lists the fields v3 declared as `FieldType.INT_HEX` or `LONG_HEX`. A plugin without v3
  components has no legacy prefix.
- Templates set `uid: {action: ..., ...}`; `setup` calls `bot.route(__name__, IDS, handler)`. The
  handler gets `ParsedId` (values are strings), dispatches on `action`, and may raise: the core
  logs it with the plugin's name and upgrades legacy IDs on the message afterwards.
- `interaction.response.edit_message(view=...)` changes only the components; content and embeds
  stay.
- A plugin with v3 components routes them all to one `handle(interaction, parsed)` that dispatches
  on `interaction.type` and `parsed.fields["action"]`, as v3's `onButtonInteraction` and
  `onModalInteraction` did; other actions get no response. The core parses v3's IDs and upgrades
  the message after the handler, so the handler compares the pressed ID as it came (Feedbacker).
- A button that opens a modal answers `interaction.response.send_modal(render_modal(
  templates.modal(name, interaction.locale.value), values, build_id=IDS.build))`; the modal's
  `uid` keeps v3's keys, so its ID is routed like a button. Read the submission with
  `modal_values(interaction.data)` (labels and action rows). To change the button's message after
  the modal, edit `interaction.message` with the bot's token: rebuild its view with
  `View.from_message` (`LayoutView.from_message` when `message.flags.components_v2`), stop it and
  `message.edit(view=...)` (Feedbacker's `highlight`). A submission that posts elsewhere defers
  (`response.defer()`, a deferred message update) and reports a failure with
  `followup.send(..., ephemeral=True)`.

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
  module cannot import another one: tests that share helpers stay in one module (BasicCalculator's
  `test_replies.py`) or become fixtures in `conftest.py` (AutoRole's `guild`).
  A callback that reads the invoked command gets `FakeInteraction(command=SimpleNamespace(
  name=...))`. Close the `discord.File`s that a test receives (Components V2 templates with a
  `file_path`), or the unclosed files fail the run. For guild placeholders and guild commands,
  `FakeInteraction` takes `guild`, `guild_locale` and `permissions`; `FakeGuild` takes `channels`
  (`get_channel`), `preferred_locale`, `icon`, `rules_channel` and the other `GuildLike`
  attributes, and `as_guild()` casts it; `FakeChannel` has `type` and `mention`; `FakeMember` has
  the user and member attributes that placeholders read (`global_name`, `nick`, `avatar`, `roles`,
  `joined_at`); a logged-in bot's user is `monkeypatch.setattr(Bot, "user",
  property(lambda _bot: BOT_USER))` (WelcomeByeGuild's `test_members.py`).
  For components and modals: `FakeMessage` (components built with `discord.ActionRow(payload)`,
  `flags`, edits and deletion into `sent`, `channel.fetch_message` until deleted, `error`),
  `FakeResponse.send_message` and `send_modal`, `FakeInteraction.followup` and `not_found()`;
  route v3 IDs through `bot.on_interaction` to see the core's upgrade (Feedbacker's
  `test_routes.py`).
  Call cog methods directly (`cog.example_command(...)`), check a command's wiring through
  `bot.tree.get_command(...)` (its `binding` is the cog), send components through
  `bot.on_interaction(...)`, which includes the routing, and run listeners with
  `plugin_fakes.dispatch(bot, "member_join", member.as_member())` (`bot.dispatch` needs a bot that
  logged in). For guild data, `monkeypatch.setattr(bot, "get_guild", guilds.get)`; for a load into a
  ready bot, patch `Bot.is_ready` and `Bot.get_guild` before `load_plugin` (AutoRole's
  `test_check.py`).
- Loops (IntervalPusher's `conftest.py`): an autouse `ready` fixture builds
  `plugin_fakes.Ready(monkeypatch)`, which patches `Bot.wait_until_ready` (discord.py's raises
  before a login) and offers `set()`, `waiters(n)` and `close()`, which cancels the tasks left
  running at teardown; an autouse fixture patches `discord.http.HTTPClient.request` to record REST
  calls; `http_fakes.running_monitor()` runs `Monitor`, a local HTTP server that answers each path
  with a status, can leave requests unanswered (answered when it closes, or its teardown waits for
  the client's timeout) and records them. Never sleep in real time: inject the clock, and wait on
  events (`monitor.received(n)`, `ready.waiters(n)`) under a timeout. `bot.remove_cog(name)` runs
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
- Pure functions get one requirement each when they can be stubbed separately (BasicCalculator:
  trimming, reading, results, powers, then `calculate` with the golden files), so that each xfail
  commit fails for its own stub.
- Never unload or reload the real plugin in a test: discord.py re-imports its modules, and later
  tests compare against classes from the old ones. The core's reload tests use fake plugins.
- ruff, pyright, pytest and coverage already cover `packages/` and `tests/`; nothing to configure
  per plugin.
