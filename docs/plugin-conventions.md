# Plugin conventions

How the bundled plugins are built; Example (`xincord.plugins.example`) is the template to copy, and
`docs/plugin-api.md` lists the core names that plugins may use.

## Layout and loading

- One package per plugin, `xincord.plugins.<package>`: `__init__.py` (metadata constants and
  `setup`), `config.py`, `cog.py`, the bundled `config.yaml` and `lang/`. The entry point in the
  `xincord.plugins` group is named after the plugin (`Example = "xincord.plugins.example"`).
- A plugin without settings ships no `config.yaml` (Calculator). A plugin without text ships no
  `lang/`, has no `DEFAULT_LOCALE` and never calls `context.lang` (AutoRole). Operator problems
  are `logger.warning` lines that name the plugin.
- Logic that needs no Discord lives in its own module and is tested directly
  (`calculator/calculator.py`); the cog only renders and sends. CPU-bound work runs in
  `asyncio.to_thread`.
- Code that two plugins share lives in a package under `xincord.plugins` without an entry point
  (VoiceLogger's and ChatLogger's `xincord.plugins.listen_channels`): neither plugin needs the
  other, and discord.py, which drops a plugin's own modules when it unloads it, leaves the package
  imported, so it holds no state. What differs is passed in (`ListenSettings(store, namespace)`,
  `Menu(lang, templates, ids, key, template)`); each plugin builds its command group in its own
  module, so that unloading the plugin removes it.

## Commands

- Commands are built in `setup` from the plugin's Lang: `app_commands.Command` with the cog's
  bound method as the callback, then `rename` and `describe` on the command.
- A global command sets `extras={"global": True}` and the contexts that discord.py does not send
  by default: `allowed_contexts=AppCommandContext(guild=True, dm_channel=True,
  private_channel=False)` and `allowed_installs=AppInstallationType(guild=True, user=False)`
  (BotInfo).
- Commands that differ only by their template share one callback that reads
  `interaction.command.name` (CustomCommands), and
  `app_commands.default_permissions(administrator=True)` limits a command to administrators by
  default (WelcomeGoodbye, Economy, Giveaway).
