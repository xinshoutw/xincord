## Context

v3's TicketAddons (`Plugins/TicketAddons`, 3 Kotlin files, 95 lines), which the owner renamed
TicketAwayNotice, has no commands, components or data. `Event` (`PluginEventConfigure`, a listener,
`Event.kt:7-30`) reads `config.yaml` (`enabled`, `guild_id`, `user_id`, `prefix`, `delay_millis`,
`ConfigSerializer.kt:6-26`) and forwards JDA's `ChannelCreateEvent` when enabled. The handler
(`TicketAddons.kt:24-39`) returns unless the new channel's name starts with a prefix, fetches the
configured member (`retrieveMemberById`, the cache else REST) and, when the member's
`onlineStatus` is `OFFLINE`, queues the `not-online` template (zh-TW, global placeholders) into
`event.channel.asTextChannel()` with `queueAfter(delay_millis)`. `info.yaml` requests the
`GUILD_PRESENCES` intent and the `ONLINE_STATUS` cache flag but no member cache policy. The
inventory is `docs/porting/analysis/inventory/TicketAddons.md`; its section 12 lists four
probable bugs (B1 to B4) and the behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's behavior (prefix matching on new channels, the offline check, the delay, the zh-TW
template with the global placeholders, v3's config keys so that v3's file loads); the four defects
fixed; the delay as a task that never blocks the event loop, ends with the plugin and checks the
channel and the owner again before posting; the first presence check in a plugin, with test
payloads that later ports reuse.

**Non-Goals:** matching Ticket's channels (see "Channel names"); other locales for the notice;
several owners or guilds; notices for channels created while the bot was offline; reloading
through the Web Dashboard (B13).

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/ticket_away_notice/`: `__init__.py` (metadata and
  `setup`), `config.py` (the config model and `watches`), `cog.py` (the listeners, the notices and
  the ready check), `config.yaml` and `lang/zh-TW/message/not-online.yaml`. Entry point
  `TicketAwayNotice = "xincord.plugins.ticket_away_notice"`; `migrate_v3.RENAMED` already maps
  `TicketAddons` to it and moves v3's `plugins/TicketAddons/` (its config and template) there.
- `INTENTS = discord.Intents(members=True, presences=True)`. Presences are privileged: without
  them Discord sends no statuses. The members intent keeps every member of the guild in discord.py's
  cache, so that a presence has a member to land on: with the presences intent, discord.py takes
  the members of small guilds from `GUILD_CREATE` and chunks large ones (`_guild_needs_chunking`),
  and `PRESENCE_UPDATE` updates cached members only. v3 requested `GUILD_PRESENCES` and no member
  cache policy (B3).
- `DEFAULT_LOCALE = "zh-TW"`, v3's only locale. No `register.yaml`: v3 had no commands.
  `DEPENDS` and `SOFT_DEPENDS` are empty (v3's `info.yaml` declared none, and the plugin does not
  need Ticket). No component IDs: v3 sent no components (its derived `ticketaddons@` prefix was
  unused). No storage.
- `setup` loads the lang files and the templates before the config, so that the first load writes
  both files even while the bundled config waits for the IDs (Economy's order), then checks that
  the notice can be posted (see "Problems").
- The bundled `config.yaml` holds 0 for `guild_id` and `user_id` (v3's file held the shop's real
  guild and owner IDs), v3's prefixes `客服單-` and `ticket-` and v3's 2000 ms, with comments that
  name the intents and give placeholder IDs. The bundled `not-online.yaml` keeps v3's text and
  footer (`❖ ORDERLY SERVER ❖`, as in the other plugins' bundled templates) with example values for
  the shop's name and its two channel IDs, written by a script that replaced them in v3's file; the text moves from the embed title into the description, where
  Discord shows channel mentions as links (in a title they show as raw `<#...>` text, inventory
  section 7). An operator's v3 file, moved by `migrate_v3`, keeps its title: `export_lang` writes
  missing files only.

### Config

