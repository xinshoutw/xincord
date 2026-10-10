# Porting guide: XsDiscordBotKt to xincord

How Kotlin/JDA concepts map to Python/discord.py in this project, which ideas from the abandoned
v4 rewrite are kept, the traps found so far, and every place where xincord deliberately behaves
differently from v3. Update it after each Core change and each plugin.

Baseline: XsDiscordBotKt `main` at `3a59607` (v3.4). Decisions: `docs/porting/decisions.md`.

## Concept mapping

| Kotlin / JDA (v3) | Python / discord.py (xincord) | Decision |
|---|---|---|
| Plugin jar + `info.yaml`, classloader per plugin | extension module + `commands.Cog`, metadata as module constants (`DEPENDS`, `SOFT_DEPENDS`, `INTENTS`), entry point in group `xincord.plugins` named after the plugin | B2, B3 |
| `enabled` key in each plugin config | the core config's `plugins` list; `setup(bot)` calls `bot.plugin_context(__name__)` for `config(Model)` and `lang(locale)` | B3, B6 |
| "API plugins" (SQLiteAPI, GoogleSheetAPI, AudioAPI) | ordinary dependencies or nothing | B12 |
| `PluginEventConfigure.load()`: export lang, read config, build the `StringLocalizer` | `setup(bot)`: `context.lang(DEFAULT_LOCALE)`, `context.config(Config)`, `Templates.load(lang)`, then `bot.add_cog`, `bot.tree.add_command(cog.command())` and `bot.route` | B3 |
| `Placeholder.get(event)` / `Placeholder.get(member)` | `placeholder_values(interaction)` (`actor_values(interaction.user, bot) \| interaction_values(interaction)`) / `actor_values(member, bot)`, plus the plugin's keys | B10 |
| Load order from `depend` / `soft_depend` | `graphlib.TopologicalSorter`; a failing plugin disables only itself | B3 |
| `GatewayIntent` presets | `discord.Intents` aggregated from enabled plugins before connecting | B4 |
| `ListenerAdapter` overrides | `@commands.Cog.listener()` | B3 |
| `CommandData` / `SlashCommandData` | `app_commands.command` / `app_commands.Group` | B5 |
| InteractionLogger's blanket `deferReply(true)` | `CommandTree.interaction_check` defers ephemerally; commands that open modals set `extras={"defer": False}` | B5 |
| `guildCommands()` / `globalCommands()` | guild commands by default, global with `extras={"global": True}` and JDA's default contexts set explicitly; `CommandTree.sync_global` / `sync_guild` upload only changed payloads | B5 |
| Command localization via `StringLocalizer` and Kotlin property paths | `app_commands.Translator` fed from `lang/<locale>/register.yaml` keys | B7 |
| `MessageCreator` YAML templates | templates module: v1 YAML tags and Components V2 | B10 |
| `Placeholder` / commons-text substitutor | single-level `%key%` substitution with a fresh context per render | B10 |
| `checkComponentIdPrefix` / `checkModalIdPrefix` in every plugin listener | `bot.route(__name__, ids, handler)` in `setup`; the handler gets the interaction and a `ParsedId` | B9 |
| `ComponentIdManager` (`{prefix}{a..z}:{value};...`) | `ComponentIds`: `{namespace}:1:{letter}={value};...` plus the permanent v3 decoder; `upgrade_view` rewrites legacy IDs | B9 |
| `event.replyModal(ModalCreator...)` and `ModalInteractionEvent.getValue(id)` | `interaction.response.send_modal(render_modal(...))` and `modal_values(interaction.data)[id]` (`xincord.core.templates`) | B10 |
| `event.deferEdit()` on a modal submission, then the bot's own sends | `interaction.response.defer()` (a deferred message update), then `interaction.followup.send(..., ephemeral=True)` for a reply | B5 |
| `component.withStyle(...)` on the message's rows, `editOriginalComponents` | `View.from_message(...)` (`LayoutView` for Components V2), change the items, `view.stop()`, `interaction.message.edit(view=...)` (Feedback's `highlight`) | |
| `getOption("member").asMember` | a `discord.Member \| discord.User` option, checked against `MemberLike`: discord.py passes the user when Discord resolved no member | |
| `getOption("member").asUser` | the same option without the check: any user, in the guild or not (Economy) | |
| `Placeholder.globalSubstitutor`, used by `getCreateBuilder(key, locale)` without a substitutor | `global_values(interaction.client)` (`bot_id`, `bot_name`; `xincord.core.placeholders`) | B10 |
| Kotlin `Int` amounts (32 bits, wrapping) | Python `int`: exact and unbounded; JSON keeps them exact (Economy) | |
| JDA's `addField`: trimmed name and value, U+200E for an empty one | the core's `render_message` does the same | B10 |
| JSON files and embedded MongoDB | SQLite (`sqlite3` + `asyncio.to_thread`), key-value table plus per-plugin tables; data kept for years in the plugin's own files under `data/<Name>/` (ChatLogger's messages) | B8 |
| `JsonGuildFileManager` (`plugins/<Name>/data/<guildId>.json`) | the store's key-value table: namespace = the plugin's name, key = the guild ID, value = v3's document unchanged, changed under `store.lock("<Name>:<guildId>")` or in one `Store.update` (Economy's wallets) | B8, B11 |
| `OptionData(CHANNEL).setChannelTypes(...)` | an `app_commands.Transformer` whose `channel_types` lists JDA's types and that passes on the `AppCommandChannel` (WelcomeGoodbye's `TextChannelOption`) | B5 |
| `event.member.hasPermission(ADMINISTRATOR)` | `interaction.permissions.administrator` (Discord's resolved permissions; Administrator cannot be set per channel) | |
| `setDefaultPermissions(DefaultMemberPermissions.enabledFor(...))` / `DefaultMemberPermissions.ENABLED` | `command.default_permissions = discord.Permissions(...)` / None (every member); `Permissions(0)`, like JDA's `DISABLED`, leaves the command to administrators | |
| `GuildMemberRemoveEvent` / `GuildLeaveEvent` | `on_raw_member_remove` (also uncached members) / `on_guild_remove` | B3 |
| kotlinx/Jackson YAML config | pydantic v2 models over PyYAML; unknown keys warn | B6 |
| Coroutines, `launch`, scheduled executors | `asyncio` tasks, `discord.ext.tasks.loop` | |
| A `CoroutineScope` job started in `load()` and cancelled in `unload()` | an `asyncio` task per loop created in `cog_load`, awaiting `bot.wait_until_ready()` first, cancelled and awaited in `cog_unload` (UptimeHeartbeat) | B3 |
| `delay(ms)` after each iteration (a fixed delay) | `while await step(): await sleep(seconds)` with `sleep` passed in; `tasks.loop` is a fixed rate | |
| Java `HttpClient` | `aiohttp.ClientSession` (installed with discord.py, declared by `xincord-plugins`) with `ClientTimeout`; `allow_redirects=False` keeps Java's default | |
| `jdaBot.restPing` | time `bot.http.request(discord.http.Route("GET", "/users/@me"))` (UptimeHeartbeat's `rest_ping`); discord.py has no REST ping | |
| JLine console (`JLineManager`, `JLineAppender`), `--ignore-update` | prompt_toolkit console (`xincord.core.console`; logs print above the prompt through `patch_stdout`), SIGHUP reload, `/xincord reload`; no version check | B15 |
| `Server/start`: `java -jar` with the token on the command line | `compose.yaml` and the `Dockerfile` image; the token goes in `bot/config.yaml` | B16 |
| `java -jar` with Clikt options | the `xincord` console script (`xincord.core.cli`, argparse); `--no-online` loads the plugins without connecting and exits | B15 |
| `BotLoader`: build JDA, wait for ready, then load the plugins | `Bot.setup_hook` sets the translator and loads the plugins before the gateway connects; `on_ready` and `on_guild_join` upload the commands | B3, B5 |
| `BotLoader.reload()`: stop JDA and start everything again | `Bot.reload(plugin=None)` in place: the loaded plugins follow `config.yaml`, or one plugin reloads with its dependents; triggered by SIGHUP, the owner's `/xincord reload` and the console | B15 |
| `StatusChanger` thread over `TYPE;text;ms` strings | `xincord.core.status.rotate` task, started on ready and restarted by a full reload | |
| `InteractionLogger` and `ConsoleLogger` listeners | `xincord.core.interaction_log.log` from `Bot.on_interaction`, after routing | |
| JDA's default mentions (all types ping) | the bot's `allowed_mentions`: users and the replied-to user; a message opts in with its own | B19 |
| `Commands.slash(...).addSubcommands(SubcommandData(...))` | an `app_commands.Group` built in the plugin's `cog.py` (its `module` comes from the creating frame, so unloading removes it) with `app_commands.Command` subcommands whose callbacks are the cog's bound methods (DynamicVoiceChannel) | B5 |
| `GuildVoiceUpdateEvent` (channel changes only) | `on_voice_state_update(member, before, after)`, which also fires for mutes, deafens and streams: compare the channels' IDs; read `channel.voice_states` before the first await | B3 |
| `AudioChannel.members.size` (voice state cache) | `len(channel.voice_states)`, which needs no member cache (`VocalGuildChannel.members` does) | B4 |
| `VoiceChannel.createCopy()` | `await channel.clone()`, which also copies the NSFW flag, the video quality and the slowmode | |
| `ChannelManager.setPosition(n)` (a raw position) | `bot.http.request(Route("PATCH", "/channels/{channel_id}", channel_id=...), json={"position": n})`; discord.py's `edit(position=...)` renumbers the guild's channels of the same sorting bucket in one bulk request | |
| `ChannelManager.putMemberPermissionOverride(id, allow, deny)` | `channel.set_permissions(member, overwrite=PermissionOverwrite(...))`, a `PUT` of that overwrite that keeps the others | |
| Embedded MongoDB collections (`CacheDbManager`, `MemoryCacheDb`) | one JSON document per guild in the store under `<Name>.<collection>` (DynamicVoiceChannel's rooms), changed under the guild's lock | B8 |
| `ChannelUpdateVoiceStatusEvent` (JDA parsed `VOICE_CHANNEL_STATUS_UPDATE` and cached each voice channel's status) | `bot.relay_gateway_event("VOICE_CHANNEL_STATUS_UPDATE")` in `setup` and a cog listener `on_gateway_voice_channel_status_update(payload)`; the plugin tracks the statuses itself (VoiceLogger) | B3 |
| `guild.retrieveAuditLogs().type(ActionType.X)` for types that discord.py does not know (192, 193) | `bot.http.request(Route("GET", "/guilds/{guild_id}/audit-logs", ...), params={"action_type": ..., "limit": ...})`, the raw entries: `Guild.audit_logs` drops their `options` (VoiceLogger) | |
| `guild.retrieveMemberById(id)` | `await guild.fetch_member(id)`, which raises `discord.NotFound` for a user who left | |
| `guild.getGuildChannelById(id).sendMessage(...)` to a channel that a command set up | `bot.get_partial_messageable(id, guild_id=...).send(...)`, which needs no cache; `discord.NotFound` means the channel is gone (VoiceLogger's listen channels) | |
| `deferEdit()` and `hook.editOriginal(MessageEditData.fromCreateData(...))` on a component | `interaction.response.edit_message(content=..., embeds=..., view=..., attachments=...)`: one type-7 response that replaces the message (`embeds=()` and `view=None` clear them) | B5 |
| `EntitySelectInteractionEvent.values` | `interaction.data["values"]`, snowflakes as strings, with `component_type` 5 to 8 | |
| `MessageReceivedEvent` | `bot.relay_gateway_event("MESSAGE_CREATE")` and a cog listener `on_gateway_message_create(payload)`, Discord's payload as the message was sent: `on_message` gets discord.py's cached `Message`, which an edit parsed before the listener runs changes in place; the bot's own messages come too, compare `bot.user.id` (ChatLogger's `created.py`) | B3 |
| `MessageUpdateEvent` (every `MESSAGE_UPDATE`, the message cached or not) | `on_raw_message_edit(payload)` with `payload.message`, the updated message that discord.py builds from the payload (since 2.5); `on_message_edit` needs the cached message | B3 |
| `MessageDeleteEvent` / `MessageBulkDeleteEvent` | `on_raw_message_delete(payload)` / `on_raw_bulk_message_delete(payload)`, uncached messages too; discord.py never splits a bulk deletion | B3 |
| `Message.contentRaw` and `getEmbeds()` | `message.content` and `message.embeds`; an embed's `type` is `rich` for bots' and webhooks' embeds and a preview type (`link`, `article`, `image`, `video`, `gifv`) for the ones Discord adds from links | |
| SQLiteAPI's `SQLiteFileManager` (ChatLogger: a file per guild, a table per channel) | the plugin's own SQLite files in `PluginContext.data_directory` (`data/<Name>/`): ChatLogger's `messages-<UTC second>.db`, each holding a range of message IDs, a new one when the newest reaches `max_file_size_mb`, one connection each on the plugin's own thread (`MessageFiles`); each operation one transaction | B8, B12 |
| Code that v3 copied between plugins (VoiceLogger's and ChatLogger's `ChannelData`, `JsonManager` and settings menu) | a package under `xincord.plugins` without an entry point that both plugins import (`xincord.plugins.listen_channels`: `ListenSettings`, `ListenChannels`) | B3 |
| An in-memory builder session per user and guild that renders through the slash command's `InteractionHook` (Giveaway's `StepManager`) | the cog's drafts per user and guild with the builder message's ID; each press or submission answers with `response.edit_message(...)` (type 7), so the builder outlives the 15-minute hook and an older builder answers that the session expired (Giveaway) | |
| `event.message.editMessage(...)` and `event.reply(...).setEphemeral(true)` on a post's button | `response.defer()` at once, then `edit_original_response(...)` with the whole post (the component's message, through the press's webhook, which no channel rate limit delays) and `followup.send(..., ephemeral=True)`; every press from the post shows it as stored, refusals included (Giveaway's joins and draws) | B5 |
| `guild.getTextChannelById(c).retrieveMessageById(m)` then `editMessage` | `bot.get_partial_messageable(c, guild_id=g).get_partial_message(m).edit(...)`: no cache, no fetch, any channel kind (Giveaway's automatic draw) | |
| `scheduleAtFixedRate(task, 5, period)` started in `load()` | a `cog_load` task: `wait_until_ready()`, `sleep(5)`, then a pass and `sleep(period)` in a loop; each pass logs its failure and the loop goes on (Giveaway) | B3 |
| `kotlin.random.Random.Default` and `shuffled(random).take(k)` | `random.SystemRandom()` on the cog (tests swap in a seeded `random.Random`) and `rng.sample(pool, k)`, the same distribution | |
| `DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")` (SMART) and `atZone(ZoneId.systemDefault())` | a regex with range checks, the day clamped to the month and `24:00` as the next day, then `datetime(..., tzinfo=zone).timestamp()` (fold 0 matches Java in gaps and overlaps); the zone is a config key, empty for the host's (Giveaway's `times.py`) | |
| `java.net.URI(value)` with an http(s) scheme and a host | `inputs.is_http_url`: RFC 2396's grammar with a server-based authority, `ipaddress` for IPv6 (Giveaway) | |
| Kotlin `String.toIntOrNull()` | `re.fullmatch(r"[+-]?\d{1,9}", text)` then `int(text)`: Unicode digits, no `_` | |
| User-facing texts hard-coded in Kotlin, chosen by a `zh` locale prefix | `lang/<locale>/text.yaml`, read with `Lang.text("text.<key>", locale)` and `%ga@...%` values in one pass; one locale for a message's texts and templates (Giveaway's `texts.language` and `Texts`) | B7 |
| Moshi data classes with defaults, `JsonGuildFileManager` | frozen dataclasses with `parse_*` (v3's defaults, `DataError` for anything else) and `*_json` in Moshi's field order; each operation parses only the entries it needs (Giveaway's `model.py`) | B8, B11 |
| camelCase keys in a v3 `config.yaml` | pydantic `Field(alias="camelCase")` on snake_case fields; validation errors name the alias (Giveaway's `Config`) | B6 |
| `category.createTextChannel(name)` and `addPermissionOverride(...)` (JDA copied the category's overrides first, `CategoryImpl.trySync`) | `category.create_text_channel(name, overwrites=...)` with the whole map: the category's overwrites when the bot is an administrator or holds every permission they set, then the channel's own; `Object(type=Role)` keys (uncached roles) left out, since discord.py would send them as member overwrites (Ticket's `tickets.overwrites`) | |
| `channel.upsertPermissionOverride(member).deny(VIEW_CHANNEL)` / `.grant(...)` | `channel.overwrites_for(member)`, change `view_channel`, `channel.set_permissions(member, overwrite=...)`: the other bits stay (Ticket's lock) | |
| `textChannel.createThreadChannel(name)` (public, no starter message) | `channel.create_thread(name=..., type=discord.ChannelType.public_thread)`: without a message and a type, discord.py creates a private thread | |
| `channel.createWebhook(name)`, `webhook.sendMessage(...).setThread(t).setUsername(...).setAvatarUrl(...)` | `channel.create_webhook(name=...)`, `webhook.send(content, files=..., username=..., avatar_url=..., thread=t, wait=True, allowed_mentions=AllowedMentions.none())`, `webhook.delete()` (Ticket's archive) | |
| `iterableHistory.order(FORWARD).cache(false)` and `takeAsync(100)` | `channel.history(limit=None, oldest_first=True)`, pages of 100 | |
| `Message.startedThread` | `Message.thread`, built from the REST payload's `thread` | |
| `attachment.proxy.downloadAsFileUpload(fileName)` | `await attachment.to_file()`; a file over `guild.filesize_limit` cannot be uploaded again | |
| `BreakIterator.getCharacterInstance(Locale.ROOT)` | no grapheme segmentation in the standard library: cut at code points, never inside a surrogate pair and never before a combining mark, a variation selector, an emoji modifier or around a zero-width joiner (Ticket's `thread_name`) | |
| `ChannelCreateEvent` (every channel kind, threads too) | `on_guild_channel_create(channel)` and `on_thread_create(thread)`, which discord.py dispatches for newly created threads only (`on_thread_join` otherwise); a `runtime_checkable` Protocol with `send` keeps the channels that take messages (TicketAwayNotice's `watch`) | B3 |
| `member.onlineStatus` with `GUILD_PRESENCES` and the `ONLINE_STATUS` cache flag | `member.status` with `discord.Intents(members=True, presences=True)`: the members intent keeps the members, the presences intent their statuses; a member from `fetch_member` has no presence and is `Status.offline`, as JDA's default (TicketAwayNotice) | B4 |
| `RestAction.queueAfter(delay, unit)` (nothing cancels it) | a task per message, started by the listener and kept in a set on the cog, that awaits the cog's injected `sleep`, checks the state again and then sends; `cog_unload` cancels the tasks (TicketAwayNotice's notices) | |
| Ktor Web-Dashboard | not ported | B13 |

## Intents kept from the v4 attempt (A3)

The v4 design spec stays in the old repository
(`XsDiscordBotKt@3a59607:docs/specs/2026-04-07-v4-core-refactor-design.md`); the branch analysis
is `docs/porting/analysis/research/v4-branch.md`. Kept:

- Plugins declare their surface (commands, components, listeners, load and unload hooks) instead
  of filtering every event themselves.
- Exact command-path dispatch: discord.py's tree already routes groups and subcommands; test that
  every command path has a callback.
- Prefix-routed persistent components that survive restarts (`discord.ui.DynamicItem`).
- Typed config models with defaults, validated at startup, failing loudly per plugin.
- Command localization from flat YAML keys; a missing name or description fails at startup instead
  of falling back to an empty string.
- A plugin manifest with dependencies and intents, sorted topologically, with a check for missing
  dependencies.

Rejected: a DI container (pass a small context object instead), classloader isolation, deferring
every component interaction centrally (it blocks modals), rewriting the template schema without
migrating the shipped YAML, silent fallbacks, reload as a full gateway reconnect, and two listener
styles at once.

## Plugin names

The owner renamed nine plugins on 2026-10-10 (`docs/porting/decisions.md`, Amendment 1). xincord
uses the new names for the entry point (the name under `plugins:`), `plugins/<Name>/`, the package,
the store namespace, the new-format component ID namespace and the OpenSpec capability; the
inventories, Kotlin citations, archived changes, placeholder keys and legacy component ID
prefixes keep the v3 names. The other plugins keep their names.

| v3 name | xincord name | Package |
|---|---|---|
| _Example | Example | `example` |
| BasicCalculator | Calculator | `calculator` |
| SimpleCommand | CustomCommands | `custom_commands` |
| WelcomeByeGuild | WelcomeGoodbye | `welcome_goodbye` |
| IntervalPusher | UptimeHeartbeat | `uptime_heartbeat` |
| Feedbacker | Feedback | `feedback` |
| TicketAddons | TicketAwayNotice | `ticket_away_notice` |
| NtustManager | NtustAnnouncements | not ported yet |
| NtustCourse | NtustCourseWatch | not ported yet |

`xincord.core.migrate_v3` (`RENAMED`) writes the new names in the `plugins` list and moves each
renamed plugin's v3 directory to `plugins/<new name>/`.

## Plugin conventions

Set by `port-example`; the full checklist is `.claude/skills/port-plugin/SKILL.md`, and Example
(`xincord.plugins.example`) is the template to copy.

- One package per plugin, `xincord.plugins.<package>`: `__init__.py` (metadata constants and
  `setup`), `config.py`, `cog.py`, the bundled `config.yaml` and `lang/`. The entry point is named
  after the plugin, with the owner's new name for a renamed one (`Example =
  "xincord.plugins.example"`; see "Plugin names").
- Commands are built in `setup` from the plugin's Lang: `app_commands.Command` with the cog's
  bound method as the callback, then `rename` and `describe` on the command; names and
  descriptions default to v3's.
- Component IDs: `ComponentIds("<package>", <v3 fields in v3 order, then new ones>,
  legacy_prefix=<v3 prefix>)`, routed with `bot.route(__name__, IDS, handler)`.
- Placeholder keys keep v3's names, and v3's `Placeholder.get(...)` values come from the core
  families (see the mapping above).
- Tests live in `tests/plugins/<package>/` and load the real plugin through its entry point
  (`plugin_fakes.load_plugin`); Discord fakes are in `tests/support/discord_fakes.py`; v3's text
  per locale is golden data in `tests/fixtures/plugins/<package>/golden.yaml`.
- Logic that needs no Discord lives in its own module and is tested directly
  (`calculator/calculator.py`); the cog only renders and sends. CPU-bound work runs in
  `asyncio.to_thread`.
- A plugin whose only v3 key was `enabled` ships no `config.yaml` (Calculator).
- A v3 reply posted with `event.channel.sendMessage` goes to `interaction.channel` when it has a
  `send` method (Calculator's `Postable` protocol: forums and categories have none), then the
  deferred response is deleted; on `discord.HTTPException` the reply replaces the deferred
  response instead.
- Recorded v3 answers (Calculator's JSONL) are copied to `tests/fixtures/plugins/<package>/`
  unchanged. Records that a fixed v3 defect changes are checked against an independent
  implementation in the test, never edited.
- Gateway events are `@commands.Cog.listener()` methods on the cog, which discord.py adds and
  removes with it; `INTENTS` declares what they need (`discord.Intents(members=True)` for member
  events, AutoRole). Work that needs guild data runs from an `on_ready` listener and from
  `cog_load` when `bot.is_ready()`, because `on_ready` does not fire again for a plugin reloaded
  into a running bot; it skips guilds that are `unavailable`.
- A plugin without text ships no `lang/`, has no `DEFAULT_LOCALE` and never calls `context.lang`
  (AutoRole). Operator problems are `logger.warning` lines that name the plugin.
- Tests run listeners with `plugin_fakes.dispatch(bot, "<event>", *args)` and write an operator
  config with `plugin_fakes.load_plugin(..., config=...)`; `discord_fakes` has `FakeGuild`,
  `FakeRole` and `FakeMember` for member events.
- A v3 global command (`globalCommands()`) sets `extras={"global": True}` and JDA's defaults, which
  discord.py does not send: `allowed_contexts=AppCommandContext(guild=True, dm_channel=True,
  private_channel=False)` and `allowed_installs=AppInstallationType(guild=True, user=False)`
  (BotInfo).
- A config value that Discord would refuse at send time (a URL, a length) is validated in the
  model, so that the plugin fails at load with the key named (BotInfo's `source_url`).
- Commands that differ only by their template share one callback that reads
  `interaction.command.name` (CustomCommands), and
  `app_commands.default_permissions(administrator=True)` stands for v3's
  `DefaultMemberPermissions.enabledFor(ADMINISTRATOR)` (WelcomeGoodbye, Economy, Giveaway).
- Commands that the operator defines in the plugin's `config.yaml` (CustomCommands, since
  `custom-commands-from-config`): one model per entry, each value checked against what Discord and
  discord.py take (discord.py's `validate_name` for the name, the core's `is_command_name` for
  localized names, `DESCRIPTION_MAX`, `discord.Locale`, `discord.Permissions.VALID_FLAGS`);
  `setup` checks what needs several entries or the lang files (names unique in every locale, no
  more commands than the room left of Discord's 100, counted with
  `bot.tree.get_commands(type=discord.AppCommandType.chat_input)`, and templates that exist in the
  default locale and render once at load with no values, ID builder or models) and raises one
  `ConfigError` with a `<file>: <key>: <problem>` line each (`checks.py`). Names and descriptions
  are localized with the core's `localized(default, translations)` instead of `register.yaml`;
  `extras["guilds"]` limits a guild command to some guilds; a public reply sets
  `extras["defer"] = False` and defers with `response.defer(thinking=True)`; a response that
  Discord refuses is deleted with a warning, so that no public "thinking" message stays. A key
  whose default Python cannot hold (zh-TW text) is required, and the bundled file holds it.
- A public message that v3 rendered with `getCreateBuilder(key)` and no locale renders in the
  default locale for every user (CustomCommands' posts and public replies); an ephemeral reply
  follows the user's locale.
- A whole operator template posted to the channel carries its `view` and `files` too; the fallback
  into the deferred response renders it again (CustomCommands' `_postable` and `_send`).
- Bundled text that held a real account number in v3 ships an all-zero example under a comment
  (CustomCommands); operators' files under `plugins/<Name>/lang/` keep their values, because only
  missing lang files are exported.
- v3's `Placeholder.get(event)` is `xincord.core.placeholders.placeholder_values(interaction)`
  (moved from Example by WelcomeGoodbye); `Placeholder.get(member)` stays
  `actor_values(member, bot)`.
- Per-guild data (v3's `JsonGuildFileManager`) is a document in the store's key-value table under
  the plugin's name and the guild ID, in v3's JSON shape so that the v3 data import (B11) can copy
  v3's files; a missing document or field reads as v3's default; read-only paths never write;
  read-modify-write runs under `store.lock("<Name>:<guildId>")`, because discord.py runs handlers
  concurrently. The data goes with `on_guild_remove` and, from `on_ready` and `cog_load` in a ready
  bot, for every guild the bot is no longer in (WelcomeGoodbye's `store.py` and
  `forget_left_guilds`).
- A command option limited to some channel types uses an `app_commands.Transformer` with those
  `channel_types` (WelcomeGoodbye's `TextChannelOption`); the handler checks the type again, and a
  command that falls back to the current channel checks `interaction.channel` the same way.
- A runtime Administrator check (v3's `member.hasPermission(ADMINISTRATOR)`) reads
  `interaction.permissions.administrator`; replies v3 rendered in the guild's locale use
  `(interaction.guild_locale or interaction.locale).value` (WelcomeGoodbye).
- A background loop is a task per loop that `cog_load` creates and that awaits
  `bot.wait_until_ready()` first, so nothing runs before READY or under `--no-online`, and a
  plugin reloaded into a ready bot starts at once; `cog_unload` cancels the tasks and awaits them.
  The loop's effects (the request, the clock's `sleep`) are passed in, so that tests run it on a
  fake clock; one failed step is logged and the loop goes on (UptimeHeartbeat's `Pusher` and cog).
  A step that keeps failing logs each kind of failure once per episode, the rest at debug level,
  and one info line once it has worked three times in a row (UptimeHeartbeat's `Failures`).
- Outgoing HTTP goes through aiohttp, one `ClientSession` per loop opened after READY and closed
  with the loop (UptimeHeartbeat's `open_session`); tests send it to `http_fakes.Monitor`, a local
  server. A URL that carries a secret, such as a push token, appears in logs as its origin only;
  error texts and tracebacks have their URLs cut and the secret URL's parts removed, and config
  errors hide their input (UptimeHeartbeat's `logs.py` and `Config`).
- A plugin with v3 components lists v3's fields in v3's order in `ComponentIds`, with v3's
  `component_prefix` as `legacy_prefix`, and routes them to one `handle` that dispatches on the
  interaction type and the `action` field; other actions get no response, as in v3. The core parses
  v3's IDs and upgrades the message afterwards (Feedback).
- A button that opens a modal answers with `interaction.response.send_modal(render_modal(...))`
  and may edit its own message afterwards with the bot's token; the modal's submission is routed
  like a button and read with `modal_values(interaction.data)` (Feedback's `press_star` and
  `submit_form`).
- Replies kept in a plugin's `config.yaml` (v3's Feedbacker) are `Annotated[str,
  StringConstraints(pattern=r"\S", max_length=2000)]`: Discord refuses an empty message or one over
  2000 characters. New optional replies get English defaults (no CJK in Python) and zh-TW texts in
  the bundled file.
- Amounts that v3 kept in Kotlin `Int`s (Economy's money and cost) are Python integers: exact,
  never wrapped, never floats; the store's JSON keeps them exact.
- A change that must not lose a concurrent one is a single `Store.update(namespace, key, fn)`: `fn`
  runs in one transaction on the store's thread, reads the document and returns a new one, and
  passes what the caller needs back through a list it appends to (Economy's `store.change`).
  `store.lock(...)` around `get` and `put` serializes only the plugin's own coroutines
  (WelcomeGoodbye).
- A guild's data stays when the bot leaves the guild if v3 kept it (Economy's wallets, which may
  hold real value); only plugins whose v3 deleted it on leave delete it (WelcomeGoodbye).
- A list that v3 required to be non-empty and shipped with real IDs (Economy's `admin_id`) has no
  default and ships empty, so the plugin waits for the operator and the error names the key.
- v3 keys of a dropped feature (Economy's Google Sheets keys) are not fields: v3's files load and
  warn about them, as about `enabled`.
- v3's global placeholders, for templates that v3 rendered without a substitutor, are
  `global_values(interaction.client)` (moved into the core from BotInfo and CustomCommands by
  Economy). CustomCommands' operator templates get `placeholder_values(interaction)` since
  `custom-commands-from-config`: the bot's keys and the user's and the channel's.
- A v3 `component_prefix` whose IDs carried no fields (Economy's `economy@`) gets
  `ComponentIds("<package>", ("action",), legacy_prefix=...)` and a handler that ignores the
  fields; the core's decoder reads `economy@` alone or with v3's `<letter>:<value>` segments.
- Commands that differ in their handler take a `kind` in the `COMMANDS` table, and `command(name)`
  builds each with the matching bound method (Economy's `balance`, `board` and `change`).
- A template whose first embed's description is the template of rows (Economy's boards) is
  checked in `setup` for every locale, so a broken one fails at load with the file named
  (`check_boards`).
- A command with subcommands is an `app_commands.Group` built in the plugin's `cog.py` with
  `default_permissions` set on it, and one `app_commands.Command` per subcommand whose callback is
  the cog's bound method, localized from `<root>.subcommands.<name>.*` with one `rename` and one
  `describe` call each (DynamicVoiceChannel's `command`).
- Channels that a plugin creates and must clean up are tracked in the store per guild, once nothing
  is lost by deleting them (DynamicVoiceChannel tracks a room once the lobby's copy exists), and
  checked when the bot is ready and when the plugin loads into a ready bot: empty ones are deleted
  and missing ones forgotten, in available guilds only. A refused deletion keeps the record, so a
  later event tries again.
- A sequence of Discord requests that a later event must not interleave with (a room's creation
  and its deletion) runs under a per-guild lock from `store.lock`, which survives reloads; the
  cache state that decides it (a voice channel's members) is read before the first await.
- A plugin with a second kind of per-guild data keeps it in its own namespace, `<Name>.<kind>`
  (DynamicVoiceChannel's `DynamicVoiceChannel.rooms`), so that the plugin's namespace keeps v3's
  documents only.
- A gateway event that discord.py does not parse is relayed with `bot.relay_gateway_event(<name>)`
  in `setup` (a core method since port-voice-logger) and handled by a cog listener
  `on_gateway_<name in lower case>(payload)` that validates Discord's payload (VoiceLogger's
  `parse_update`). The relay lasts as long as the bot; a reload only adds the listener again.
- Messages to channels that a command set up (VoiceLogger's listen channels) go through
  `bot.get_partial_messageable(id, guild_id=...)`, which needs no cache and reaches archived
  threads; a `discord.NotFound` forgets the channel's settings, another refusal is a warning, and
  the other channels still get the message.
- Settings that v3 kept per channel inside a guild's file (`{"<channelId>": {...}}`) stay one
  document per guild, changed one channel at a time under the guild's lock; a change that changes
  nothing writes nothing (`xincord.plugins.listen_channels.store`, shared by VoiceLogger and
  ChatLogger).
- Audit log entries of types that discord.py does not know are read raw and matched by type,
  channel and time, never taken as "the guild's newest entry" (VoiceLogger's `status.match`).
- Code that two plugins share lives in a package under `xincord.plugins` without an entry point
  (VoiceLogger's and ChatLogger's `xincord.plugins.listen_channels`): neither plugin needs the
  other, and discord.py, which drops a plugin's own modules when it unloads it, leaves the package
  imported, so it holds no state. What differs is passed in (`ListenSettings(store, namespace)`,
  `Menu(lang, templates, ids, key, template)`); each plugin builds its command group in its own
  module, so that unloading the plugin removes it.
- Data that grows with the guilds' traffic and is kept for years (ChatLogger's messages, five years
  by default) lives in the plugin's own SQLite files under `context.data_directory`
  (`data/<Name>/`, in the `data` volume; the core never creates it), on a thread of the plugin's
  own with one connection per file, opened in `cog_load` and closed in `cog_unload` after the work
  under way (ChatLogger's `MessageFiles`). Files hold ranges of snowflakes and are named after the
  UTC second where each starts (`files.py`): every operation goes to the one file holding its ID;
  a new file starts after the newest stored ID once the newest file's page count reaches the size
  limit, so no row moves; the retention deletes the files whose range ended before it and the
  other files' older rows in batches, at READY and every hour (decisions B8 and the owner's
  2026-10-10 answer, `chat-logger-split-storage`). Small plugin tables that need queries can still
  live in the core store (`<Plugin>_<table>` through `Store.run`).
- Tests of message events feed discord.py's own parsers: `tests/support/payloads.py` builds the
  payloads, `plugin_fakes.add_guild` caches a guild, and `plugin_fakes.gateway` runs the listeners
  that the parsers dispatched (ChatLogger's `scene` fixture).
- Texts that v3 wrote in its code go to a `text.yaml` per locale (no CJK in Python), with
  `%ga@...%` placeholders rendered in one pass; a message's texts and its template come from one
  locale: the plugin's files for the user's locale, else zh-TW for a Chinese locale and en-US for
  another (Giveaway's `texts.language`).
- State that a builder keeps between interactions (Giveaway's drafts) lives on the cog, keyed by
  user and guild, with the ID of the message that shows it; every change answers through the
  interaction that made it (`response.edit_message`), never through an older interaction's token.
  A confirmation takes the state before its first await, so a second press finds none.
- Data that must not lose a concurrent change and may also change nothing (joins, draws) runs a
  pure transition under the guild's `store.lock`, reading, then writing only a changed document
  (Giveaway's `Giveaways.change`); the automatic draw takes the same lock, so a draw happens once.
- Values drawn at random come from `random.SystemRandom()` kept on the cog, which tests replace
  with a seeded `random.Random`; the pure draw takes the generator as an argument.
- Work that an event starts and that waits (TicketAwayNotice's notice, v3's `queueAfter`) is an
  `asyncio` task that the listener creates after the checks that need no await, kept in a set on
  the cog (`add_done_callback(set.discard)`) and cancelled and awaited in `cog_unload`; it waits on
  the cog's `sleep`, which tests replace, checks the cache again when the wait ends (the channel,
  the guild, the member's status), and logs any failure that it does not handle with
  `logger.exception`, because nothing awaits it. The listener returns at once, so the wait holds no
  other event up.
- A plugin that reads members' statuses declares `discord.Intents(members=True, presences=True)`:
  both are privileged, and the smoke checklist says to allow them in the developer portal
  (TicketAwayNotice).

## Pitfalls

- **Annotations at import time.** discord.py evaluates app-command parameter annotations when the
  decorator runs (PEP 649/749 make annotations lazy, but discord.py resolves them eagerly). Keep
  those imports at runtime; see `runtime-evaluated-decorators` in `pyproject.toml`.
- **Deprecation warnings.** pytest turns warnings into errors. discord.py 2.7.1 checks cog
  listeners (`Bot.add_listener`) and hooks with the deprecated `asyncio.iscoroutinefunction`;
  `pyproject.toml` ignores that warning from discord.py modules only.
- **Member removal.** `on_member_remove` fires only for cached members; use
  `on_raw_member_remove`.
- **Member joins.** `on_member_join` builds the member from the event, so it needs no member
  cache, but discord.py drops a join for a guild it has not cached or a member it already caches.
- **Roles.** JDA's `modifyMemberRoles(member, roles)` replaced every role; discord.py's
  `member.add_roles(role)` (atomic by default) sends one add-role request per role and keeps the
  others, while `atomic=False` sends one request computed from the cache. discord.py sends without
  JDA's client-side checks; `Role.is_assignable()` makes them (not `@everyone`, not managed, below
  the bot's highest role unless the bot owns the guild).
- **The members intent** is privileged: the bot's application must allow it in the developer
  portal, or the connection fails. With it, discord.py also downloads every guild's members before
  `on_ready` (`chunk_guilds_at_startup` follows the intent); v3 did not.
- **Unavailable guilds.** During an outage discord.py keeps a guild without roles or members, so
  `guild.me` is None there; check `guild.unavailable` before using guild data.
- **Member counts.** `Guild.member_count` stays current only with the members intent: discord.py
  updates it from member join and leave events. It is None for a guild unavailable since the bot
  connected. JDA's guild list left unavailable guilds out; `Client.guilds` keeps them.
- **Global command contexts.** discord.py sends `contexts` and `integration_types` only when a
  command sets them, and Discord's defaults then apply; JDA always sent guild and bot DM contexts
  and guild installs. Set them on ported global commands.
- **Events in tests.** `bot.dispatch` schedules listeners on the loop of a bot that logged in (a
  sentinel before that); tests await the listeners with `plugin_fakes.dispatch`.
- **Channel overwrites.** `create_text_channel(overwrites=...)` does not inherit the category's
  overwrites the way JDA does; merge them explicitly: copy `category.overwrites` when the bot may
  set them (Administrator, or every permission they allow or deny held in the category, JDA's
  `trySync`), drop `Object(type=Role)` keys, then set the channel's own (Ticket).
- **UptimeHeartbeat.** `tasks.loop` schedules from each start, not after each completion as Kotlin
  did. discord.py has no REST ping; time `GET /users/@me` to keep `%ping%`.
- **`wait_until_ready` before a login.** discord.py creates the READY event in `login` or
  `async with bot`, and `wait_until_ready` raises before that, as in tests, which never log in:
  `plugin_fakes.Ready` stands for READY there. `--no-online` enters `async with bot`, so a loop
  waits for a READY that never comes until `close` unloads the plugin and cancels it.
- **Cancellation.** `asyncio.CancelledError` is a `BaseException`: `except Exception` does not
  catch it, so a cancelled loop ends quietly. Kotlin's `catch (e: Exception)` caught
  `CancellationException` and logged a spurious failure (UptimeHeartbeat).
- **aiohttp error texts.** aiohttp 3.14's `ConnectionTimeoutError` reads `Connection timeout to
  host <the whole URL>`, a malformed answer's `ClientResponseError` ends with `url='<the whole
  URL>'` and quotes the server's bad line (a server that sends the request line back shows the
  path and the query), `ServerDisconnectedError` carries the partial answer, and
  `InvalidUrlClientError`'s text is the URL. When the URL carries a secret, cut the URLs out of an
  error's text and remove the URL's parts wherever they appear before logging it, and format the
  traceback yourself: `logger.exception` prints the text as it is (UptimeHeartbeat's `redact`).
- **pydantic input in errors.** A `ValidationError`'s text shows each invalid input
  (`input_value=...`, up to about 50 characters), and the core chains it to its `ConfigError`,
  whose traceback it logs. A model whose values hold secrets sets
  `ConfigDict(hide_input_in_errors=True)` and gives its validators fixed messages: `urlsplit`'s
  errors quote parts of the URL (UptimeHeartbeat's `Config`).
- **aiohttp test servers.** `RawTestServer.close()` waits for the requests still in flight, so a
  request a test leaves unanswered holds the teardown until the client's timeout;
  `http_fakes.Monitor` answers its silent requests when it closes. Autouse fixtures are torn down
  last, after the fixtures a test requests.
- **Logging in `except`.** ruff's TRY400 wants `logger.exception` instead of `logger.error` in an
  `except` block (add `# noqa: TRY400` where a traceback is noise, such as a network error), and
  TRY401 refuses the exception object in a `logger.exception` call: the traceback shows it.
- **Exact decimals.** `decimal` defaults to 28 digits, and `Fraction` reduces with a gcd that costs
  75 to 180 ms per operation at 100,000 digits. Calculator models Java's `BigDecimal` as an
  unscaled integer and a scale, which costs a few milliseconds there.
- **Big integers.** Python refuses `str()` and `int()` conversions of more than 4,300 digits
  (`ValueError`); bound the size before converting. Bound a power before computing it: Python
  computes `10**999999999` if asked.
- **Kotlin character classes.** `Char.isWhitespace()` is `str.isspace()` without U+0085;
  `Char.isDigit()` is `str.isdecimal()`; Kotlin strings are UTF-16, so v3 saw a character outside
  the BMP as two surrogates.
- **`str.splitlines()`** also splits at U+0085, U+2028 and other separators; split JSONL and other
  line-based data with `split("\n")`.
- **ruff S105** reports a variable or constant named like `token` that is compared with or assigned
  a string ("possible hardcoded password"); name it after what it holds instead.
- **CRLF in v3 files.** Some v3 resources have CRLF line endings (BasicCalculator's zh-TW
  `register.yaml`). Git stores them as LF, but the copied working file keeps CRLF; convert copied
  files to LF.
- **Lookup keys.** Kotlin's `StringLocalizer` uses camelCase property paths; Python uses the YAML
  keys directly.
- **CJK in tests.** Build samples with `chr(0x4E2D)` or YAML fixtures. Agent tools may decode a
  typed `\u` escape into the real character, which the CJK hook then rejects.
- **prek pygrep** compiles patterns as bytes, so a `\u` escape in a pattern fails; match UTF-8 byte
  ranges instead.
- **Plugin modules run twice.** Discovery imports a plugin to read its constants, and
  `load_extension` executes it again; keep import time free of work.
- **Setup runs before connecting.** A plugin's `setup` runs in `setup_hook`, before the gateway
  connects, so the guild cache is empty; with `--no-online` there is no login and `bot.user` is
  None too. Work that needs guilds waits for `bot.wait_until_ready()` in a task or listens for
  `on_ready`; background loops stop in `cog_unload`, because the offline check loads and
  unloads plugins without ever becoming ready.
- **Reload re-runs setup.** `reload_extension` executes the plugin module again and calls the new
  `setup`; release what the old version holds (tasks, listeners outside a cog) in `teardown` or
  `cog_unload`. A failed reload restores the old module and runs its `setup` again, which reads the
  plugin's files again: the file that broke the new version broke the old one too, and discord.py
  then left the plugin unregistered. The core hands that setup a context that replays the config,
  lang and templates it loaded (`PluginContext.replaying`, and `Templates.load` parses a `Lang`'s
  templates once; discord.py 2.7.1 runs that setup while the plugin's modules are out of
  `sys.modules`). When it still fails (a file the plugin reads itself), the core unloads the
  plugin, its modules and the plugins that depend on it, uploads the commands without theirs, and
  a full reload loads them again (`custom-commands-from-config`).
- **Command callbacks.** discord.py evaluates a callback's annotations when the command is built,
  so `import discord` must stay at runtime; ruff does not flag a move into `TYPE_CHECKING` while
  other `discord` imports remain, but the plugin then fails to load and its tests fail. Pass the
  cog's bound method: discord.py unwraps it and makes the cog the binding.
- **Real plugins in tests.** Unloading or reloading a real plugin makes discord.py re-import its
  modules, so classes imported by test modules no longer match; test reloads with fake plugins.
  A `setup` that raises (an invalid config, for example) also drops the plugin's modules from
  `sys.modules`: tests that load a plugin with a bad file look its cog up with `cast`, not an
  `isinstance` check against a class imported at collection (AutoRole's `test_config.py`). The
  tests that run after them load the new modules too, so the plugin's `cog` fixture also uses
  `cast` (BotInfo's `conftest.py`).
- **Reloading a real plugin in a test** works with an autouse fixture that puts the plugin's
  `sys.modules` entries back after each test (`plugin_modules`); look the new cog up by name
  (CustomCommands' `test_reload.py`).
- **Command names.** discord.py's `app_commands.Command` refuses an apostrophe, which Discord takes
  in names and localizations, and its pattern ends in `$`, which lets a final line break through
  that Discord refuses with the guild's whole upload: check a configured name with discord.py's
  `validate_name` (`discord.app_commands.commands`) and the core's `is_command_name` (Discord's
  rules: letters, numbers, `-`, `_`, `'` and the Devanagari and Thai scripts), a localized one with
  `is_command_name`.
- **Rendering at load.** A template that the plugin can never post (a `uid` without an ID builder,
  a `model_key` without models, a missing `file_path`, six rows) fails `render_message` with
  `TemplateError` or discord.py's `ValueError`; render it once in `setup` with no values and close
  its files (CustomCommands' `checks._render_problem`).
- **One command table.** The core keeps every plugin's commands, guild-limited ones included, in
  discord.py's global table: discord.py refuses the 101st (`CommandLimitReached`) and a name that
  another plugin registered first (`CommandAlreadyRegistered`), and the plugin that loads second
  fails, in the order of the core config's `plugins` list.
- **Public replies after a deferral.** A deferred response keeps the flags of the deferral: after
  the command tree's ephemeral defer, no reply can be public. A public reply opts out
  (`extras={"defer": False}`) and defers itself with `response.defer(thinking=True)`.
- **Stopped views.** A discord.py view created outside a running event loop never reports
  `is_finished()`; tests that check rendered views must be `async`.
- **Sent files are closed.** discord.py closes a message's `File` objects once `send` or an edit
  used them, even when Discord refused the request; a fallback that sends the message elsewhere
  renders it again. A test that receives `File` objects closes them: an unclosed file fails the
  run (`PytestUnraisableExceptionWarning`).
- **`send` overloads.** `Messageable.send` takes a `View` with content and embeds, or a
  `LayoutView` without them, never `View | LayoutView | None`; an `isinstance` check against a
  Protocol keeps a channel union's own overloads. Pass the channel as `object` before the check
  (CustomCommands' `_postable`).
- **Global `core.hooksPath`.** prek refuses to install while a global `core.hooksPath` is set; use
  `git config --local core.hooksPath .git/hooks`.
- **Channel option types.** A `discord.TextChannel` annotation offers text and announcement
  channels (`channel_types` [0, 5]) and needs the channel in discord.py's cache; JDA's
  `setChannelTypes(ChannelType.TEXT)` needs a `Transformer` with `channel_types` [text] over the
  resolved `AppCommandChannel`. discord.py keeps announcement channels in `TextChannel` too: check
  `channel.type`, not the class.
- **Thread categories.** `Thread.category` raises `ClientException` when the parent channel is not
  cached, and `getattr(thread, "category", None)` does not catch it (the core's
  `interaction_values` does since port-welcome-bye-guild).
- **Interaction guilds.** In a guild, `interaction.guild` is never None: discord.py creates a
  placeholder for a guild it has not cached, without channels. The guild's preferred locale is
  `interaction.guild_locale`, straight from the payload.
- **Member removals.** `on_raw_member_remove` fires for every removal with the cached `Member` or
  else the `User`; JDA ignored the bot's own removal, so skip `bot.user`. `on_guild_remove` fires
  when the bot leaves or is removed, `on_guild_unavailable` during an outage.
- **Guilds at ready.** At `on_ready`, `Client.guilds` holds every guild of the session's READY,
  unavailable ones included, so data of guilds missing there belongs to guilds the bot left.
- **Fakes hide discord.py.** Drive a new plugin once through discord.py's own objects in a scratch
  script: `discord.Interaction(data=payload, state=bot._connection)` after setting
  `state.user`, `command._invoke_with_namespace(...)`, and gateway payloads through
  `state.parse_*` with `bot.loop` set. This found the thread category failure above.
- **Member options.** A `discord.Member` annotation makes discord.py raise a `TransformerError`
  before the callback when Discord resolved no member (a user outside the guild), and the deferred
  response stays "thinking"; annotate `discord.Member | discord.User` and check the member in the
  callback.
- **Modal submissions.** discord.py parses a submission only for a `Modal` it dispatches; the core
  stops its modals, so plugins read `interaction.data` with `modal_values`. `defer()` on a
  submission sends a deferred message update (type 6), after which `followup.send(...,
  ephemeral=True)` can still tell the user something.
- **Empty embed fields.** Discord refuses an embed field whose name or value is empty; JDA sent
  U+200E instead and trimmed both with Java's `trim`, and the core's renderer now does the same
  (an empty optional modal input is the common case).
- **Views from messages.** `View.from_message` refuses a Components V2 message (`ValueError`); use
  `LayoutView.from_message` when the message has the `components_v2` flag, as the core's upgrade
  does.
- **Deleted messages and legacy IDs.** After a handler that deletes the message of a v3 ID (a v3
  modal opened before the switch), the core's upgrade cannot fetch it and logs an error.
- **Option texts on a built command.** `app_commands.describe(...)` applied to a built `Command`
  gives every option it does not name an ellipsis as its description: call it once with all the
  options (Economy's `command`). `rename(...)` leaves the options it does not name alone.
- **Voice state updates.** `on_voice_state_update` fires for mutes, deafens and streams too; JDA's
  `GuildVoiceUpdateEvent` fired for channel changes only. Compare `before.channel` and
  `after.channel` by ID.
- **Listeners run after the cache moved on.** discord.py runs each listener as a task, and the
  gateway events parsed before that task runs, or while it awaits, are already in the cache it
  reads: a listener can see a member who already left (DynamicVoiceChannel's probe parsed a join
  and a leave before the listeners ran). Read what decides the handling at the start of the
  listener, before the first await, and check again under a lock before acting; JDA ran each
  listener with the cache as of its event.
- **Channel positions.** `GuildChannel.edit(position=...)` renumbers every channel of the guild in
  the channel's sorting bucket (all voice and stage channels, say), and `move(...)` those of its
  category, in one `PATCH /guilds/{id}/channels` computed from the cached positions; JDA's
  `ChannelManager.setPosition` sent the channel's raw position in `PATCH /channels/{id}`, which a
  `Route` request keeps (DynamicVoiceChannel).
- **Clones.** `VocalGuildChannel.clone()` copies the overwrites as they are, and also the NSFW
  flag, the video quality and the slowmode, which JDA's `createCopy` left at Discord's defaults.
  `Guild.create_*_channel(overwrites=...)` sends an `Object(type=Role)` key (an uncached role) as a
  member overwrite: its `_create_channel` checks `isinstance(target, Role)` only, unlike `edit`.
- **No-op updates.** `Store.update` writes the function's result even when it is the value it read,
  and stores `null` for a missing key when the function returns None. Changes that may find nothing
  to change use `store.lock` with `get`, `put` and `delete` (DynamicVoiceChannel's `unbind` and
  `untrack`).
- **Unparsed gateway events.** discord.py 2.7.1 drops `VOICE_CHANNEL_STATUS_UPDATE` (its gateway
  logs "Unknown event" at debug level) and has no `VoiceChannel.status`. Its `AuditLogAction` lacks
  the types 192 and 193: `AuditLogEntry` names them `unknown_192`, gives no `target` and drops their
  `options`, where the channel and the status are. Discord documents (2026-04-20) that statuses are
  not part of channel objects; its Request Channel Info (gateway opcode 43) reads them.
- **The voice state after.** `on_voice_state_update` gets discord.py's cached voice state as `after`,
  which later events update in place, and a copy as `before`: a join and a leave that discord.py
  parses before the listener runs reach it as no change, and a switch and a leave as a leave from
  the first channel.
- **Replacing a component's message.** `interaction.response.edit_message(...)` keeps what it is
  not given; JDA's `MessageEditData.fromCreateData` replaced everything, so pass `embeds=()` and
  `view=None` to clear them.
- **Lengths in UTF-16.** JDA counted Discord's text limits with Java's `String.length`, in UTF-16
  code units, where a character outside the BMP counts twice; Python's `len` counts it once. Count
  `len(text.encode("utf-16-le")) // 2` to stay within the limits (VoiceLogger's lists,
  DynamicVoiceChannel's names).
- **Members in payloads.** discord.py makes a message's author a `Member` only when the payload's
  `member` holds every field that `Member` reads (`flags` too); `Message.__init__` swallows the
  `KeyError` and keeps a `User`. `payloads.member` and `payloads.message` carry them.
- **Parsers dispatch through the state.** discord.py's own parsers call the connection state's
  `dispatch`, bound when the client was created, not `bot.dispatch`; `plugin_fakes.gateway`
  records both.
- **Uncached guilds, channels and parents.** A message from a guild that discord.py has not cached
  has no `guild`, and one from an uncached channel a `PartialMessageable`; `Thread.category_id`
  raises without the cached parent channel, so read `thread.parent`. `guild.channels` leaves
  threads out; `guild.threads` holds the active ones (ChatLogger's `Place.of`), and archived
  threads are not cached at all: ask Discord (`bot.http.get_channel`) before taking an uncached ID
  for a deleted channel (the shared READY check).
- **Members' embeds.** Members cannot send embeds: the embeds of a member's message are link
  previews, and some sites' previews are typed `rich` (ChatLogger takes a member's text from the
  content only).
- **Embed types.** `Embed.from_dict` leaves `type` None when the payload has none; Discord's
  default is `rich`.
- **The cached message changes in place.** discord.py parses the gateway frames that arrived
  together without yielding, then runs the listeners as tasks: `on_message` gets the cached
  `Message`, which a `MESSAGE_UPDATE` parsed meanwhile has already changed, and a listener's awaits
  let later events' listeners overtake it. Read a new message from the relayed `MESSAGE_CREATE`
  payload, and let a message's later events wait for its handling (ChatLogger's `inserting`);
  `plugin_fakes.burst` reproduces such frames in tests.
- **Privileged message content.** A plugin that declares `message_content` makes the core request
  it, and Discord closes the gateway (4014) unless the developer portal allows it: the bot does not
  connect at all. Without the intent, messages arrive without their text.
- **Fixtures by parameter.** `pytest.mark.parametrize` with a fixture's name overrides that fixture
  for the test, also where other fixtures request it (ChatLogger's `config`).
- **Batched deletions.** SQLite's `DELETE` takes no `LIMIT` unless it was compiled with it: delete a
  batch through a subquery of IDs (ChatLogger's `PRUNE`).
- **Unclosed SQLite connections.** Since Python 3.13, `sqlite3` warns (`ResourceWarning`) when a
  connection is collected without `close()`, and pytest's `filterwarnings = error` turns the
  warning into a failure of whichever test runs when the collector does: close every connection,
  and unload in each test what it loaded (ChatLogger's `load` fixture removes the cog, whose
  `cog_unload` closes the files).
- **Renaming SQLite files.** SQLite names a file's journal after the path its connection opened:
  never rename an open database. Build a new file under a temporary name, close it, rename it, then
  open it (ChatLogger's `create_file`).
- **SQLite file size.** `PRAGMA page_count` times `PRAGMA page_size` is the file's size, answered
  without a scan; deleted rows leave free pages (`PRAGMA freelist_count`) that later rows of that
  file reuse, and the file never shrinks without `VACUUM`. With `autocommit=False`, Python opens a
  new (deferred, lock-free) transaction right after each commit: read such pragmas inside the
  work's transaction, before its commit.
- **Failed commits.** A commit that cannot get its lock (another connection reading past the busy
  timeout, 5 seconds by default) raises and leaves the write transaction open, and the next
  commit on that connection applies it: commit inside the `try` that rolls back (`Store.run`,
  ChatLogger's `transaction`, since `chat-logger-split-storage`).
- **Cancelled executor jobs.** Cancelling the await of `loop.run_in_executor(...)` cancels the job
  if it has not started: a job that must run, such as closing connections, is submitted with
  `executor.submit` and awaited through `asyncio.shield(asyncio.wrap_future(...))`
  (`MessageFiles.close`), and a cancelled `open` queues the closing job after its own.
- **Leaks in tests.** A cancelled task keeps its exception, whose traceback keeps the frames and
  their locals alive, and a `ResourceWarning` that the collector raises later surfaces as an
  unraisable warning after the test's call (xfail does not see it) or in another test: drop such
  references and assert `plugin_fakes.unclosed() == []`, or record the connections and check each
  (`total_changes` raises `ProgrammingError` on a closed connection, from any thread).

- **Re-imported plugin modules in tests.** A failed load (an invalid config) makes discord.py drop
  the plugin's modules; later loads import new classes, and frozen dataclasses from the old and the
  new module never compare equal (`Prize(...) != Prize(...)`). An autouse fixture that puts the
  plugin's `sys.modules` entries back after each test keeps one set of classes (Giveaway's
  `plugin_modules`).
- **Modal submissions update their message.** discord.py's `response.edit_message` answers a
  modal submission with type 7 when the modal came from a message's button: the builder message
  changes without a hook.
- **`strftime("%Y")`** does not pad years below 1000 everywhere; format the year with `:04d`. A
  naive `datetime(1, 1, 1).timestamp()` (local time) raises `ValueError`.
- **Embed totals.** Discord refuses an embed whose title, description, field names and values,
  footer and author exceed 6000 characters; count UTF-16 code units and shorten the longest part
  (Giveaway's `_fit` shortens the post's description).
- **ruff's argument count** (PLR0913) includes keyword-only arguments: bundle values that travel
  together in a frozen dataclass (Giveaway's `Drawer`, the tests' `Who`).
- **Test modules cannot import `conftest`** at runtime (importlib mode): build its dataclasses
  through a fixture's method (Giveaway's `scene.who(...)`).
- **Gated xfail tests** that wait for a fake to start sending: `asyncio.wait({event_task, task},
  return_when=FIRST_COMPLETED)` and `result()` on what finished, so a stub's `NotImplementedError`
  surfaces at once instead of a timeout.

- **Threads without a message.** `TextChannel.create_thread(name=...)` without `message` creates a
  private thread unless `type=discord.ChannelType.public_thread` is given; JDA's
  `createThreadChannel(name)` made a public one (Ticket's archive).
- **Refused interaction responses.** `InteractionResponse.edit_message` marks the response done
  only after Discord took it: when it raises `HTTPException`, the interaction is still open and
  `response.send_message(..., ephemeral=True)` can explain (Ticket's refused drafts).
- **Views rebuilt from a message.** `View.from_message` gives each item its row; `add_item` appends
  to `children`, and `to_components` sorts by row when sending: check the payload, not `children`,
  for the order (Ticket's added button).
- **Hashable fakes.** A `@dataclass` with the default `eq=True` is unhashable; a fake that is a key
  of a permission overwrite map needs its own `__hash__` (`discord_fakes.FakeMember`).
- **Webhook names.** Discord refuses a webhook message's username with `@`, `#`, `:`, three
  backticks, `discord` or `clyde`, or one that is `everyone` or `here`, or over 80 characters; JDA's
  archive then failed. Fall back to the username, then the ID (Ticket's `forwarded_name`).
- **Objects as overwrite keys.** `discord.Object(id, type=discord.User)` compares and hashes equal
  to the member with that ID, so setting the member's overwrite replaces a copied one instead of
  adding a second (Ticket's `overwrites`).
- **Attachments in probes.** `Attachment.to_file()` downloads through `HTTPClient.get_from_cdn`,
  not `request`: a probe that records HTTP patches both. A recorded webhook answer needs whole
  attachment objects (`size` included), or discord.py raises `KeyError`.
- **Edits clear suppressed embeds.** `Message.edit()` sends the message's flags with
  `suppress_embeds` set to its `suppress` argument, False by default: an edit (the core's upgrade
  of v3 IDs) shows embeds that were suppressed.
- **Undoing a placed component.** When a button goes onto a message before its record is stored
  and the store then fails, put the earlier view back: `Message.edit` leaves the fetched message
  as it was, so `View.from_message` on it rebuilds the earlier view; a button left without its
  record would make the next one take the same custom ID, which Discord refuses (Ticket's
  `/add-ticket`, found in its review).
- **Echoed options.** A string option takes up to 6000 characters, and a reply at most 2000: cut
  what a reply repeats of it (Ticket's invalid message ID shows 100 characters).
- **Files in memory.** `Attachment.to_file()` reads the whole file into memory before the upload;
  JDA streamed it (Ticket's archive keeps one message's files at a time).
- **Webhook URLs in errors.** A webhook's URL holds its token, and aiohttp's connect timeout names
  the whole URL: cut URLs in error texts to their origin before showing or logging them
  (`xincord.plugins.redaction.redact`, shared since port-ticket).

- **Presences.** The presences intent is privileged: without the developer portal's permission,
  Discord closes the gateway (4014) and the bot does not connect. With it, discord.py takes a small
  guild's members and their statuses from `GUILD_CREATE` instead of chunking it, and chunks large
  guilds without presences (their online members' statuses come with `GUILD_CREATE`);
  `PRESENCE_UPDATE` updates cached members only, so the members intent is needed too. A member from
  `fetch_member` (REST) has no presence: `member.status` is `Status.offline`, as JDA's default.
- **New threads.** discord.py dispatches `on_thread_create` only for a `THREAD_CREATE` marked
  `newly_created`, and `on_thread_join` when the bot gets a thread that it did not cache (it is
  added to a private thread, or a thread is unarchived).
- **Tasks that nothing awaits.** An exception left in a task that nothing awaits surfaces only as
  asyncio's "Task exception was never retrieved" when the task is collected: log it inside the task
  (TicketAwayNotice's `_notice`). `asyncio.CancelledError` is no `Exception`, so a cancelled task
  stays quiet.
- **Mentions in embed titles.** Discord shows a channel or user mention in an embed's title,
  author or footer as raw `<#...>` text; it renders mentions in the description and in field
  values (TicketAwayNotice's bundled notice moved v3's text into the description).

v3 behaviors never to reproduce: loading plugins in reverse dependency order, non-atomic JSON
writes that silently reset corrupt files, recursive placeholder expansion, shared mutable
placeholder caches, `asTextChannel()` failures in threads, voice chat and announcement channels,
allow-all mentions, naming the member of an event after the guild's newest audit log entry,
keeping message content forever, rendering a builder through an expired interaction token,
drawing a giveaway twice, pinging what a user typed into a ticket, losing an error thrown in a
callback (Ticket's archive hung), a guild filter that never applied, and a delayed message that
nothing could cancel or check again (TicketAddons).

## Differences from v3

Every deliberate difference, added by the change that introduces it.

| Area | v3 behavior | xincord behavior | Change |
|---|---|---|---|
| Config files | unknown keys fail the whole load (KAML strict mode) | unknown keys are logged as warnings | core-config |
| Core config | `general_settings` / `builtin_settings` with `TYPE;text;ms` strings | `token`, `status.activities`, `interaction_log`; migrate with `python -m xincord.core.migrate_v3 <dir>` | core-config |
| Status rotation | a `STREAMING` entry used its third field as both URL and delay, so nothing waited | separate `url` and `seconds` fields | core-config |
| Status rotation | malformed entries were skipped at runtime on every cycle | rejected when the config loads | core-config |
| Interaction log | unknown `log_type` values were ignored | validation error | core-config |
| Default core config | shipped a real guild and channel ID | ships no interaction log targets | core-config |
| Storage | a JSON file that failed to parse was replaced by the default and saved | a corrupt database stops startup and is left untouched | core-storage |
| Storage | JSON files written in place; save errors only logged | SQLite transactions; a failed write raises | core-storage |
| Lang files | a `register.yaml` that failed to decode was logged and its locale dropped | the plugin fails to load with the file and key named | core-i18n |
| Lang files | an invalid localized command name surfaced as a failed registration | rejected when the lang files load | core-i18n |
| Lang keys | Kotlin camelCase property paths (`basicCalculate.name`) | YAML paths (`basic-calculate.name`) | core-i18n |
| Placeholders | substituted values were expanded again (user text could inject placeholders; a self-reference dropped the message) | values are inserted verbatim in one pass | core-placeholders |
| Placeholders | per-user substitutors cached in shared maps, keeping every custom key ever set | each render builds its own values | core-placeholders |
| Placeholders | `guild_owner_id` / `guild_owner_mention` were `0` / `-` unless the owner member was cached | taken from `Guild.owner_id` | core-placeholders |
| Placeholders | commons-text read `%key:-fallback%` as the key's value, else `fallback` | left as written; no shipped template uses it (recorded in port-welcome-bye-guild) | core-placeholders |
| Placeholders | avatar and icon URLs were JDA's, without a query | discord.py's, ending with `?size=1024` (recorded in port-welcome-bye-guild) | core-placeholders |
| Templates | a locale directory missing one template raised at render time | per-file fallback to the default locale | core-templates |
| Templates | render-time values were added to the shared global substitutor for good | values apply to one render only | core-templates |
| Templates | bad styles, missing `uid`s and bad timestamps failed when a message was sent | they fail when the plugin loads | core-templates |
| Components V2 | V2 components were checked when a message was rendered | validated when the plugin loads | core-components-v2 |
| Components V2 | without `is_components_v2`, a top-level `model_key` in `components_v2` could supply a whole action row | only action rows there; models work inside them | core-components-v2 |
| Components V2 | an embed model's timestamp became ISO text in the container footer | Discord `<t:...:f>` markup, shown in the reader's time zone | core-components-v2 |
| Component IDs | values containing `:` or `;` could not be parsed back | values are percent-encoded | core-component-ids |
| Component IDs | values went through the shared placeholder substitutor | values are written verbatim | core-component-ids |
| Component IDs | no version; old IDs had to stay valid forever | versioned; legacy IDs still parse and are rewritten when first used | core-component-ids |
| Plugin loading | plugins loaded in reverse dependency order | dependencies load first | core-plugin-loading |
| Plugin loading | one plugin's broken config or lang file could stop the whole bot | only that plugin and its dependents are skipped | core-plugin-loading |
| Plugin switches | an `enabled` key in each plugin config, checked by every handler; disabled plugins still exported their files | the core config's `plugins` list; disabled plugins are never imported | core-plugin-loading |
| Intents | GUILD_MEMBERS always requested | requested only when an enabled plugin declares it | core-plugin-loading |
| Command upload | guild commands overwritten in every guild at every start | uploaded only when a scope's payload hash changed, or when forced | core-command-tree |
| Component routing | every plugin received every component and modal event and filtered by prefix | only the owning plugin's handler runs; a message is upgraded to new IDs after a legacy one is used | core-component-routing |
| Placeholders | `channel_category_name` came from `asTextChannel()`, which failed for commands in threads, voice-channel chats and announcement channels | taken from any channel's category, for components too | core-interaction-values |
| Placeholders | `component_url` was defined but always absent: link buttons send no interactions | not provided | core-interaction-values |
| Command line | `--no-online` read the core config, then idled with the console open | loads the config and the plugins without connecting, then exits with 0, or 1 if a plugin did not load | core-startup |
| Command line | logback level names; an unknown name silently became DEBUG | Python level names in any case; an unknown name is a usage error | core-startup |
| Command line | `--ignore-update` (`-I`) and `--auto-defer-interactions` / `--no-auto-defer-interactions` | removed: no version check, and commands opt out of the defer with `extras` | core-startup |
| Logging | also written to `log/output.log`, rotated at 1 MB | stderr only | core-startup |
| Startup | the token was compared with a placeholder string | the default token is empty; `--token` overrides the config | core-startup |
| Startup | plugins loaded after JDA was ready, so `setup` could read the guild cache | plugins load before the gateway connects | core-startup |
| Command upload | guild commands were uploaded at startup only when there were any, so the last removed one stayed | an empty payload is uploaded once | core-startup |
| Mentions | every mention type pinged, including `@everyone` and roles | users and the replied-to user only, unless a message opts in | core-startup |
| Reload | the console's `reload` disconnected and rebuilt everything; a plugin that failed stayed off | reloads in place without disconnecting; a plugin whose new version fails keeps its previous one | core-reload |
| Reload | only the console (whole bot) or the Web Dashboard (one plugin) could reload | SIGHUP and the owner's `/xincord reload [plugin]` (the console follows) | core-reload |
| Console | started without a terminal too, and end of input stopped the bot | runs only when stdin and stdout are terminals | core-console |
| Console | `reload` took no plugin and completion covered the command names | `reload <plugin>`, and the loaded plugins complete after `reload` | core-console |
| Interaction log | modal submissions were posted to log channels with `cl_type` `BTN` | `MODAL` | core-status-log |
| Interaction log | log channel messages used JDA's default mentions, so `%user_mention%` pinged | log messages never ping | core-status-log |
| Status rotation | a single activity was set again after every delay | set once | core-status-log |
| Deployment | `java -jar` from `Server/`, files and MongoDB data next to the jar | an arm64 image under docker compose: files in `./bot`, the SQLite database in the `xincord_data` volume | container |
| Example | an `option1` longer than 1024 characters overflowed the embed field, and the command got no reply | Discord refuses more than 1024 characters | port-example |
| Example | no reply in threads, voice channel chats and announcement channels | answers in any channel | port-example |
| Example | `%...%` in the options was expanded, and a self-reference made the reply fail | option text is inserted as typed | port-example |
| Example | the `_Example@` keys stayed in the user's cached placeholders | each render uses its own values | port-example |
| Example | `example_key` was required but never read; a config without it stopped the bot | optional, `example_value` by default, shown in the reply | port-example |
| Example | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-example |
| Example | the reply was the embed alone | a third field shows `example_key`, and a button under the embed counts presses | port-example |
| Calculator | a minus after an operator subtracted from a synthetic `0` (`2*-3` was `-3`, `2^-1` was `0`, `1/-2` divided by zero) | it negates (`-6`, `0.5`, `-0.5`) | port-basic-calculator |
| Calculator | `^` grouped from the left (`2^3^2` was 64) | from the right (512) | port-basic-calculator |
| Calculator | `^` truncated its exponent to 32 bits (`2^0.5` was 1, `2^4294967297` was 2) | whole exponents only: `Exponent must be an integer` or `Too many digits` | port-basic-calculator |
| Calculator | division by zero and negative or huge exponents threw, and "thinking..." stayed | an error embed; negative exponents divide 1 by the power | port-basic-calculator |
| Calculator | no limits: `10^999999999` stalled the gateway thread, and formulas or results over 1018 characters got no reply | `formula` takes at most 1018 characters, numbers over 50,000 digits fail with `Too many digits`, and the calculation runs in a worker thread | port-basic-calculator |
| Calculator | `%...%` in a failing formula was expanded, and `%bc_question%` gave no reply | the formula is shown as typed | port-basic-calculator |
| Calculator | the `bc_` keys stayed in the member's cached placeholders | each render uses its own values | port-basic-calculator |
| Calculator | `%bc_answer_round%` was the whole answer | the part before the decimal point | port-basic-calculator |
| Calculator | "thinking..." stayed when the bot could not post in the channel | the answer replaces the deferred response | port-basic-calculator |
| Calculator | the en-US `formula` description said "bracket is ignorable" | it says that the multiplication sign can be omitted | port-basic-calculator |
| Calculator | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-basic-calculator |
| Calculator | an unknown character outside the BMP was reported as half a surrogate pair | the whole character | port-basic-calculator |
| AutoRole | `modifyMemberRoles` replaced the member's roles with the configured ones, so a role another bot gave at the join could be removed | each configured role is added with its own request; the member keeps every other role | port-auto-role |
| AutoRole | roles were looked up in every guild, and another guild's role made JDA refuse every role | roles are looked up in the joined guild; another guild's role is skipped and logged | port-auto-role |
| AutoRole | one role the bot could not give (managed, `@everyone`, too high) or a missing Manage Roles meant no role at all | such a role is skipped with a warning and the others are given; without Manage Roles one warning names the guild | port-auto-role |
| AutoRole | roles were resolved once, at the first join, so later roles and guilds needed a reload | roles are looked up at each join | port-auto-role |
| AutoRole | unknown role IDs were dropped without a log, and other problems showed only at a join | warnings when the bot is ready, when the plugin loads into a ready bot, and at each join | port-auto-role |
| AutoRole | a reload replaced the guild set and the role map one after the other, so a join in between could fail | a reload replaces the whole cog | port-auto-role |
| AutoRole | the bundled `config.yaml` held real guild and role IDs | it lists no guilds and shows placeholder IDs in a comment | port-auto-role |
| BotInfo | `member_counts` and `guild_counts` were written into the shared global placeholders at each use, so every plugin's later renders saw them | the counts are values of one render | port-bot-info |
| BotInfo | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-bot-info |
| BotInfo | guilds that became unavailable during an outage were left out of both counts | they count as guilds, with the members discord.py knew | port-bot-info |
| BotInfo | no source link; the bundled `config.yaml` held only `enabled: false` | a Source Code field shows `source_url` (decision C3), by default the xincord repository, checked when the plugin loads | port-bot-info |
| CustomCommands | the deferred response was deleted together with the post, so a post the channel refused left the administrator with nothing | the message is posted first; when the channel takes no messages or refuses it, it replaces the deferred response and a warning is logged | port-simple-command |
| CustomCommands | the commands needed the core's auto-defer; with `--no-auto-defer-interactions` the user saw "The application did not respond" | the command tree always defers the commands | port-simple-command |
| CustomCommands | the bundled templates held real bank account numbers | they hold the example `000000000000`; operators' files keep theirs | port-simple-command |
| CustomCommands | messages were rendered with the shared global substitutor, with the keys other plugins had written into it | each render gets its own values: `bot_id` and `bot_name`, and since custom-commands-from-config the user's and the channel's | port-simple-command, custom-commands-from-config |
| CustomCommands | five commands fixed in Kotlin: adding one needed changes to three Kotlin files and a new jar (inventory B3) | the commands come from `config.yaml` (bundled: v3's five), each with its localizations, template, permissions, reply (a channel post, a public or an ephemeral reply) and guilds, checked at load and followed by reloads (the owner's decision) | custom-commands-from-config |
| CustomCommands | the names' localizations lived in `register.yaml` | they live in `config.yaml`; `register.yaml` is no longer bundled or read | custom-commands-from-config |
| WelcomeGoodbye | commands in threads, voice channel chats, stage and announcement channels got no reply (`asTextChannel()` threw), a bind chosen with the option there was saved silently, and `invalid-channel` was never delivered | the commands answer everywhere; without the option there, the reply is `invalid-channel` | port-welcome-bye-guild |
| WelcomeGoodbye | `%...%` in member, guild and channel names was expanded, and a self-reference stopped the welcome or bye message | names are inserted as written | port-welcome-bye-guild |
| WelcomeGoodbye | the bye message used the user's placeholders only, so its `wbg@member_*` and unprefixed member keys stayed as written | they render when discord.py still knew the member | port-welcome-bye-guild |
| WelcomeGoodbye | `invalid-channel`, `*-bind-already` and `*-unbind-empty` created the guild's data file | nothing is written unless a channel changes | port-welcome-bye-guild |
| WelcomeGoodbye | bindings in `plugins/WelcomeByeGuild/data/<guildId>.json`, written in place; a corrupt file was reset, a non-numeric file name stopped the bot | v3's document in the SQLite store under the guild ID; v3's files are not read (migration deferred, B11) | port-welcome-bye-guild |
| WelcomeGoodbye | a guild's file was deleted only on a leave event received while the plugin was enabled | also deleted when the bot is ready, for guilds it left while offline or while the plugin was off | port-welcome-bye-guild |
| WelcomeGoodbye | `guild-only` was rendered with the global placeholders only | with the interaction's, like `no-permission` (guild commands never show it) | port-welcome-bye-guild |
| WelcomeGoodbye | a welcome or bye message that Discord refused surfaced as JDA's exception log | a warning names the guild and the channel | port-welcome-bye-guild |
| WelcomeGoodbye | the commands needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers them | port-welcome-bye-guild |
| WelcomeGoodbye | the zh-TW `welcome` and `bye` texts had typos | corrected in the bundled files | port-welcome-bye-guild |
| UptimeHeartbeat | an `interval` of 0 or less made the loop push without pause | the plugin does not load, and the error names `listeners.<n>.interval` | port-interval-pusher |
| UptimeHeartbeat | the URL was not checked, so a URL without a scheme, with another scheme or with a space failed at every push | the plugin does not load unless each `url` is an http or https URL with a host | port-interval-pusher |
| UptimeHeartbeat | stopping a pusher while it waited for the ping logged a spurious `Query URL ... failed` error | a cancelled loop logs nothing | port-interval-pusher |
| UptimeHeartbeat | the REST ping was requested at every push | only for URLs that contain `%ping%` | port-interval-pusher |
| UptimeHeartbeat | the bundled `config.yaml` held a listener on the owner's status domain | it lists no listeners and shows an example on `status.example.com` in a comment | port-interval-pusher |
| UptimeHeartbeat | a config without `listeners` or with an unknown key stopped the whole bot, even with the plugin disabled | only UptimeHeartbeat is disabled, unknown keys warn, and the file is read only when `plugins` lists it | port-interval-pusher |
| UptimeHeartbeat | log lines did not say which listener (`Status Monitor refused the connection! (Code: 404)!`) | English lines that number the listener and name the URL's origin; a new failure at v3's level | port-interval-pusher, uptime-heartbeat-keep-pushing |
| UptimeHeartbeat | a 404, Uptime Kuma's answer for an unknown or paused push token, stopped the listener until a reload or restart | no failure stops a listener: it keeps pushing at its interval until the plugin unloads (the owner's decision) | uptime-heartbeat-keep-pushing |
| UptimeHeartbeat | failure lines and the debug line showed the URL with its push token | only its origin (scheme, host, port); URLs in error texts and tracebacks are cut the same way | uptime-heartbeat-keep-pushing |
| UptimeHeartbeat | every failed push and every failed ping logged a line, at every interval | each kind of failure (status code, error type) is logged once per episode, the rest at debug level; the episode ends after three successes in a row with one info line | uptime-heartbeat-keep-pushing |
| Feedback | a missing submit channel was reported through the interaction hook before anything acknowledged the submission, so the member saw a failed modal | the submission is acknowledged; the member gets `form_submit_failure` and the form stays | port-feedbacker |
| Feedback | the form was deleted while its review was posted, so a refused review lost the feedback | the form is deleted only after the review is posted; a refused review keeps it and tells the member | port-feedbacker |
| Feedback | a `member` option naming a user outside the guild, or a channel refusing the form, left the administrator's response "thinking" | `form_failure` and a log warning | port-feedbacker |
| Feedback | `SubmitChannel must be TextChannel` and `Submit channel not found` were hard-coded English | `form_failure` and `form_submit_failure` in `config.yaml`: zh-TW in the bundled file, English defaults for v3's files | port-feedbacker |
| Feedback | the star restyle was queued on the interaction hook before the modal acknowledged the press | the bot edits its own message after the modal opened; a refused edit is logged | port-feedbacker |
| Feedback | the feedback was expanded as placeholders, and `%fb_content%` in it made the modal fail | the feedback is shown as typed | port-feedbacker |
| Feedback | a submission without a member wrote its values into the global placeholders | each render has its own values | port-feedbacker |
| Feedback | a star count above 5 or below 0 threw after the member had typed a feedback | the press fails before the modal opens | port-feedbacker |
| Feedback | the command needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers it | port-feedbacker |
| Feedback | a config without one of the three replies, or with an unknown key, stopped the whole bot even with the plugin disabled | only Feedback is disabled, unknown keys warn, and a blank reply or one over 2000 characters is refused at load | port-feedbacker |
| Economy | amounts were 32-bit `Int`s that wrapped silently (`2147483647 + 1` was saved as `-2147483648`), and a `value` beyond 32 bits left the response "thinking" | amounts are exact integers, and any value Discord sends is applied | port-economy |
| Economy | `/balance`, the button and the boards created the wallet and the guild's file when reading, so every member who ran `/balance` appeared on the boards at 0 | reading writes nothing; only changed wallets are ranked | port-economy |
| Economy | a user who is not an administrator and named another member in `/balance` silently got their own wallet | they get `no-permission` | port-economy |
| Economy | board ties had no defined order (Java `HashMap` order and a stable sort) | ties are ordered by user ID | port-economy |
| Economy | a change could lose a concurrent one (the button callback ran beside the gateway thread without a lock) | a change is one store transaction | port-economy |
| Economy | an unreadable file was replaced by `{}` and saved, losing the guild's wallets; files were written in place | an unreadable entry stops the command with an error and is never overwritten; the store writes in transactions | port-economy |
| Economy | each change reply set only the before values of the amounts it changed; the other key kept what an earlier command had left in the user's cached placeholders | every change reply has both before values | port-economy |
| Economy | a board template without a description threw at each use and gave no reply | the plugin does not load, and the error names the file | port-economy |
| Economy | Economy did not load without the GoogleSheetAPI plugin, which only the dead Sheets storage used | no dependency; the Sheets keys only warn | port-economy |
| Economy | an empty `admin_id`, a `port` outside 1 to 65535 or a limit outside 1 to 25 stopped the whole bot, even with the plugin disabled; the bundled `config.yaml` held two real user IDs | only Economy is disabled (the `port` is gone), unknown keys warn, the file is read only when `plugins` lists the plugin, and the bundled file lists no administrator | port-economy |
| Economy | the commands needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers them | port-economy |
| Economy | every load and reload rewrote every guild file, and a file whose name was not a number stopped the load | the store is read only when a command needs it; v3's files are not read (migration deferred, B11) | port-economy |
| Economy | any button ID starting with `economy@` showed the wallet | the core's v3 decoder reads `economy@` alone or with v3's `<letter>:<value>` segments; no v3 template or production message has such a button | port-economy |
| DynamicVoiceChannel | `/dynamic-voice-channel bind` and `unbind` never ran: the command filter compared the top-level name with the subcommands' full names (since `ea14fbf`), and the response stayed "thinking" | both subcommands answer | port-dynamic-voice-channel |
| DynamicVoiceChannel | the `channel` options offered every channel type, and anything but a voice channel threw before an answer | they offer voice channels only | port-dynamic-voice-channel |
| DynamicVoiceChannel | replies used `Placeholder.get(event)`, which threw outside text channels | the replies work in every channel | port-dynamic-voice-channel |
| DynamicVoiceChannel | `bind` appended a duplicate entry, which won until the next restart and lost afterwards | a bind replaces the binding of the same category and name | port-dynamic-voice-channel |
| DynamicVoiceChannel | the lobby was tracked as a room before its copy existed, so a refused copy got the lobby deleted once it emptied, and its binding dropped at the next start | the room is tracked once the copy exists; a refused copy leaves the lobby as it was, with a warning | port-dynamic-voice-channel |
| DynamicVoiceChannel | the tracker was written to MongoDB asynchronously while leaves read MongoDB, so a quick leave left an orphan room | a guild's voice changes are handled one after another, and a leave sees the room that the join created | port-dynamic-voice-channel |
| DynamicVoiceChannel | rooms that emptied while the bot was away were never deleted, and the tracker kept deleted channels forever | at READY and on a load into a ready bot, empty rooms are deleted and missing ones forgotten | port-dynamic-voice-channel |
| DynamicVoiceChannel | a refused step of the creation skipped the following ones; a blank name or one over 100 characters also skipped the move and the member's permissions; a missing Manage Permissions also skipped the rename (one PATCH) | each step runs and logs its own refusal; an unusable name keeps the room's old name, with a warning; the permissions are a separate request | port-dynamic-voice-channel |
| DynamicVoiceChannel | a failed deletion still untracked the room, which then stayed forever | the room stays tracked, and a later leave or READY tries again | port-dynamic-voice-channel |
| DynamicVoiceChannel | an empty room was deleted on the leave event even when someone joined it right after | emptiness is checked right before the deletion | port-dynamic-voice-channel |
| DynamicVoiceChannel | a stage channel with a lobby's name threw and stopped that voice update's handling, its leave part included | stage channels are not lobbies | port-dynamic-voice-channel |
| DynamicVoiceChannel | a tracked room that kept the lobby's name could be copied again as a lobby | tracked rooms are never lobbies | port-dynamic-voice-channel |
| DynamicVoiceChannel | placeholders in display names were expanded again, and a self-reference stopped the rename; `dvc@custom_name` stayed in the member's shared placeholders | names are inserted as written, with each render's own values | port-dynamic-voice-channel |
| DynamicVoiceChannel | deleting the file of a left guild threw inside the loop over the files, which left the following guilds' bindings unloaded until the next restart; a guild unavailable at startup counted as left | every left guild's data is deleted; unavailable guilds keep theirs | port-dynamic-voice-channel |
| DynamicVoiceChannel | leaving a guild kept its bindings in memory (a wrong predicate) and its rooms in MongoDB | both are deleted | port-dynamic-voice-channel |
| DynamicVoiceChannel | the copy of a lobby lost its NSFW flag, video quality and slowmode | the copy keeps them | port-dynamic-voice-channel |
| DynamicVoiceChannel | the plugin did not load without SQLiteAPI, which it never used; an unreadable binding file was replaced by `[]`; the commands needed the core's auto-defer | no dependency; an unreadable document stops the handling with an error and is never overwritten; the command tree always defers the commands | port-dynamic-voice-channel |
| DynamicVoiceChannel | bindings in `plugins/DynamicVoiceChannel/data/<guildId>.json` and rooms in MongoDB's `DynamicVoiceChannel.generated_cache` | v3's binding documents and the rooms per guild in the SQLite store; v3's files and MongoDB are not read (migration deferred, B11) | port-dynamic-voice-channel |
| DynamicVoiceChannel | the en-US `unbind-fail` title said "is not be found" | it says "was not found" | port-dynamic-voice-channel |
| VoiceLogger | the first use after a start threw (`ConcurrentModificationException`) when a settings file held a left guild or a deleted listen channel, and the plugin then logged nothing until a restart, or never again | settings are read from the store at each use | port-voice-logger |
| VoiceLogger | a listen channel's first selection was saved in the block mode while the menu showed the allow mode, so after a restart the channel logged every voice channel | new entries keep the allow mode | port-voice-logger |
| VoiceLogger | "Delete" deleted the guild's whole settings file, so the guild's other listen channels lost their settings at the next restart | it deletes the channel's settings only | port-voice-logger |
| VoiceLogger | the switch embed's `Channel Join` showed an earlier join's channel or the placeholder itself | it shows the joined channel | port-voice-logger |
| VoiceLogger | a channel outside categories showed an earlier event's category or the placeholder | `-` | port-voice-logger |
| VoiceLogger | a status change named the user of the guild's newest type-192 audit log entry, whatever its channel or age, so a cleared status named the last person who set one; without such an entry or View Audit Log, nothing was posted | the entry of the change's type (192 or 193) and channel, made within 30 seconds, names the member; without one the log shows `-` | port-voice-logger |
| VoiceLogger | the audit log and the member were read for every status change, before the listen channels were looked for | only for changes that a listen channel detects | port-voice-logger |
| VoiceLogger | a log stopped at the first listen channel that no longer existed and threw for listen channels that were neither text nor voice channels | each listen channel gets the log on its own; a deleted one is forgotten, a refusing one is a warning | port-voice-logger |
| VoiceLogger | `/voice-logger setting` gave no reply outside plain text channels | the menu works in every channel, which can then be a listen channel | port-voice-logger |
| VoiceLogger | a list of more than about 22 channels made the menu throw after the selection was saved, so it never opened again | the list shows the lines that fit and `...` | port-voice-logger |
| VoiceLogger | `%...%` in channel names and statuses was expanded, and a status naming its own key made the log throw | names and statuses are shown as written | port-voice-logger |
| VoiceLogger | the values stayed in the member's shared substitutor, mixed between the status handler and the voice handler | each log renders with its own values | port-voice-logger |
| VoiceLogger | the settings of a left guild were deleted at the next start only; an unknown select menu action threw; an unreadable file was replaced by `{}`; the command needed the core's auto-defer | they are deleted on leave and at READY; no response; an error without overwriting; the command tree always defers the command | port-voice-logger |
| VoiceLogger | settings in `plugins/VoiceLogger/setting/<guildId>.json` | v3's document per guild in the SQLite store; v3's files are not read (migration deferred, B11) | port-voice-logger |
| ChatLogger | settings in `plugins/ChatLogger/setting/<guildId>.json` and messages in `plugins/ChatLogger/data/<guildId>.db`, one table per channel, growing forever | v3's settings documents in the store; the messages in `data/ChatLogger/messages-<UTC second>.db`, files of message ID ranges split at `max_file_size_mb` (256 MiB) and deleted whole once expired; v3's files are read only by the planned `xincord migrate` | port-chat-logger, chat-logger-split-storage |
| ChatLogger | messages were stored forever, deleted ones' too | they are kept `retention_days` days (1826, 5 years, by default), and a deleted message's text leaves its file once its deletion is handled | port-chat-logger, chat-logger-split-storage |
| ChatLogger | the database connections were never closed (their keys were listen channel IDs) | the message files open when the plugin loads and close when it unloads, after the work under way | chat-logger-split-storage |
| ChatLogger | `log_all: false` froze the logged channels to those that had a table; its start-up `DROP TABLE` always failed; leaving a guild deleted nothing (wrong key) | it stores the detected channels' messages; one table; a left guild's messages are deleted with `log_all: false` | port-chat-logger |
| ChatLogger | edits and deletions in threads were never posted, and the block mode never detected threads | threads are logged, detected through their channel and its category or by their own ID | port-chat-logger |
| ChatLogger | the deletion of a message whose author had left, or of a webhook's message, was not logged | it is logged with the stored author's mention and `-` | port-chat-logger |
| ChatLogger | bulk deletions (purges) were never logged | each stored message of one is logged, oldest first | port-chat-logger |
| ChatLogger | every `MESSAGE_UPDATE` counted as an edit, link previews included, whose text replaced the content | only a change of the text counts | port-chat-logger |
| ChatLogger | a message with embeds was stored without its content, with `null` for a missing title or description | the content and the rich embeds, without missing parts | port-chat-logger |
| ChatLogger | a message over 1024 characters lost its log; `%...%` in messages was expanded, and `%cl_msg_after%` made the log throw | texts are cut with `...` and shown as written | port-chat-logger |
| ChatLogger | a webhook's edit showed the placeholders themselves; a channel without a category showed an earlier category or the placeholder | the webhook's mention, and `-` | port-chat-logger |
| ChatLogger | VoiceLogger's settings defects (the first use threw, the first selection switched to the block mode, "Delete" deleted the guild's file, the menu only in text channels, posts stopped at a missing listen channel, long lists broke the menu) | fixed as in VoiceLogger, by the same shared code | port-chat-logger |
| Giveaway | v3's `plugins/Giveaway/data/<guildId>.json` | v3's document per guild in the store (namespace `Giveaway`), in Moshi's shape; v3's files are not read (migration deferred, B11) | port-giveaway |
| Giveaway | two quick presses of Confirm Create posted two giveaways | the draft is taken before the post; the second press answers that the session expired | port-giveaway |
| Giveaway | the builder rendered through the slash command's 15-minute hook, then silently stopped; long descriptions or prize lists froze it | each press or submission updates the builder; long fields end with `...` | port-giveaway |
| Giveaway | any builder message of a user drove their newest draft | only the builder message that shows the draft; others answer that the session expired | port-giveaway |
| Giveaway | a failed post replaced the builder with `create-failed` and left an orphaned draft; JDA's client-side errors said nothing | the builder and the draft stay, and `create-failed` with the error comes ephemerally | port-giveaway |
| Giveaway | the automatic draw refreshed and announced in text channels only, saved after queuing the posts, and could draw a giveaway that a manual draw drew too | any channel kind through partial messageables; stored first, under the guild's lock | port-giveaway |
| Giveaway | leaving a guild deleted its giveaways; giveaways of guilds left while offline were drawn silently | the giveaways stay; due ones wait until the bot is back in the guild | port-giveaway |
| Giveaway | an invalid `defaultLocale` aborted the bot; an uppercase `HTTPS://` thumbnail was accepted but never shown | the plugin does not load, with the key named; the thumbnail shows | port-giveaway |
| Giveaway | draft values were expanded as placeholders (a self-reference threw) and leaked into the global substitutor; the announcement pinged roles and everyone named in a title | values are inserted as written, per render; users only (B19) | port-giveaway |
| Giveaway | texts and templates were chosen separately (en-GB: English texts, zh-TW buttons) | one language per message: the locale's files, else zh-TW for Chinese and en-US | port-giveaway |
| Giveaway | the end time was read in the host's zone; `+12026-...` and `9999-12-31 24:00` were accepted | `timeZone` (empty for the host's); years up to 9999 | port-giveaway |
| Giveaway | a modal with an unknown sub-action re-rendered the preview; a post button without an ID answered `Invalid giveaway id.` in English | no response; `Giveaway not found.` in the user's language | port-giveaway |
| Giveaway | a drawn giveaway whose post was not refreshed (a crash after the draw, a refused edit) kept Reroll disabled for good; joins answered after the REST edit, which a burst delayed | every press is acknowledged at once and shows the stored giveaway in the post | port-giveaway |
| Plugin names | plugins named `_Example`, `BasicCalculator`, `SimpleCommand`, `WelcomeByeGuild`, `IntervalPusher` and `Feedbacker`, with their files in `plugins/<name>/` | `Example`, `Calculator`, `CustomCommands`, `WelcomeGoodbye`, `UptimeHeartbeat` and `Feedback` (decision B18 as amended) under `plugins:` and as `plugins/<Name>/`; `migrate_v3` maps the names and moves the v3 directories | rename-plugins |
| Feedback | the command was `/feedbacker` | `/feedback`; the zh-TW localized name is unchanged | rename-plugins |
| Ticket | panels in `plugins/Ticket/data/<guildId>.json`, rewritten at every load and created when read; a corrupt file was reset | v3's documents in the store (namespace `Ticket`), read without writing, a broken entry reported and kept; v3's files are read only by the planned v3 data import | port-ticket |
| Ticket | the preview button had no action and failed; `preview-reason` was unreachable (B1) | it opens `preview-reason`, titled with the reason title | port-ticket |
| Ticket | the zh-TW button modal's ID said `modify-btn-content`, so zh-TW users could not change the button's text or emoji (B2) | the bundled file says `modify-btn-text`, and the old ID is accepted | port-ticket |
| Ticket | `press-ticket`'s titles were swapped between zh-TW and en-US (B13) | each locale's own title in the bundled files | port-ticket |
| Ticket | the builder edited through the command's 15-minute hook (B14); a user's step served any guild and any of their builders | each interaction answers itself; drafts are per user and guild, only the newest builder works, older ones answer that the session expired | port-ticket |
| Ticket | colors were read after their first character: `0x00FFFF` failed, `FFFFFF` became `0x0FFFFF` (B5) | `#RRGGBB`, `0xRRGGBB` and `RRGGBB` with one to six hex digits; anything else is refused | port-ticket |
| Ticket | an invalid value (an empty title or icon URL, an invalid emoji) stayed in the draft and every later render failed silently | empty texts unset their part; a value Discord refuses answers its error and leaves the draft | port-ticket |
| Ticket | `/add-ticket` with a non-numeric ID, an unknown message or one without an embed stayed "thinking" or stored a broken draft (B7, B8, B9); a first row with a select passed the full check (B16); another user's message failed at the confirmation | each answers its error at once | port-ticket |
| Ticket | confirming deleted the builder first and never acknowledged, so failures were invisible (B15) | failures answer `create-failed` and keep the builder and the draft | port-ticket |
| Ticket | an added button's index was its row's size (B6); the edit kept the first embed and the first row only (B17), and a message without rows threw | the stored list's length; only the view changes; a message without rows gets a new row | port-ticket |
| Ticket | a missing category or panel after the reason left the member "thinking" (B3, B4) | v3's error texts arrive | port-ticket |
| Ticket | a reason that made the opener exceed 2000 characters left the channel without controls (B10) | the opener is split; a channel whose opener is refused is deleted | port-ticket |
| Ticket | the ticket channel had no overwrite for the bot, which needed Administrator or a staff role (B11) | the bot allows itself View Channel | port-ticket |
| Ticket | the opener and the archive used JDA's default mentions, so a typed `@everyone` pinged (S1) | the opener pings the staff roles only, the archive nobody | port-ticket |
| Ticket | lock and unlock answered after two REST calls, and a member who had left made the press fail | acknowledged at once; failures answer `lock-failed` | port-ticket |
| Ticket | an archive failure thrown in a callback (a 4000-character message, a refused webhook name, an upload over the limit) hung the archive and leaked the webhook (B12); a failed webhook left an empty thread | long texts are split, names fall back, large files are linked, every failure is reported and the webhook deleted, an empty thread is deleted | port-ticket |
| Ticket | en-US users got Chinese replies, zh-TW users four English errors | replies follow the user's locale (zh-TW where the plugin has no files); public texts stay zh-TW | port-ticket |
| Ticket | a guild's panels were deleted only on a leave seen while the plugin was enabled | also at READY for guilds the bot left while offline | port-ticket |
| Plugin names | `TicketAddons`, with its files in `plugins/TicketAddons/` | `TicketAwayNotice` under `plugins:` and as `plugins/TicketAwayNotice/`; `migrate_v3` maps the name and moves the directory | rename-plugins, port-ticket-away-notice |
| TicketAwayNotice | the guild filter never applied, so the notice was posted in every guild where the owner was a member and offline (B1) | only `guild_id` is watched; a warning at READY names a guild the bot is not in | port-ticket-away-notice |
| TicketAwayNotice | a matching thread, announcement, voice, stage, forum or category channel threw, logged by JDA (B2) | threads and every channel that takes messages get the notice; categories and forums are skipped quietly | port-ticket-away-notice |
| TicketAwayNotice | the owner was read without a member cache, so JDA reported offline and the notice was posted almost always (B3) | the members and presences intents keep the owner's status; only an offline owner gets a notice | port-ticket-away-notice |
| TicketAwayNotice | the notice was queued after one check and posted after the delay whatever happened, into a deleted channel or after the owner came online; nothing cancelled it | the channel and the owner are checked again when the wait ends; unloading cancels the waiting notices | port-ticket-away-notice |
| TicketAwayNotice | an invalid config stopped the bot even while disabled (B4), unknown keys failed the load, and the IDs took any text | only the plugin is disabled, unknown keys warn, and both IDs must be positive integers | port-ticket-away-notice |
| TicketAwayNotice | the bundled files held the shop's guild and owner IDs, its name and two channel IDs, and the text sat in the embed title, where channel mentions show as raw text | 0 for both IDs (the plugin waits for them), example values, the text in the description; operators' files keep theirs | port-ticket-away-notice |
| TicketAwayNotice | a template that could not be sent failed at each notice; a refused notice or a missing owner showed only as JDA's failure log | the template is checked at load, with the file named; warnings name the guild and the channel or the user | port-ticket-away-notice |