- Commands that differ in their handler take a `kind` in the `COMMANDS` table, and `command(name)`
  builds each with the matching bound method (Economy's `balance`, `board` and `change`).
- A command with subcommands is an `app_commands.Group` built in the plugin's `cog.py` with
  `default_permissions` set on it, and one `app_commands.Command` per subcommand whose callback is
  the cog's bound method, localized from `<root>.subcommands.<name>.*` with one `rename` and one
  `describe` call each (DynamicVoiceChannel's `command`).
- Commands that the operator defines in the plugin's `config.yaml` (CustomCommands): one model per
  entry, each value checked against what Discord and discord.py take (discord.py's `validate_name`
  for the name, the core's `is_command_name` for localized names, `DESCRIPTION_MAX`,
  `discord.Locale`, `discord.Permissions.VALID_FLAGS`); `setup` checks what needs several entries
  or the lang files (names unique in every locale, no more commands than the room left of
  Discord's 100, counted with `bot.tree.get_commands(type=discord.AppCommandType.chat_input)`, and
  templates that exist in the default locale and render once at load with no values, ID builder
  or models) and raises one `ConfigError` with a `<file>: <key>: <problem>` line each
  (`checks.py`). Names and descriptions are localized with the core's
  `localized(default, translations)` instead of `register.yaml`; `extras["guilds"]` limits a guild
  command to some guilds; a public reply sets `extras["defer"] = False` and defers with
  `response.defer(thinking=True)`; a response that Discord refuses is deleted with a warning, so
  that no public "thinking" message stays. A key whose default Python cannot hold (zh-TW text) is
  required, and the bundled file holds it.
- A command option limited to some channel types uses an `app_commands.Transformer` with those
  `channel_types` (WelcomeGoodbye's `TextChannelOption`); the handler checks the type again, and a
  command that falls back to the current channel checks `interaction.channel` the same way.
- A runtime Administrator check reads `interaction.permissions.administrator`; replies in the
  guild's locale use `(interaction.guild_locale or interaction.locale).value` (WelcomeGoodbye).

## Components and replies

- Component IDs: `ComponentIds("<package>", <fields>, legacy_prefix=<prefix>)`, routed with
  `bot.route(__name__, IDS, handler)`. A plugin with legacy IDs lists their fields in their order
  and routes them to one `handle` that dispatches on the interaction type and the `action` field;
  other actions get no response. The core parses legacy IDs and upgrades the message afterwards
  (Feedback). A legacy prefix whose IDs carried no fields (Economy's `economy@`) gets
  `ComponentIds("<package>", ("action",), legacy_prefix=...)` and a handler that ignores the
  fields; the decoder reads the prefix alone or with `<letter>:<value>` segments.
- A button that opens a modal answers with `interaction.response.send_modal(render_modal(...))`
  and may edit its own message afterwards with the bot's token; the modal's submission is routed
  like a button and read with `modal_values(interaction.data)` (Feedback's `press_star` and
  `submit_form`).
- A reply posted to the channel goes to `interaction.channel` when it has a `send` method
  (Calculator's `Postable` protocol: forums and categories have none), then the deferred response
  is deleted; on `discord.HTTPException` the reply replaces the deferred response instead.
- A whole operator template posted to the channel carries its `view` and `files` too; the fallback
  into the deferred response renders it again (CustomCommands' `_postable` and `_send`).
- A public message renders in the default locale for every user (CustomCommands' posts and public
  replies); an ephemeral reply follows the user's locale.
- Replies kept in a plugin's `config.yaml` (Feedback) are `Annotated[str,
  StringConstraints(pattern=r"\S", max_length=2000)]`: Discord refuses an empty message or one over
  2000 characters. Optional replies get English defaults (no CJK in Python) and zh-TW texts in the
  bundled file.
- Messages to channels that a command set up (VoiceLogger's listen channels) go through
  `bot.get_partial_messageable(id, guild_id=...)`, which needs no cache and reaches archived
  threads; a `discord.NotFound` forgets the channel's settings, another refusal is a warning, and
  the other channels still get the message.
- Ephemeral panels that refresh themselves (MusicPlayer) are tasks per member that edit the panel
  through its latest interaction, stop at their expiry, a refused edit, the member's next panel,
  the guild's player stopping or the unload, and log the error that ends one (nothing awaits
  them). A press acknowledges at once (`response.defer()`), then edits the panel.

## Text and placeholders

- Texts outside the templates go to a `text.yaml` per locale (no CJK in Python), with plugin
  placeholders such as `%ga@...%` rendered in one pass; a message's texts and its template come
  from one locale: the plugin's files for the user's locale, else zh-TW for a Chinese locale and
  en-US for another (Giveaway's `texts.language`).
- A plugin whose texts are English first (NtustCourseWatch) ships them in `lang/en-US/` as its
  default locale and translates them in `lang/zh-TW/`: replies follow the member's locale, public
  posts use the default locale, and command names stay the same in every locale.
- An interaction's placeholder values are `xincord.core.placeholders.placeholder_values(interaction)`;
  a member's are `actor_values(member, bot)`. Templates rendered without a user get
  `global_values(interaction.client)`, the bot's keys; CustomCommands' operator templates get
  `placeholder_values(interaction)`: the bot's keys and the user's and the channel's.
- A template whose first embed's description is the template of rows (Economy's boards) is
  checked in `setup` for every locale, so that a broken one fails at load with the file named
  (`check_boards`).
- Bundled text that would hold a real account number ships an all-zero example under a comment
  (CustomCommands); operators' files under `plugins/<Name>/lang/` keep their values, because only
  missing lang files are exported.

## Config

- A config value that Discord would refuse at send time (a URL, a length) is validated in the
  model, so that the plugin fails at load with the key named (BotInfo's `source_url`).
- A list that must not be empty and would ship with real IDs (Economy's `admin_id`) has no default
  and ships empty, so that the plugin waits for the operator and the error names the key.
- Keys of a dropped feature (Economy's Google Sheets keys) are not fields: files that hold them
  load and warn about them, as about `enabled`.
- Amounts (Economy's money and cost) are Python integers: exact, never wrapped, never floats; the
  store's JSON keeps them exact.

## Data

- Per-guild data is a document in the store's key-value table under the plugin's name and the
  guild ID; a missing document or field reads as its default; read-only paths never write;
  read-modify-write runs under `store.lock("<Name>:<guildId>")`, because discord.py runs handlers
  concurrently. The data goes with `on_guild_remove` and, from `on_ready` and `cog_load` in a
  ready bot, for every guild the bot is no longer in (WelcomeGoodbye's `store.py` and
  `forget_left_guilds`).
- A change that must not lose a concurrent one is a single `Store.update(namespace, key, fn)`: `fn`
  runs in one transaction on the store's thread, reads the document and returns a new one, and
  passes what the caller needs back through a list it appends to (Economy's `store.change`).
  `store.lock(...)` around `get` and `put` serializes only the plugin's own coroutines
  (WelcomeGoodbye).
- Data that must not lose a concurrent change and may also change nothing (joins, draws) runs a
  pure transition under the guild's `store.lock`, reading, then writing only a changed document
  (Giveaway's `Giveaways.change`); the automatic draw takes the same lock, so that a draw happens
  once.
- A guild's data stays when the bot leaves the guild when it may hold real value (Economy's
  wallets); other plugins delete theirs on leave (WelcomeGoodbye).
- Settings kept per channel inside a guild's document (`{"<channelId>": {...}}`) are changed one
  channel at a time under the guild's lock; a change that changes nothing writes nothing
  (`xincord.plugins.listen_channels.store`, shared by VoiceLogger and ChatLogger).
- A plugin with a second kind of per-guild data keeps it in its own namespace, `<Name>.<kind>`
  (DynamicVoiceChannel's `DynamicVoiceChannel.rooms`), so that the plugin's namespace keeps one
  kind of document.
- Channels that a plugin creates and must clean up are tracked in the store per guild, once nothing
  is lost by deleting them (DynamicVoiceChannel tracks a room once the lobby's copy exists), and
  checked when the bot is ready and when the plugin loads into a ready bot: empty ones are deleted
  and missing ones forgotten, in available guilds only. A refused deletion keeps the record, so
  that a later event tries again.
- Data that grows with the guilds' traffic and is kept for years (ChatLogger's messages, five years
  by default) lives in the plugin's own SQLite files under `context.data_directory`
  (`data/<Name>/`, in the `data` volume; the core never creates it), on a thread of the plugin's
  own with one connection per file, opened in `cog_load` and closed in `cog_unload` after the work
  under way (ChatLogger's `MessageFiles`). Files hold ranges of snowflakes and are named after the
  UTC second where each starts (`files.py`): every operation goes to the one file holding its ID;
  a new file starts after the newest stored ID once the newest file's page count reaches the size
  limit, so that no row moves; the retention deletes the files whose range ended before it and the
  other files' older rows in batches, at READY and every hour. Small plugin tables that need
  queries can still live in the core store (`<Plugin>_<table>` through `Store.run`).
- State that a builder keeps between interactions (Giveaway's drafts) lives on the cog, keyed by
  user and guild, with the ID of the message that shows it; every change answers through the
  interaction that made it (`response.edit_message`), never through an older interaction's token.
  A confirmation takes the state before its first await, so that a second press finds none.
- Values drawn at random come from `random.SystemRandom()` kept on the cog, which tests replace
  with a seeded `random.Random`; the pure draw takes the generator as an argument.

## Events and background work

- Gateway events are `@commands.Cog.listener()` methods on the cog, which discord.py adds and
  removes with it; `INTENTS` declares what they need (`discord.Intents(members=True)` for member
  events, AutoRole). Work that needs guild data runs from an `on_ready` listener and from
  `cog_load` when `bot.is_ready()`, because `on_ready` does not fire again for a plugin reloaded
  into a running bot; it skips guilds that are `unavailable`.
- A plugin that reads members' statuses declares `discord.Intents(members=True, presences=True)`:
  both are privileged, and the smoke checklist says to allow them in the developer portal
  (TicketAwayNotice).
- A gateway event that discord.py does not parse is relayed with `bot.relay_gateway_event(<name>)`
  in `setup` and handled by a cog listener `on_gateway_<name in lower case>(payload)` that
  validates Discord's payload (VoiceLogger's `parse_update`). The relay lasts as long as the bot;
  a reload only adds the listener again.
- Audit log entries of types that discord.py does not know are read raw and matched by type,
  channel and time, never taken as "the guild's newest entry" (VoiceLogger's `status.match`).
- A sequence of Discord requests that a later event must not interleave with (a room's creation
  and its deletion) runs under a per-guild lock from `store.lock`, which survives reloads; the
  cache state that decides it (a voice channel's members) is read before the first await.
- A background loop is a task per loop that `cog_load` creates and that awaits
  `bot.wait_until_ready()` first, so that nothing runs before READY or under `--no-online`, and a
  plugin reloaded into a ready bot starts at once; `cog_unload` cancels the tasks and awaits them.
  The loop's effects (the request, the clock's `sleep`) are passed in, so that tests run it on a
  fake clock; one failed step is logged and the loop goes on (UptimeHeartbeat's `Pusher` and cog).
  A step that keeps failing logs each kind of failure once per episode, the rest at debug level,
  and one info line once it has worked three times in a row (UptimeHeartbeat's `Failures`).
- Work that an event starts and that waits (TicketAwayNotice's notice) is an `asyncio` task that
  the listener creates after the checks that need no await, kept in a set on the cog
  (`add_done_callback(set.discard)`) and cancelled and awaited in `cog_unload`, which first sets a
  `closed` flag that the listener checks; it waits on the cog's `sleep`, which tests replace,
  checks the cache again when the wait ends (the channel, the guild, the member's status), and logs
  any failure that it does not handle with `logger.exception`, because nothing awaits it. The
  listener returns at once, so that the wait holds no other event up.
- Background work over several independent sources runs one loop per source in a `TaskGroup`
  inside the plugin's single task, so that one source's long waits hold up no other; a shared
  `asyncio.Semaphore` bounds the requests themselves (NtustAnnouncements' boards).
- A plugin that watches items that members register (NtustCourseWatch's courses) asks the
  external API about one registered item per step, the items in turn, at most once per `interval`
  seconds (a config key with a minimum, so that the bot cannot hammer the API), and only from the
  configured start while anything is registered. Repeated alerts are throttled per channel and
  item, and a state change (full) is announced once per alert; the posts are tasks that hold up no
  step, tracked on the cog and cancelled in `cog_unload`.

## Network and services

- Outgoing HTTP goes through aiohttp, one `ClientSession` per loop opened after READY and closed
  with the loop (UptimeHeartbeat's `open_session`); tests send it to `http_fakes.Monitor`, a local
  server. A URL that carries a secret, such as a push token, appears in logs as its origin only;
  error texts and tracebacks have their URLs cut and the secret URL's parts removed, and config
  errors hide their input (UptimeHeartbeat's `logs.py` and `Config`).
- A plugin that scrapes pages (NtustAnnouncements) parses them with the standard library
  (`markup.py`'s tree and selectors), keeps the pages it needs as trimmed and anonymized copies of
  the live ones under `tests/fixtures/plugins/<package>/` (fetched once, the date in a comment),
  and keeps the exact URL strings where they are an item's identity (the stored lists). Its tests
  refuse every host but this machine's (an autouse `offline` fixture on aiohttp's resolver), so
  that a test that forgot a fake never reaches the site.
- Calls to an LLM API go over its documented REST API with aiohttp (no SDK); keys are config,
  validated with hidden input, named in logs by their position and removed from error texts, and
  shared within a client-side rate limit (`conversion.KeyRing`) with a retry schedule on the
  injected `sleep` (NtustAnnouncements). Every setting of the model is a config key and a reload
  applies it: the request format (`gemini` or an OpenAI-compatible `openai`), the endpoint with its
  version path, the model, the generation settings (null sends none), the timeouts, the rate limit
  and the retries. Logs and module names name no product, the endpoint shows only as its origin
  (`xincord.plugins.redaction`), and URLs in error texts are cut to theirs.
- A plugin that plays audio (MusicPlayer) talks to a Lavalink node in compose through narrow
  Protocols of its own (`audio.Link`, `audio.Player`, `audio.Listener`): the cog and the per-guild
  sessions only see them, `node.py` implements them with lavalink.py, the cog's tests give fakes
  (`tests/support/music_fakes.py`) and the adapter's tests a local fake node
  (`tests/support/lavalink_fakes.py`). The plugin keeps what plays next (its history) and starts
  one song at a time on the node; the link is created at READY and closed, after leaving voice in
  every guild, by `cog_unload`.

## Tests

- Tests live in `tests/plugins/<package>/` and load the real plugin through its entry point
  (`plugin_fakes.load_plugin`); Discord fakes are in `tests/support/discord_fakes.py`; the
  bundled texts per locale are golden data in `tests/fixtures/plugins/<package>/golden.yaml`.
- Recorded answers (Calculator's JSONL) live in `tests/fixtures/plugins/<package>/` unchanged;
  records that a later fix changes are checked against an independent implementation in the test,
  never edited.
- Tests run listeners with `plugin_fakes.dispatch(bot, "<event>", *args)` and write an operator
  config with `plugin_fakes.load_plugin(..., config=...)`; `discord_fakes` has `FakeGuild`,
  `FakeRole` and `FakeMember` for member events.
- Tests of message events feed discord.py's own parsers: `tests/support/payloads.py` builds the
  payloads, `plugin_fakes.add_guild` caches a guild, and `plugin_fakes.gateway` runs the listeners
  that the parsers dispatched (ChatLogger's `scene` fixture).