`Config(Model)` has v3's four keys, all required as in v3 (`ConfigSerializer.kt:6-19` has no
defaults): `guild_id` and `user_id` are `PositiveInt` (v3's Strings, `require(isNotBlank)`; v3's
files hold unquoted 18-digit numbers, and pydantic also reads quoted ones), `prefix` a tuple of
strings with at least one item (`require(isNotEmpty)`), `delay_millis` an integer from 1 to Java's
`Long.MAX_VALUE` (`require(> 0)`). v3's `enabled` is not a field: a v3 file logs `unknown key
enabled`. An invalid file raises `ConfigError` in `setup`, so the core disables only this plugin
and names the key. `Config.watches(guild_id, name)` is the pure filter: the configured guild and
`name.startswith(prefix)`, case-sensitive as Kotlin's `startsWith`; an empty prefix matches every
name, as in v3.

### Watching

`on_guild_channel_create(channel)` and `on_thread_create(thread)` are cog listeners; discord.py
dispatches `thread_create` only for a newly created thread (`newly_created`), `thread_join`
otherwise. Both call `watch`, which reads the guild ID and the name before anything is awaited,
returns unless `Config.watches` holds, and checks the channel as `object` against `Postable`, a
`runtime_checkable` Protocol with `send` (text and announcement channels, voice and stage channels'
chats, threads and forum posts have it; categories and forum or media channels do not, and are
skipped at debug level). JDA's `ChannelCreateEvent` covered every kind too, but `asTextChannel()`
threw for all but text channels (B2). `watch` then starts the notice as a task and returns, so the
listener holds nothing up.

### The owner's status and the delay

A notice is an `asyncio` task kept in the cog's `notices` set until it ends (see "Problems" for its
failures). It:

1. reads the owner (`user_id`) from `guild.get_member`, else `await guild.fetch_member` (v3's
   `retrieveMemberById`); a member from Discord's REST API has no presence, so discord.py reports
   it `offline`, as JDA did;
2. returns unless `member.status is discord.Status.offline` (online, idle and do not disturb post
   nothing; invisible members look offline to bots, as in v3);
3. awaits the cog's `sleep` (`asyncio.sleep` by default; tests replace it) for `delay_millis /
   1000` seconds;
4. looks the guild up again through `bot.get_guild` and the channel through
   `guild.get_channel_or_thread`, and returns when either is gone (deleted, the bot left, or the
   thread archived: discord.py drops archived threads from its cache);
5. reads the owner's status again as in 1 and 2;
6. renders `not-online` in the default locale (v3 forced zh-TW) with
   `xincord.core.placeholders.global_values(bot)` (v3's `getCreateBuilder` without a substitutor)
   and sends its content, embeds, view and files to the channel.

v3 checked once, before `queueAfter`, which nothing could cancel. Steps 4 and 5 are new: v3 posted
into a channel deleted meanwhile (the send failed and was logged) and after the owner came online.

### The notice

`render_message(templates.message("not-online", lang.default_locale), global_values(bot))`; the
bot's `allowed_mentions` (users and the replied-to user, B19) apply. The bundled template is one
embed: author `範例商店` (an example shop name), the description holding v3's two lines with the
example channels `<#111111111111111111>` and `<#222222222222222222>`, and v3's footer `❖ ORDERLY
SERVER ❖`.

### Problems

- `discord.NotFound` from `fetch_member` (the owner is not in the guild): a warning that names the
  user and the guild, and no notice. v3 logged JDA's failure at each channel.
- Another `discord.HTTPException` from `fetch_member`: a warning with the error, and no notice.
- A notice that Discord refuses (`discord.HTTPException`, such as a missing Send Messages): a
  warning that names the channel and the guild. v3 left it to JDA's failure log.
- Any other failure inside the task (a dropped connection, an answer discord.py cannot read) is
  logged with its traceback by the task itself (`logger.exception`), so that none is lost in a task
  that nothing awaits; cancellation is no `Exception` and stays quiet.
- `setup` renders the `not-online` template once with no values and closes its files: a template
  that the plugin can never post (a component with a `uid`, a `model_key`, a missing `file_path`,
  too many rows) raises `ConfigError` with the file named, so the plugin does not load
  (CustomCommands' `_render_problem`). v3 failed at each notice.

### Unload

`cog_unload` cancels the waiting notices and awaits them; a reload builds a new cog, so the notices
that waited during a reload are dropped. The tasks hold no files or connections.

### Ready check

`check()` runs from an `on_ready` listener and from `cog_load` when `bot.is_ready()` (AutoRole's
pattern): a warning when `bot.get_guild(guild_id)` is None (the bot is not in the guild), nothing
for an unavailable guild, and a warning when `guild.get_member(user_id)` is None. With the members
intent, discord.py fires `on_ready` once the guilds' members are cached. With B1 fixed, a wrong
`guild_id` silently stops the notices, where v3 posted in every guild; this check names it.

### Channel names (Ticket)

Ticket names a ticket channel after the member's username and creates it with
`create_text_channel`, so `on_guild_channel_create` fires once per ticket (the archived
`port-ticket` design, "Channel names"). The default prefixes do not match such names, as in v3,
where TicketAddons predated Ticket and watched another ticket system's channels. This change keeps
v3's prefix matching, which also serves channels made by other bots, and leaves Ticket alone; the
owner's question about a `ticket-` prefix is in the review queue's Ticket section.

### Tests

- `tests/plugins/ticket_away_notice/`: `test_plugin.py` (installation), `test_config.py`,
  `test_watch.py`, `test_notice.py`, `test_problems.py`, `test_unload.py`, `test_ready.py`.
- The tests feed discord.py's own parsers (`plugin_fakes.add_guild`, `gateway`) with
  `CHANNEL_CREATE`, `THREAD_CREATE`, `PRESENCE_UPDATE`, `CHANNEL_DELETE`, `GUILD_DELETE` and
  `GUILD_MEMBER_REMOVE` payloads, so that the plugin gets discord.py's channels, threads and members
  with their statuses; `discord_fakes.FakeRest` records the REST requests (the notices' `POST
  /channels/{id}/messages`, the member lookups) and answers them. `payloads.guild` gains `members`
  and `presences`, `payloads.channel` a `guild_id`, and `payloads.presence` builds a presence.
- The delay runs on a fake `sleep` that records the delay and waits until the test wakes it, so
  that a test can change the cache during the wait; nothing sleeps in real time.
- Golden data (`tests/fixtures/plugins/ticket_away_notice/golden.yaml`): the bundled notice's
  embed, v3's prefixes and an operator's v3-style template with example values. No CJK text is
  typed in Python.

## v3 behaved differently

- v3 behaved differently: the guild filter was `!event.isFromGuild && event.guild.id !=
  config.guildId`, always false, so the notice was posted in every guild where the owner was a
  member and offline (B1); only `guild_id` is watched now.
- v3 behaved differently: `asTextChannel()` threw for a matching thread, announcement, voice,
  stage, forum or category channel, and JDA only logged it (B2); threads and every channel that
  takes messages get the notice, and categories and forums are skipped quietly.
- v3 behaved differently: the owner was read without a member cache and without presences in it, so
  JDA reported `OFFLINE` and the notice was posted almost always, unless the owner was the guild's
  owner or in a voice channel (B3); the members and presences intents keep the owner's status.
- v3 behaved differently: an invalid config failed the plugin's load even while disabled, and the
  core did not catch it, which stopped the bot (B4); the file is read only when `plugins` lists the
  plugin, and an invalid one disables only this plugin (core-plugin-loading).
- v3 behaved differently: the queued notice was posted after the delay whatever happened meanwhile,
  into a deleted channel (a logged failure) or after the owner came online, and nothing cancelled
  it; the plugin checks both again before posting, and unloading cancels the waiting notices.
- v3 behaved differently: `guild_id` and `user_id` took any non-blank text, and a user ID that was
  not a number failed at each channel; both must be positive integers when the plugin loads.
- v3 behaved differently: the bundled `config.yaml` held the shop's real guild and owner IDs, and
  the template its name and two channel IDs; the bundled files hold example values.
- v3 behaved differently: the template's text sat in the embed title, where Discord shows channel
  mentions as raw `<#...>` text; the bundled example puts it in the description.
