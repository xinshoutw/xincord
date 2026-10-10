## Context

v3's VoiceLogger (`Plugins/VoiceLogger`, 9 Kotlin files, 835 lines) shares most of its code with
ChatLogger. `Event` (`Event.kt:23-110`) exports the lang files, builds the localizers when `enabled`
is true and forwards five JDA events to `VoiceLogger` (`VoiceLogger.kt:29-439`): the slash command
`/voice-logger setting`, the menu's buttons and entity select menus (`voice-logger@a:<action>`),
`GuildVoiceUpdateEvent` and `ChannelUpdateVoiceStatusEvent`. `JsonManager` (`JsonManager.kt:17-117`)
keeps every guild's listen channel settings in `plugins/VoiceLogger/setting/<guildId>.json` and in
one global map, loaded lazily at the first event, when it also prunes left guilds and deleted
channels. `ChannelData` (`ChannelData.kt:8-77`) computes the detected voice channels of a listen
channel. The inventory is `docs/porting/analysis/inventory/VoiceLogger.md`; its section 12 lists
nine bugs and the behavior to preserve, and its section 14 calls the voice channel status the hard
part.

## Goals / Non-Goals

**Goals:** v3's command, menu, buttons, select menus and settings model (allow or block mode,
add-only lists, categories expanded at event time); v3's six log templates for joins, leaves,
switches and status changes in the guild's locale; v3's settings document in the store, so that
the deferred migration can copy v3's files; status changes logged with the right member, as far as
the audit log tells.

