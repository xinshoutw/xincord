# Pitfalls and verified facts

What earlier sessions checked the hard way: discord.py, Discord, the tools and the tests
(moved from `HANDOFF.md` on 2026-10-12).

## Working tips

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
- OpenSpec is not installed globally: run the pinned CLI through npx as `HANDOFF.md` shows. Telemetry is also off in `~/.config/openspec/config.json`.
- Per change: propose, `validate --strict`, commit; xfail and implementation commits; porting-guide
  rows; push; `gh run watch <id> --exit-status`; `archive <name> --yes`; `validate --all --strict`;
  commit; push.

## Verified facts and pitfalls

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
- After a discord.py upgrade, check the internals that plugins call: UptimeHeartbeat's REST ping
  (`HTTPClient.request` and `Route`: pushes must carry a real ping, not `-1`), DynamicVoiceChannel's
  position PATCHes (`Route`), VoiceLogger's relay (`ConnectionState.parsers`) and its audit log
  request, and ChatLogger's relayed `MESSAGE_CREATE`.
- A request that empties a rate-limit bucket returns only after the bucket resets
  (`Ratelimit.__aexit__` sleeps in `_refresh`), although Discord applied it at once; command
  uploads (about two bulk overwrites a minute per route) wait so, silently below DEBUG.
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

- NTUST's course query (`POST https://querycourse.ntust.edu.tw/QueryCourse/api//courses`) no longer
  answers v3's whole-catalogue request (`CourseTeacher: " "`): on 2026-10-11, no answer in 60 s,
  then `500 {"Message": ...}` after 120 s. It matches `CourseNo` as a prefix (a code's request
  answers in under a second) and lists a course once per room and time with the same counts; take
  only whole codes, or a short one asks about a department. A client timeout shorter than a
  server's slow query piles queries up there.
- PyYAML reads a timestamp with an offset as an aware `datetime` and one without as naive, which
  the container would take as UTC: pydantic's `AwareDatetime` requires the offset. YAML 1.1 reads
  `0115` as octal 77, which `coerce_numbers_to_str` turns into `"77"`.
- Chinese input methods type full-width letters and digits: NFKC turns them into ASCII before a
  code is checked. Python's `\d` and `int()` take digits outside the BMP, which Kotlin's UTF-16
  strings saw as surrogates, no digits.
- One `Failures` for several items that a loop checks in turn ends a failing item's episode with
  the others' successes: keep one per item.
- A task that nothing awaits until the unload hides the error that ended it: log it from a done
  callback (`task.exception()` also marks it retrieved).

- lavalink.py 5.11.1 (MusicPlayer): `DefaultPlayer.handle_event` plays the next song of its own
  queue at each end that may start one; `player.current` stays set after a song ended and is the
  `track` of the next end event; event hooks run as unawaited tasks, the player's `handle_event` in
  order in the message's task; a 401 stops its reconnects for good; it sends the voice state's
  `channelId` only with a new voice session (a move keeps it: drop the cached `sessionId`);
  `player_manager.destroy` of an unknown guild asks every node to delete it; its requests take
  aiohttp's 5-minute default unless `request_timeout` is given (`total` leaves its WebSocket
  alone); it ships an sdist only and no `py.typed` (`# pyright: ignore[reportMissingTypeStubs]` on
  the import); its client's connector option `enable_cleanup_closed` makes aiohttp warn on Python
  3.14 (ignored in pytest).
- The Lavalink 4.2.2 image: the Ubuntu variant (glibc 2.35) for DAVE, not Alpine; `curl` inside;
  uid 322; plugins downloaded at each container creation; `/version` needs the password; no log
  files unless configured; request logging (on in Lavalink's example) logs every search, and
  `lavalink.server.player.AudioLoaderRestHandler` logs each load's identifier at INFO (WARN in
  `lavalink/application.yml`).