- v3 behaved differently: an unknown key failed the whole load (kaml's strict mode); it only warns
  (core-config).
- v3 behaved differently: a template that could not be sent failed at each notice; it now keeps the
  plugin from loading, with the file named.
- v3 behaved differently: a refused notice or an owner missing from the guild showed only as JDA's
  failure log; warnings name the guild and the channel or the user, and the ready check names a
  missing guild or owner.

Kept on purpose: prefix matching, case-sensitive, on every new channel kind; the offline-only
check; a REST member's missing presence counting as offline; the delay; the zh-TW template for
everyone with the global placeholders only; no notice for channels created while the bot was away.

## User-visible changes

Copy: the comments of the bundled `config.yaml`, the bundled `not-online.yaml` (example shop name
and channel IDs; the text in the description), and operator log warnings (English).

1. The notice is posted only in `guild_id` (v3: in every guild where the owner was a member).
2. Threads, forum posts, announcement channels and voice and stage channels' chats with a matching
   name get the notice (v3 posted in text channels only and threw for the others).
3. The notice appears only while the owner is offline as Discord reports it (v3 posted almost
   always), and not when the owner comes online or the channel is deleted during the wait.
4. The plugin is `TicketAwayNotice` under `plugins:` and in `plugins/TicketAwayNotice/`; the bot
   then requests the privileged presences and members intents, which the developer portal must
   allow.
5. The bundled `config.yaml` holds 0 for both IDs, so the plugin does not load until they are set;
   v3's file, moved by `migrate_v3`, loads unchanged and warns `unknown key enabled`.
6. The bundled template holds example values and its text in the description; an operator's file
   keeps its own text and title.
7. Warnings at READY name a configured guild that the bot is not in and an owner who is not in it;
   warnings name a refused notice or a missing owner when a channel is created.

## Risks / Trade-offs

- The presences intent makes Discord send every member's status changes in every guild of the bot,
  and with the members intent discord.py keeps every member; memory is not a concern on the host
  (F2). The intent is requested for the whole bot as soon as the plugin is enabled.
- Requesting the privileged presences intent without the developer portal's permission makes
  Discord close the gateway (4014): the whole bot then does not connect.
- An owner that discord.py has not cached (a large guild still being chunked after a start or an
  outage) is read through REST without a presence and counts as offline, as in v3: a notice may
  then appear while the owner is online. `guild.query_members(user_ids=..., presences=True)` would
  ask the gateway for the presence instead.
- A notice that waits during a reload or an unload is dropped.
- Two channels created at once start two notices; there is no deduplication, as in v3.
- discord.py drops a `CHANNEL_CREATE` for a guild it has not cached, and Discord sends no event for
  a private channel that the bot cannot see: such channels get no notice, as in v3.

## Manual smoke checklist

On a test guild, with a bot token, the Presence and Server Members intents allowed for the bot in
the Discord developer portal, a second account as the owner and `plugins: [TicketAwayNotice]` in
`config.yaml`:

1. Start the bot with the bundled config: TicketAwayNotice does not load, and the error names
   `guild_id` and `user_id`; `plugins/TicketAwayNotice/` holds `config.yaml` and
   `lang/zh-TW/message/not-online.yaml`. Without the Presence intent in the portal, the bot does
   not connect (4014).
2. Set `guild_id` to the test guild and `user_id` to the second account, then run `/xincord reload
   TicketAwayNotice`: it loads and logs no warning. With a wrong `user_id`, a warning names it.
3. With the second account offline (or invisible), create a text channel `ticket-1`: about 2
   seconds later the bundled notice appears, its channel mentions shown as links.
4. With the second account online, idle or in do not disturb, create `ticket-2`: no notice.
5. With the account offline, create `ticket-3` and delete it within 2 seconds: no notice and no
   warning. Create `ticket-4` and bring the account online within 2 seconds: no notice.
6. Create a thread, a voice channel and a category named `ticket-5`: the thread and the voice
   channel's chat get the notice; the category gets nothing and nothing is logged as an error.
7. Create `ticket-6` in another guild where the account is a member: no notice.
8. Open a ticket with Ticket: no notice (its channel is named after the username).
9. Remove the bot's Send Messages permission in a category and create `ticket-7` in it: a warning
   names the channel.