**Non-Goals:** migrating v3's settings files (B11); removing single list entries; logging mutes,
deafens, streams or video; reading the statuses voice channels had before the bot connected; the
Web Dashboard (B13).

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/voice_logger/`: `__init__.py` (metadata and
  `setup`), `settings.py` (pure: the settings, detection and the list texts), `store.py` (the
  settings in the store), `status.py` (pure where possible: status changes and their audit log
  entries), `cog.py` (the command, the components, the listeners, the posts and the checks at
  READY) and `lang/`. Entry point `VoiceLogger = "xincord.plugins.voice_logger"`.
- `DEPENDS` and `SOFT_DEPENDS` are empty. `INTENTS = discord.Intents(voice_states=True)`, v3's
  `GUILD_VOICE_STATES`; discord.py's defaults already hold it and the guilds intent, which carries
  `VOICE_CHANNEL_STATUS_UPDATE`. v3's `VOICE_STATE` cache flag and `VOICE` member cache policy are
  discord.py's defaults with that intent. The members intent is not needed: voice updates carry
  the member, and the member of a status change is fetched. `DEFAULT_LOCALE = "zh-TW"`, v3's
  default and fallback.
- `lang/` holds v3's 24 files (`register.yaml`, `placeholder.yaml` and `message/{voice-logger@setting,
  delete,modify-allow,modify-block,on-channel-join,on-channel-left,on-channel-switch,on-status-new,
  on-status-update,on-status-delete}.yaml` per locale), each with a final newline (six files had
  none). The texts are v3's.
- No `config.yaml`: v3's only key was `enabled`, which the core's `plugins` list replaces.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists the six modules, the 24 lang files and the
  `VoiceLogger` entry point; `xincord --no-online`, run from a scratch virtual environment with
  both wheels and `plugins: [VoiceLogger]`, writes the 24 lang files and no `config.yaml`, loads
  the plugin and exits with 0.
- A scratch probe drove the plugin through discord.py's own objects (a zh-TW guild added with
  `_add_guild_from_data`, `discord.Interaction` built from gateway payloads, the tree's `_call`,
  `bot.on_interaction`, `state.parse_voice_state_update` and `DiscordWebSocket.received_message`),
  with `HTTPClient.request` and the webhook adapter's `request` recorded: the command deferred with
  type 5 and the ephemeral flag and edited `@original` into the en-US menu; the allow list button
  answered type 7 with the select menu alone (channel types 2 and 4, 1 to 25, no embed); choosing
  the category answered type 7 with the menu listing it; v3's `voice-logger@a:toggle_btn` toggled
  twice; a join of a voice channel of that category posted the zh-TW join embed with
  `POST /channels/<listen channel>/messages`, a mute posted nothing, a switch to a channel outside
  categories posted the switch embed with `-`, and a leave that nothing detected posted nothing;
  `VOICE_CHANNEL_STATUS_UPDATE` messages through discord.py's gateway code were relayed: a set, a
  changed and a cleared status read `GET /guilds/10/audit-logs` with `action_type` 192, 192 and
  193 and `limit` 10, fetched `GET /guilds/10/members/7` and posted the three zh-TW status embeds;
  a stage channel's status posted nothing; a status cleared without an audit log entry read the
  audit log twice and posted `-` without a thumbnail.

### Core: gateway events discord.py does not parse

discord.py 2.7.1 has no parser for `VOICE_CHANNEL_STATUS_UPDATE` (its gateway logs "Unknown event"
and drops it), no `status` on `VoiceChannel`, and no `AuditLogAction` for the audit log types 192
and 193: its `AuditLogEntry` names them `unknown_192` and drops their `options`, where the channel
and the status are. Discord documents the event (fields `id`, `guild_id`, `status`, under the
guilds intent), the audit log types (`options.channel_id` for both, `options.status` for 192) and
that statuses are not part of channel objects (since 2026-04-20).

`Bot.relay_gateway_event(name)` adds a parser for `name` to discord.py's parser table
(`ConnectionState.parsers`, the dictionary that `DiscordWebSocket.received_message` looks events up
in, shared by every connection of the client) that calls discord.py's own parser for that event, if
any, and then `dispatch("gateway_<name in lower case>", payload)`. Cog listeners named
`on_gateway_<name>` receive the payload as Discord sent it. A second call for the same name does
nothing; the relay stays for the bot's life (a reload calls it again). The `gateway_` prefix keeps
the events apart from discord.py's own names, `raw_*` included. A scratch probe fed a
`VOICE_CHANNEL_STATUS_UPDATE` message through discord.py's real `DiscordWebSocket.received_message`
and a listener received the payload.

Alternatives: `enable_debug_events=True` with `on_socket_raw_receive`, discord.py's public hook,
which hands every gateway message to the listeners as text and makes the plugin parse each one
again; and `on_audit_log_entry_create` (the moderation intent), which discord.py parses without the
channel and the status of types 192 and 193.

### Settings and storage

`settings.py` is pure:

- `Setting(allow_mode=True, allow=(), block=())`, a frozen dataclass: v3's `ChannelData` with its
  `ChannelMode.Allow` default. Lists keep their order (v3's `LinkedHashSet`) and hold each ID once.
- `detects(setting, channel_id, category_id)`: in the allow mode, the channel or its category is in
  the allow list; in the block mode, neither is in the block list. This is v3's
  `getCurrentDetectChannels()` without the cache: v3 expanded allowed and blocked categories into
  their current children and compared the event's channel with them, which gives the same answer.
- `targets(settings, channels)`: the listen channels, in stored order, that detect any of the
  event's channels (`(id, category_id)` pairs; a switch has two).
- `list_text(ids, line, empty, values, prefix)`: v3's list field. Each ID renders the locale's
  `placeholder.<prefix>_list_format` with `<prefix>_channel_mention` (`<#id>`) and
  `<prefix>_channel_id` and the interaction's values, in one pass (v3 replaced the two keys and then
  ran the substitutor); an empty list renders `placeholder.empty`. When the lines exceed 1024 UTF-16
  code units, Discord's field limit, the text keeps the whole lines that fit with `...` after them:
  v3 threw there, after saving, so the menu of a list of about 22 IDs broke for good.