- discord.py voice protocols (MusicPlayer's cross-review): READY after a new gateway session (not a
  resume) empties discord.py's voice clients without calling them; a voice state goes to the
  protocol the guild has when it arrives, so Discord's late answer to a leave reaches the next
  connection; `VoiceProtocol.cleanup()` removes whatever the guild has registered; and
  `channel.connect` releases a protocol only after a timeout. What a command checks before an
  await (a load, a lock, the node) may be gone after it: decide under the session's lock.
- compose's `${VAR:?message}` fails every compose command while `VAR` is unset (`run --rm -T bot
  --no-online` included): the image check needs `.env`. A healthcheck string with `: ` in a block
  list must be quoted, or YAML reads a mapping.
- discord.py's `Client.__init__` warns that PyNaCl and davey are missing ("voice will NOT be
  supported"): its own `VoiceClient`; a `VoiceProtocol` for Lavalink needs neither.
- A component interaction's `response.defer()` is a deferred update (type 6), and its
  `edit_original_response` / `delete_original_response` edit or delete the pressed message, an
  ephemeral one too (MusicPlayer's probe); a command's response message ID comes from
  `edit_original_response`'s return value.
- Without the project's hooks, `ruff check --fix` deletes an import that nothing uses yet: add
  imports with the code that uses them, or check after the fix. A text replacement anchored on a
  line that the formatter reflowed silently matches nothing: assert the anchor (a script with
  `assert old in text`).

- pydantic passes exceptions other than `ValueError` and `AssertionError` out of validators
  unchanged: a `BeforeValidator` that raises `NotImplementedError` stubs a new config key for
  xfail-first while files without the key still load. A `field_validator` reads the fields declared
  before it (defaults included, failed ones left out) in `ValidationInfo.data` and names its own
  key; a model validator's error reads `<root>` in the core's messages.
- discord.py's log format prints each record's logger name, the module's path: a module named
  after a product names it on every line (NtustAnnouncements' `gemini.py` became `conversion.py`).
- pydantic's lax numbers read YAML's `yes`, `on` and `true` as 1; `Field(strict=True)` refuses them
  (a strict float still takes an integer; make a tuple's items strict, since a strict tuple
  refuses YAML's lists). Check URLs that aiohttp requests with yarl: `urlsplit` takes a backslash
  in the host that yarl refuses, and yarl takes port 0. Read a clock once per decision: a limiter
  that reads it again to compute a wait can find the oldest attempt gone.
- A module that `config.py` imports must not import one that imports `config.py`
  (NtustAnnouncements' `pages.py` imports `Layout`): put such helpers in a module that imports
  nothing of the plugin (`strings.trim`).
- OpenAI's reasoning models refuse a temperature other than their default and `max_tokens`;
  Ollama's OpenAI-compatible endpoint takes `max_tokens` (no `max_completion_tokens`) and ignores
  the key; Gemini's is `https://generativelanguage.googleapis.com/v1beta/openai/` with a bearer key;
  aiohttp refuses an `Authorization` header together with credentials in the URL (`ValueError`).

- pyright does not narrow a union with `==` against a string literal (`found == "error.admin-only"`
  leaves `Entry | str`, since a class may define `__eq__`): narrow with `isinstance`, or pass the
  literal on (Ticket's `delete` in the xfail commit of `ticket-staff-controls`).
- discord.py's `Member.roles` lists @everyone, the default role whose ID is the guild's, among every
  member's roles; JDA's `getRoles()` left it out. Leave it out before matching configured role IDs
  (Ticket's `_role_ids`, found in `ticket-staff-controls`' cross-review).

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions, guild filters that never applied, delayed messages that nothing could cancel or check
again, alerts posted at every poll beyond Discord's rate limit, and songs queued forever after
the end of a list, refusals that never reached the member and refresh tasks that ran forever (the
porting guide has the full list).

**Exact numbers (Calculator):** `decimal` defaults to 28 digits, and `Fraction` reduces with a
gcd that costs 75 to 180 ms per operation at 100,000 digits; scaled integers (v3's `BigDecimal`)
cost a few milliseconds. Python refuses `str()`/`int()` conversions over 4,300 digits and computes
`10**999999999` if asked: bound sizes first.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