`store.py` keeps one document per guild in the key-value table: namespace `VoiceLogger` (the
plugin's name), key the guild ID in decimal, value v3's document unchanged,
`{"<listen channel ID>": {"allow_mode": <bool>, "allow": [<id>...], "block": [<id>...]}}`, in
Moshi's field order, so that the deferred migration (B11) can copy v3's `setting/<guildId>.json`.

- `read_settings(store, guild_id)` and `read_setting(store, guild_id, channel_id)` never write; a
  missing entry is `Setting()` (v3's `computeIfAbsent` default, which v3 kept in memory only).
- `toggle`, `add_channels(store, guild_id, channel_id, kind, ids)` (kind `allow` or `block`; IDs
  already listed are skipped) and `remove` change one entry and return the new `Setting` (or whether
  there was one); `prune(store, guild_id, exists)` drops the listed IDs for which `exists` is false
  and returns them; `forget` deletes the document; `guild_ids` lists the guilds with one.
- A change runs under `store.lock("VoiceLogger:<guild ID>")` and reads the document again there
  (WelcomeByeGuild's and DynamicVoiceChannel's pattern), so concurrent menus never lose a change.
  A change that changes nothing writes nothing, and the document goes with its last entry (v3 kept
  an empty file). Entries that a change does not touch stay as they were; a changed entry is
  written in v3's shape, dropping unknown fields as v3's save did.
- New entries start in the allow mode, as the menu showed them: v3 saved a listen channel's first
  selection with `allow_mode: false` while its memory said allow, so the mode flipped to block at
  the next start.
- A document that is not an object, a key that is not a channel ID, or an entry that is not an
  object with a boolean `allow_mode` and integer lists `allow` and `block` (Moshi's required
  fields) raises `DataError`, which names the guild; nothing is written then. v3's Moshi failed on
  such files too, and Core replaced them with `{}`.

### Command

`VoiceLogger.command()` builds v3's group with `app_commands.Group(name=..., description=...,
default_permissions=discord.Permissions(administrator=True))` in `cog.py` and one
`app_commands.Command` subcommand, `setting`, whose callback is the cog's bound method
`show_settings`. Names and descriptions come from `register.yaml` (`voice-logger.name`,
`.description`, `.subcommands.setting.name` and `.description`; v3 looked them up as Kotlin
properties, `voiceLogger.*`), with v3's base texts from `Register.kt`. The tree defers it
ephemerally, as v3's core did; there is no runtime permission check, as in v3.

`show_settings` reads the setting of `interaction.channel_id` and edits the deferred response into
the menu: `voice-logger@setting` in `interaction.locale` (v3's `event.userLocale`) with
`placeholder_values(interaction)` (v3's `Placeholder.get(event)`, which threw outside text channels
and now works in every channel), `vl_channel_mode` (`ALLOW` or `BLOCK`), `vl_allow_list_format` and
`vl_block_list_format`.

### Components

- `IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")`: v3's only
  field, `action` (a string), and v3's `component_prefix`. `setup` routes it to `handle`.
- `handle(interaction, parsed)` dispatches on the component type and `action`, as v3's two
  handlers did: buttons (type 2) with `toggle_btn`, `modify_allow_btn`, `modify_block_btn` and
  `delete_btn`; entity select menus (types 5 to 8, v3's `EntitySelectInteractionEvent`) with
  `modify_allow_menu` and `modify_block_menu`. Anything else gets no response (v3 ignored unknown
  buttons and threw for unknown select menus).
- Each answers with `interaction.response.edit_message(...)` of the rendered template, content,
  embeds, view and attachments, which replaces the whole message as JDA's
  `MessageEditData.fromCreateData` did (v3's `deferEdit` and `editOriginal` became one request):
  `toggle_btn` toggles and shows the menu; `modify_*_btn` shows `modify-allow` or `modify-block`
  (the select menu alone, v3's 1 to 25 voice channels and categories); the select menus add their
  `values` to the list and show the menu; `delete_btn` removes the channel's settings and shows
  `delete`, without components. The listen channel is `interaction.channel_id`, as v3's
  `event.channel`; templates render in the user's locale with `placeholder_values(interaction)`.
- The menu is ephemeral, so the core never upgrades its legacy IDs; v3's IDs are still routed.

### Voice changes

`on_voice_state_update(member, before, after)` handles channel changes only (`before.channel` and
`after.channel` differ by ID), as JDA's `GuildVoiceUpdateEvent`. It reads both channels' IDs,
names, mentions, jump URLs and category IDs at once, before anything awaits (later events change
discord.py's cache meanwhile), then the guild's settings and the targets. Without targets it stops.
The values are `actor_values(member, bot)` (v3's `Placeholder.get(member)`: the member whose state
changed, bots included, also when a moderator moved them) and, per side, `vl_channel_<side>_mention`,
`_name`, `_url` and `vl_category_<side>_mention` (`<#category>`, or `-` without a category), with
`<side>` `join` or `left`. A join is `on-channel-join`, a leave `on-channel-left` and a switch
`on-channel-switch` with both sides.

### Posts

`_post(guild, targets, name, values)` renders the template for each target again (discord.py closes
a message's files once sent) in `guild.preferred_locale` (v3's `guild.locale`; the `Templates`
fall back to zh-TW, v3's default) and sends it to `bot.get_partial_messageable(target,
guild_id=...)`: the listen channel is where an administrator ran the command, any channel that
takes messages, and posting needs no cache. A `discord.NotFound` (the channel is gone) removes the
listen channel's settings with an info line; another `discord.HTTPException` is a warning naming the
guild and the channel. Either way the other targets still get the log. v3 looked the channel up in
the cache, returned at the first missing one and threw for channels other than text and voice
channels.

### Voice channel status

- `setup` relays `VOICE_CHANNEL_STATUS_UPDATE`; `on_gateway_voice_channel_status_update(payload)`
  reads `id`, `guild_id` and `status` (null or missing is empty; a malformed payload is ignored with
  a warning).
- The cog keeps `statuses`, each voice channel's last status from these events, in memory, as JDA's
  channel cache did. A status is empty until an event names it: Discord sends statuses in no channel
  object, so JDA's cache started empty too. Before anything awaits, the listener reads the cached
  guild and channel (nothing for an uncached guild or channel, or a channel that is not a voice
  channel: JDA's `VoiceChannel` lookup), compares the new status with the tracked one (nothing when
  equal, as JDA), records the new one, and reads the channel's mention, jump URL and category.
- `status.classify(old, new)`: `delete` when the new status is empty, else `new` when the old one
  is, else `update` (v3's order). Templates `on-status-delete`, `on-status-new` and
  `on-status-update`; values `vl_channel_mention`, `vl_channel_url`, `vl_category_mention` (or
  `-`), `vl_status_before` (the old status) and `vl_status_after` (the new one), both always set.
- Without targets the listener stops before any request (v3 read the audit log and the member
  first, for nothing).
- The member: `status.find_actor(fetch, channel_id, status, at, sleep)` reads the guild's audit log
  (`GET /guilds/<id>/audit-logs?action_type=<type>&limit=10` through `bot.http.request(Route(...))`,
  because discord.py's `Guild.audit_logs` drops the fields), type 192 for a set or changed status and
  193 for a cleared one. `status.match(log, kind, channel_id, status, at)` takes the entries of that
  type whose `options.channel_id` or `target_id` is the channel and whose ID's time is within 30
  seconds of `at` (when the listener started), and returns the user of the newest one whose
  `options.status` is the new status, else of the newest one. Without a match, the audit log is read
  once more after 2 seconds, in case its entry comes after the gateway event. The user is fetched as
  the guild's member (`guild.fetch_member`, v3's `retrieveMemberById`) for `actor_values`.
- Without a member (no entry, as for a status that Discord clears by itself; an audit log that
  Discord refuses, logged as a warning that names the guild; a user who left), the log is still
  posted, with the bot's values and `-` for the user's and the member's texts and no avatar URL, so
  the shipped templates show `-` and no thumbnail. v3 posted nothing when the audit log had no entry
  of type 192 or could not be read, and attributed everything else to the newest type-192 entry of
  the guild.

### Left guilds and checks at READY

`on_guild_remove` deletes the guild's settings. `on_ready`, and `cog_load` in a ready bot, run
`check_guilds()`: for each guild with settings, a guild that `bot.get_guild` does not know is a
guild the bot left, and its settings are deleted with an info line (v3's `JsonManager` deleted the
files of such guilds at its first use, inside a loop that then threw); an unavailable guild is left
alone; in an available guild, `prune` drops the allow and block IDs that `guild.get_channel` does
not know, with an info line, as v3's startup did. A guild whose settings cannot be read is skipped
with an error. Listen channels are not checked at READY: a deleted one is forgotten when a log
finds it gone, and a listen channel in a thread is not cached while the thread is archived.

### Tests

- `tests/plugins/voice_logger/`: `test_plugin.py`, `test_store.py`, `test_settings.py` (detection
  and list texts), `test_menu.py`, `test_components.py`, `test_command.py`, `test_voice.py`,
  `test_post.py`, `test_status.py`, `test_actor.py`, `test_forget.py` and `test_check.py`;
  `conftest.py` loads the plugin, records REST requests with `FakeRest` (autouse), gives the bot its
  user (autouse), sends the posts to fake channels through `get_partial_messageable` and finds the
  cog with `cast`.
- `tests/core/test_gateway.py` covers `relay_gateway_event`; `plugin_fakes.gateway(bot, name,
  payload)` hands a payload to the bot's parser table as discord.py's gateway does and awaits the
  listeners it dispatched.
- `tests/support/discord_fakes.py`: `FakeRest` also records query parameters and can answer a
  request with a payload (the audit log); `FakeGuild.fetch_member` finds `members` or raises
  `NotFound`; `FakeVoiceChannel.jump_url`.
- `tests/fixtures/plugins/voice_logger/golden.yaml`: v3's embeds per locale for the menu, `delete`,
  the select menus and the six logs, and the translated command payload.

### v3 behaved differently

- v3 behaved differently: `JsonManager`'s first use threw a `ConcurrentModificationException` when a
  guild's file belonged to a guild the bot had left or held a deleted listen channel, and every
  later use threw `NoClassDefFoundError`, so the plugin logged nothing until a restart, or never
  again (a deleted listen channel that was not the file's last); settings are read from the store at
  each use.
- v3 behaved differently: the first selection of a listen channel was saved in the block mode while
  the menu showed the allow mode, so the channel switched to the block mode, logging every voice
  channel, after a restart; new entries keep the allow mode.
- v3 behaved differently: "Delete" deleted the guild's whole settings file, so every other listen
  channel of the guild lost its settings at the next restart; it deletes the channel's settings
  only.
- v3 behaved differently: the switch embed's `Channel Join` used `%vl_channel_join_mention%`, which
  the switch never set, so it showed an earlier join's channel or the placeholder itself; it shows
  the joined channel.
- v3 behaved differently: the category values were set only when the channel had a category, so a
  channel outside categories showed an earlier event's category or the placeholder; it shows `-`.
- v3 behaved differently: the member of a status change was the user of the guild's newest audit
  log entry of type 192, whatever its channel or age, so a cleared status (type 193) and a status
  that Discord cleared by itself named the last person who set any status, and the log was not
  posted when the guild had no type-192 entry or the bot lacked View Audit Log; the entry must match
  the change's type and channel and be recent, and the log is posted with `-` without one.
- v3 behaved differently: a log stopped at the first listen channel that no longer existed and threw
  for listen channels that were neither text nor voice channels; each listen channel gets the log on
  its own, a deleted one is forgotten and a refusing one is a warning.
- v3 behaved differently: `/voice-logger setting` gave no reply outside plain text channels
  (`Placeholder.get(event)` threw); the menu works in every channel, which can then be a listen
  channel.
- v3 behaved differently: a list longer than about 22 channels made the menu throw, after the
  selection was saved, so the menu of that channel never opened again; the list shows the lines
  that fit and `...`.
- v3 behaved differently: `%...%` in channel names and statuses was expanded, and a status naming
  its own key, such as `%vl_status_after%`, made the log throw; names and statuses are shown as
  written.
- v3 behaved differently: the `vl_*` and member values stayed in the member's shared substitutor,
  where the status handler (on REST threads) and the voice handler (on the gateway thread) mixed
  them; each log renders with its own values.
- v3 behaved differently: the settings of a guild the bot left were deleted only at the next
  start; they are deleted when the bot leaves, and at READY for guilds left while offline.
- v3 behaved differently: an unknown select menu action threw; it gets no response, as unknown
  buttons did.
- v3 behaved differently: the command needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers it.
- v3 behaved differently: an unreadable settings file was replaced by `{}`, losing the guild's
  settings; an unreadable document stops the handling with an error and is never overwritten.

Kept on purpose: only channel changes are logged; a switch is one event, posted to every listen
channel that detects either side; bots are logged, and a moderator's move or disconnect names the
moved member; logs use the guild's locale and the menu the user's, with zh-TW as fallback; the
settings model (allow or block, add-only lists, categories expanded at each event, the allow mode
for channels without settings); "Delete" without a confirmation; the menu is ephemeral and its
buttons have no expiry; no permission check besides Discord's default; the computed `locale` that
v3 never used stays unused (logs follow `guild.locale`); IDs added in one selection keep the order
Discord sends them (v3's `HashSet` had none).

### User-visible changes

- The menu answers in every channel, and logs reach threads, voice and stage chats and
  announcement channels set up as listen channels (v3: text channels only, no reply elsewhere).
- A listen channel's first selection keeps the allow mode after a restart; "Delete" deletes only
  that channel's settings.
- The switch embed shows the joined channel's mention; a channel without a category shows `-` in
  the category fields.
- A status change names the member of its own audit log entry; without one (a status Discord
  cleared by itself, a missing View Audit Log, a member who left) it is posted with `-` and no
  thumbnail instead of not at all or with the wrong member.
- A listen channel that refuses a log no longer stops the others; a deleted one is forgotten.
- A long list ends with `...` instead of breaking the menu.
- Channel names and statuses are shown as written.
- Settings of a guild the bot leaves are deleted at once; channels deleted from the lists are
  dropped when the bot is ready.
- v3's settings in `plugins/VoiceLogger/setting/*.json` are not read: listen channels must be set
  up again (the data migration is deferred, B11).
- No `plugins/VoiceLogger/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.

## Risks / Trade-offs

- The relay writes into discord.py's internal parser table and the audit log is read through the
  undocumented `HTTPClient.request` and `Route`; a discord.py upgrade must keep both working (the
  tests run the relay through the table, the probe through discord.py's gateway). If discord.py
  starts parsing the event, the relay still runs after its parser.
- Statuses set before the bot connected, or before a reload of the plugin, are unknown: the first
  change of such a status is logged as a new status, and its clear is not logged, as in v3 (whose
  cache started empty). Discord's Request Channel Info (gateway opcode 43) could read them.
- The audit log is read once or twice per detected status change; a status that Discord clears by
  itself always costs two reads and a 2-second delay.
- Attribution depends on Discord's audit log: two changes of one channel within 30 seconds whose
  entries lack the status, or an entry later than 2 seconds, can name the wrong member or none.
- discord.py passes the cached voice state as `after`, so a join and a leave that discord.py parses
  before the listener runs reach the listener as no change (the join is not logged), and a switch
  followed by a leave as a leave from the first channel. JDA handled each event before the next.
- A deleted listen channel is forgotten only when a log tries to reach it; until then its settings
  stay in the store.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [VoiceLogger]` in `config.yaml`, a category `Voice`
with the voice channels `Room A` and `Room B`, a voice channel `Loose` outside categories, the text
channels `#log` and `#log-2`, and two accounts (an administrator and a member). The bot needs View
Channel, Send Messages and Embed Links in the log channels, and View Audit Log.

1. Start the bot: the log lists `VoiceLogger` as loaded, and the 24 files exist under
   `plugins/VoiceLogger/lang/`; no `config.yaml` is written there.
2. As the member, the command list does not show `voice-logger`. As the administrator, run
   `/voice-logger setting` in `#log`: an ephemeral `Voice Log` embed with `<ALLOW>`, `Empty` twice
   and four buttons.
3. Press `Modify Allowlist`: the message becomes a select menu offering voice channels and
   categories; choose the category `Voice`: the menu lists it. Press `Toggle Mode` twice: `<BLOCK>`,
   then `<ALLOW>`.
4. As the member, join `Room A`: `#log` gets a green `Voice Channel Joined` embed with the member,
   the category and `Room A`. Switch to `Room B`: a yellow switch embed with both channels, both
   mentions shown. Switch to `Loose`, then leave it: the switch is posted (from a detected channel),
   the leave is not (not detected). Mute and unmute in `Room A`: nothing.
5. Run the command in `#log-2`, toggle to `<BLOCK>`, block `Room B`. Join `Loose` and leave it:
   `#log-2` gets both, with `-` as the category; `#log` gets neither.
6. In `Room A`, set the voice channel status `Gaming`: `#log` gets `New Voice Status` naming the
   member who set it. Change it to `Chill`: `Voice Status Updated` with both. Clear it:
   `Voice Status Deleted` naming that member. Set a status and leave the channel so that it empties:
   if Discord clears the status, the log shows `-` as the member (record what happens).
7. Take View Audit Log away from the bot and change a status: the log shows `-`, and the bot's log
   warns that the audit log was refused.
8. Run the command in a voice channel's chat and in a thread: the menu answers in both.
9. Delete `#log-2`, then join `Loose`: the bot's log says that the listen channel was forgotten.
   Press `Delete` in `#log`'s menu: `Deleted Successfully`, and joins are no longer posted there.
10. Switch the administrator's client and the guild's language to zh-TW: the menu, the select menu
    placeholder and the logs are v3's zh-TW texts.
11. Restart the bot after deleting a category that a list holds: the bot's log says that it was
    dropped, and the menu no longer lists it.
