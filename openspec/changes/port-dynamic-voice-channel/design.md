## Context

v3's DynamicVoiceChannel (`Plugins/DynamicVoiceChannel`, 7 Kotlin files, 539 lines) binds voice
channels as lobbies by (category, exact name). `Event` (`Event.kt:21-78`) exports the lang files,
builds the localizer when `enabled` is true and forwards three JDA events to `DynamicVoiceChannel`
(`DynamicVoiceChannel.kt:19-135`): the slash command (`bind` and `unbind`, which v3's command
filter never lets through since commit `ea14fbf`), the guild leave and the voice updates.
`JsonManager` (`JsonManager.kt:30-142`) keeps the bindings in `plugins/DynamicVoiceChannel/data/
<guildId>.json` and in memory, and validates them once, lazily, after startup. The rooms the plugin
created are tracked in Core's embedded MongoDB (`DynamicVoiceChannel.generated_cache`, through
`MemoryCacheDb`). The inventory is `docs/porting/analysis/inventory/DynamicVoiceChannel.md`; its
section 5 lists eight race conditions and failure modes and its section 12 eleven bugs and the
behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's command, replies and binding rules; v3's room life cycle (copy, rename, move,
owner permissions, deletion when empty); v3's binding document in the store, so that the deferred
migration can copy v3's files; rooms that are never lost or orphaned by a race, a failed request
or a restart.

**Non-Goals:** migrating v3's binding files and MongoDB's tracker (B11); a meaning for
`format-name-2`; new room features (limits, moving members, commands for owners); the Web
Dashboard (B13).

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/dynamic_voice_channel/`: `__init__.py` (metadata
  and `setup`), `store.py` (the bindings and the rooms in the store), `names.py` (pure: the room
  name), `cog.py` (the command, the listeners and the checks at READY) and `lang/`. Entry point
  `DynamicVoiceChannel = "xincord.plugins.dynamic_voice_channel"`.
- `DEPENDS` and `SOFT_DEPENDS` are empty: v3's `depend_plugins: [SQLiteAPI]` was never used.
  `INTENTS = discord.Intents(voice_states=True)`, v3's `GUILD_VOICE_STATES`; discord.py's default
  intents already hold it, and the declaration documents the need. v3's `VOICE_STATE` cache flag
  and `VOICE` member cache policy are discord.py's defaults with that intent (`MemberCacheFlags.
  from_intents`); the plugin counts a channel's members from `channel.voice_states`, which needs no
  member cache. `DEFAULT_LOCALE = "zh-TW"`, v3's hard-coded default and fallback.
- `lang/` holds v3's ten files (`register.yaml` and `message/{bind-success,must-under-category,
  unbind-fail,unbind-success}.yaml` per locale) with a final newline (the en-US `register.yaml`
  had none). The en-US `unbind-fail` title reads "Unbind fail, the channel was not found in
  settings" (v3: "is not be found").
- No `config.yaml`: v3's only key was `enabled`, which the core's `plugins` list replaces.

### Storage

`store.py` keeps two documents per guild in the store's key-value table, both keyed by the guild
ID in decimal:

- Bindings, namespace `DynamicVoiceChannel` (the plugin's name): v3's document unchanged, a list of
  `{"categoryId": <int>, "defaultName": <str>, "formatName1": <str>, "formatName2": <str>}` in
  Moshi's field order, so that the deferred migration (B11) can copy v3's `data/<guildId>.json`.
  `Binding(category_id, default_name, format_name_1="", format_name_2="")` is a frozen dataclass.
  - `read_bindings(store, guild_id)` never writes; a guild without a document has none; a missing
    format reads as `""` (Moshi's defaults). `find(bindings, category_id, name)` returns the first
    binding of that category and exact name, as v3's set kept the first of duplicates at startup.
  - `bind(store, guild_id, binding)` removes every entry of the binding's category and name and
    appends the new one: v3 appended a duplicate and replaced it in memory only.
  - `unbind(store, guild_id, category_id, name)` removes every entry of that category and name and
    returns whether there was one; nothing is written when there was none, and the document is
    deleted when no binding is left (v3 kept an empty `[]` file). `drop(store, guild_id, keys)`
    removes the entries of several keys, for the checks at READY.
  - Entries that a change does not match stay as they were, unknown fields included.
- Rooms, namespace `DynamicVoiceChannel.rooms`: `{"<room ID>": <owner ID>}`, the pairs of v3's
  MongoDB documents (`{_id: "<room ID>", value: <owner ID>, timestamp}`), grouped by guild because
  the checks at READY need to know whether a room's guild is unavailable or left. The owner is
  kept, as in v3, and not read. `read_rooms`, `track(store, guild_id, room_id, owner_id)` and
  `untrack(store, guild_id, room_id)` (nothing written for an unknown room; the document deleted
  with the last room).
- `forget(store, guild_id)` deletes both documents; `guild_ids(store)` lists the guilds with either.
- Every change runs under `store.lock("DynamicVoiceChannel:<guild ID>")` (WelcomeByeGuild's
  pattern) and reads the document again there, so that concurrent commands, checks and voice
  changes never lose one another; reads take no lock.
- A bindings document that is not a list, or an entry that is not an object with an integer
  `categoryId`, a text `defaultName` and, when present, text formats, raises `DataError`, which
  names the guild; so does a rooms document that is not an object of decimal room IDs to integers.
  Nothing is written then. v3's Moshi failed on such files too, and Core replaced them with `[]`.

### Commands

- `DynamicVoiceChannel.command()` builds v3's group with `app_commands.Group(name=..., description=
  ..., default_permissions=discord.Permissions(administrator=True))`, v3's
  `setDefaultPermissions(enabledFor(ADMINISTRATOR))`, and adds two `app_commands.Command`s whose
  callbacks are the cog's bound methods `bind_lobby` and `unbind_lobby`, so the cog is their
  binding. The group is built in `cog.py`, so its `module` is the plugin's and unloading removes it.
  Names and descriptions come from `register.yaml` (`dynamic-voice-channel.name`, `.description`,
  `.subcommands.<bind|unbind>.name`, `.description` and `.options.<channel|format-name-1|
  format-name-2>.<name|description>`; v3 looked them up as Kotlin properties, `dynamicvc.*` and
  `formatName1`), with v3's base texts from `Register.kt`. `rename` and `describe` are each called
  once with every option of a subcommand. The en-US option names stay v3's `name-format-1` and
  `name-format-2`, while the base names are `format-name-1` and `format-name-2`.
- `channel` is `app_commands.Transform[app_commands.AppCommandChannel, VoiceChannelOption]`, a
  copy of WelcomeByeGuild's transformer with `channel_types` [voice]: JDA's `as VoiceChannel` cast
  threw for every other type, stage channels included. Both formats are plain required strings, as
  in v3.
- The tree defers both subcommands ephemerally, as v3's core did; each reply edits that response
  with the template rendered in `interaction.locale` (v3's `event.userLocale`) and
  `placeholder_values(interaction)` (v3's `Placeholder.get(event)`, which threw outside text
  channels and now works everywhere). Without a guild, which guild commands never meet, the
  callbacks return without an answer.
- `bind_lobby`: a channel without a category gets `must-under-category`; otherwise `bind` stores
  `Binding(channel.category_id, channel.name, format_name_1, format_name_2)` and the reply is
  `bind-success`. `unbind_lobby`: no category gives `must-under-category`; otherwise `unbind`
  removes the bindings of the channel's category and current name, and the reply is
  `unbind-success` or `unbind-fail`. Each change is logged at info level. There is no server-side
  permission check, as in v3: Discord shows the command to administrators.

### Room names

`names.py` is pure: `custom_name(display_name)` is v3's `effectiveName.split(" - ").first()` (the
display name, `nick or global_name or name`, as JDA's `effectiveName`), and `room_name(template,
values)` renders format 1 in one pass with the core's `render`, strips whitespace and returns None
for a blank result or one longer than 100 UTF-16 code units, JDA's `setName` checks. The values are
`actor_values(member, bot)` (v3's `Placeholder.get(member)`: `bot_id`, `bot_name`, `user_id`,
`user_mention`, `user_name`, `user_avatar_url`, `member_display_name`, `member_avatar_url`,
`member_fixed_name`) and `dvc@custom_name`.

### Rooms

`on_voice_state_update(member, before, after)` handles channel changes only (`before.channel` and
`after.channel` differ), as JDA's `GuildVoiceUpdateEvent`; discord.py also fires it for mutes,
deafens and streams.

- **Alone in the joined channel.** JDA ran the listener on its event thread with the cache as of
  that event; discord.py runs listeners as tasks, and later events may update the cache before one
  runs. The listener therefore reads the joined channel's `voice_states` first, before anything
  awaits, and goes on only when they hold the member alone.
- **One guild at a time.** The rest runs under `store.lock("DynamicVoiceChannel:voice:<guild
  ID>")`, so that a leave waits for the room that the join is creating (v3 tracked rooms in memory
  at once and in MongoDB later, and read MongoDB on leaves, so a quick leave left an orphan room).
  The lock is outside the store's data lock and nothing takes them in the other order. Both are
  the store's, so a plugin reloaded during a creation still waits for it.
- **Creation** (`DynamicVoiceChannel.kt:94-135`): the joined channel must be a voice channel (a
  stage channel threw in v3's `asVoiceChannel`) in a category, `find` must match its category and
  exact name, and it must not be a tracked room. If the member left the channel while the handler
  waited, nothing happens. Then, in v3's order:
  1. `copy = await lobby.clone()`: discord.py's clone copies the name, bitrate, user limit, RTC
     region, category and every overwrite, as JDA's `createCopy`, and also the NSFW flag, the video
     quality and the slowmode, which JDA left at Discord's defaults. If Discord refuses, a warning
     names the guild and the lobby, and nothing else happens: the lobby stays as it was.
  2. `track` the joined channel as the member's room: from here on, the copy is the lobby and
     deleting the room cannot lose it. v3 tracked the lobby before any request, so a refused copy
     made the lobby itself be deleted when it emptied.
  3. `PATCH /channels/<copy>` with `{"position": 0}`, JDA's `setPosition(0)`, through
     `bot.http.request(Route(...))`: discord.py's `edit(position=...)` instead renumbers every
     voice channel of the guild in one bulk request.
  4. `PATCH /channels/<room>` with `{"name": <format 1>, "position": 1}`, or `{"position": 1}` and
     a warning when the name is unusable (v3's `setName` threw there and skipped the whole PATCH).
  5. `room.set_permissions(member, overwrite=PermissionOverwrite(manage_channels=True,
     manage_permissions=True))`, a `PUT` of the member's overwrite (bits 4 and 28, allowed, none
     denied), which keeps the other overwrites as JDA's `putMemberPermissionOverride` did. v3 sent
     steps 4 and 5 in one PATCH, so a missing Manage Permissions also cost the rename.
  Steps 3 to 5 each log a warning when Discord refuses them, and the others still run; v3's
  `flatMap` chain stopped at the first failure. The room stays tracked either way.
- **Deletion** (`DynamicVoiceChannel.kt:104-109`): when the member left a channel (or moved out of
  it), the handler checks, under the lock, that the channel is empty and tracked, deletes it and
  forgets it. A 404 (already deleted) also forgets it; another refusal keeps it tracked and logs a
  warning, so the next empty leave or READY tries again (v3 untracked it even when the delete
  failed). Checking emptiness under the lock, right before the request, also spares a member who
  joined in between (JDA deleted on the leave event regardless). A move handles the joined channel
  first and the left one second, as v3.
- Bots, the bot itself included, get rooms as in v3.

### Checks at READY

`on_ready` and `cog_load` in a ready bot run `check_guilds()` (WelcomeByeGuild's
`forget_left_guilds`, extended): for each guild with bindings or rooms,

- a guild that `bot.get_guild` does not know is a guild the bot left: both documents are deleted
  with an info line (v3's `JsonManager` deleted that guild's file, inside a loop that then threw);
- an unavailable guild (an outage) is left alone; JDA did not list such guilds, so v3 deleted their
  bindings at startup;
- in an available guild, under the voice lock: a binding whose category is gone, or whose category
  holds no voice channel with the lobby's exact name (JDA's `getVoiceChannelsByName(name, false)`),
  is dropped with a warning, as v3's startup validation did; a tracked room that no longer exists is
  forgotten; a tracked room without members is deleted as on a leave. v3 never looked at its rooms
  again: rooms that emptied while it was away stayed, and their documents too.

`on_guild_remove` deletes the guild's bindings and rooms (v3 deleted the binding file only, and its
in-memory predicate removed nothing).

### Tests

- `tests/plugins/dynamic_voice_channel/`: `test_plugin.py`, `test_store.py`, `test_names.py`,
  `test_replies.py` (bind and unbind), `test_command.py`, `test_create.py`, `test_delete.py`,
  `test_forget.py` and `test_check.py`; `conftest.py` loads the plugin and records Discord's REST
  requests by patching `discord.http.HTTPClient.request` (IntervalPusher's pattern).
- `tests/support/discord_fakes.py`: `FakeVoiceChannel` (a `FakeChannel` with a guild, a category,
  `voice_states`, `clone`, `delete` and `set_permissions` that record into `sent` or raise from
  `errors`, and an optional gate that holds `clone`), `FakeGuild.voice_channels` and a
  `voice_state(channel)` helper.
- `tests/fixtures/plugins/dynamic_voice_channel/golden.yaml`: v3's embeds per locale, the en-US
  `unbind-fail` corrected, and the translated command payload.

### v3 behaved differently

- v3 behaved differently: `/dynamic-voice-channel bind` and `unbind` never ran, because the command
  filter compared the top-level name with the full subcommand names (since `ea14fbf`), and the
  response stayed "thinking"; both subcommands answer.
- v3 behaved differently: the `channel` option offered every channel type, and anything but a voice
  channel threw before an answer; it offers voice channels only.
- v3 behaved differently: replies used `Placeholder.get(event)`, which threw outside text channels;
  the replies work everywhere.
- v3 behaved differently: `bind` appended a duplicate entry, the last one winning until a restart
  and the first one after; a bind replaces the binding of the same category and name.
- v3 behaved differently: the lobby was tracked as a room before the copy existed, so a refused copy
  (permissions, channel limits) got the lobby itself deleted when it emptied, and its binding
  dropped at the next start; the room is tracked once the copy exists, and a refused copy leaves the
  lobby as it was, with a warning.
- v3 behaved differently: the tracker was written to MongoDB asynchronously while leaves read
  MongoDB, so a member who left a new room quickly left an orphan room; a guild's voice changes are
  handled one after another, and a leave sees the room that the join created.
- v3 behaved differently: rooms that emptied while the bot was away were never deleted, and the
  tracker kept deleted channels forever; at READY, empty rooms are deleted and missing ones
  forgotten.
- v3 behaved differently: a failed step of the creation skipped the following ones, an unusable
  name (blank or over 100 characters) also skipped the move and the member's permissions, and a
  missing Manage Permissions also skipped the rename; each step runs and logs its own failure, and
  an unusable name only keeps the room's old name.
- v3 behaved differently: a failed deletion still untracked the room, which then stayed forever; it
  stays tracked and is tried again.
- v3 behaved differently: an empty room was deleted on the leave event even when someone joined it
  right after; emptiness is checked right before the deletion.
- v3 behaved differently: a stage channel with a lobby's name threw and stopped the handling of that
  voice update, its leave part included; stage channels are not lobbies.
- v3 behaved differently: a tracked room that kept the lobby's name could be copied again as a
  lobby; tracked rooms are never lobbies.
- v3 behaved differently: placeholders in display names were expanded again, and a self-reference
  stopped the rename; names are inserted as written.
- v3 behaved differently: `dvc@custom_name` and other plugins' keys stayed in the member's shared
  placeholders; each name renders with its own values.
- v3 behaved differently: deleting the file of a guild the bot had left threw inside the loop over
  the files, which left the bindings of the following guilds unloaded until the next restart;
  every left guild's data is deleted.
- v3 behaved differently: a guild unavailable at startup counted as left, so its bindings were
  deleted; unavailable guilds keep their data.
- v3 behaved differently: leaving a guild kept its bindings in memory (a wrong predicate) and its
  rooms in MongoDB; both are deleted.
- v3 behaved differently: the copy of a lobby lost its NSFW flag, video quality and slowmode; the
  copy keeps them.
- v3 behaved differently: the plugin did not load without SQLiteAPI, which it never used; it has no
  dependency.
- v3 behaved differently: an unreadable binding file was replaced by `[]`, losing the guild's
  bindings; an unreadable document stops the handling with an error and is never overwritten.
- v3 behaved differently: the commands needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers them.
- v3 behaved differently: the en-US `unbind-fail` title said "is not be found"; it says "was not
  found".

Kept on purpose: lobbies keyed by (category, exact case-sensitive name), and any voice channel with
that name in that category is a lobby; the joined channel becomes the room and the copy the new
lobby; raw positions 0 and 1; Manage Channels and Manage Permissions for the member on top of the
lobby's overwrites; `%dvc@custom_name%` cut at the first ` - `; rooms only when the member is alone
(a second member who joins at once shares the first one's room); `format-name-2` required, stored
and unused; bindings matched by the channel's current name on `unbind`; bots getting rooms; no
server-side permission check; every reply ephemeral; no log line for created or deleted rooms.

### Inventory audit

Every section of `docs/porting/analysis/inventory/DynamicVoiceChannel.md` maps to this change:

- Overview (1): the entry object, `info.yaml` and the name are "The plugin installs as
  DynamicVoiceChannel" ("Discovered by name"); `depend_plugins: SQLiteAPI` is gone (a "v3 behaved
  differently" entry); `GUILD_VOICE_STATES`, `VOICE_STATE` and `VOICE` are `INTENTS` and
  discord.py's defaults (Package); the unused derived component prefix has no counterpart; the
  terminology (binding, lobby, room) is the spec's.
- Lifecycle (2): exporting the lang files is "First load creates the lang files"; `enabled` is the
  core's `plugins` list; the localizer is the Translator; `reload()` is the core's reload; the lazy
  MongoDB and `JsonManager` initializers are replaced by reads of the store; the startup validation
  (left guild, missing category, missing lobby, rewrite) is "Left while offline" and "Stale
  bindings", its `ConcurrentModificationException` and the unavailable guild are "v3 behaved
  differently" entries; the missing room reconciliation is "Rooms after a restart"; no background
  jobs; the in-memory state is the store's documents.
- Slash commands (3): the group, its subcommands, options, localizations (en-US `name-format-1`
  included) and the Administrator default are "Command payload"; the routing defect is a "v3
  behaved differently" entry and "Command callbacks"; `bind`'s cast, category check, append and
  reply are "Bind", "Bind outside a category" and "Binding again"; `unbind`'s removal and its
  inverted flag are "Unbind" and "Unbind outside a category"; replies in the user's locale with
  `Placeholder.get(event)` are the golden embeds; no server-side permission check: kept.
- Components (4): none.
- Events (5): the slash command is the tree; `GuildLeaveEvent` is "The bot leaves" (bindings and
  rooms; the wrong predicate is a "v3 behaved differently" entry); `GuildVoiceUpdateEvent` on
  channel changes only is "Same channel"; the algorithm is "First join", "Not alone", "Not a lobby",
  "Last member leaves", "Someone stays" and "Untracked channel"; `asVoiceChannel` on a stage channel
  is "Not a lobby"; `createCopy` and the PATCHes are "First join" (with the copied fields and the
  owner bits in Rooms); the name template is "Room names follow format 1"; `formatName2` unused and
  the sample's non-existent keys: kept and out of scope. Races: 1 is "Leaving during the creation";
  2 is "Copy refused"; 3 is "Unusable name" and "Later step refused"; 4 is the emptiness check
  before the deletion ("Someone stays"); 5 is kept (a second member shares the room); 6 is kept for
  manual channels and "Not a lobby" for tracked rooms; 7 is gone (the store is read off the event
  loop's thread); 8 is gone (the store's writes are awaited, and `Bot.close` unloads plugins before
  it closes the store).
- Configuration (6): `enabled` only, so no `config.yaml` ("First load creates the lang files").
- Localization and templates (7): en-US and zh-TW with the zh-TW default are `DEFAULT_LOCALE` and
  the bundled files; the four templates per locale are the golden embeds, with the en-US
  `unbind-fail` correction; the channel-name placeholders are "Room names follow format 1".
- Persistence (8): the binding files are "Bindings are kept per guild in v3's documents" (shape,
  Moshi defaults, duplicates, corrupt files); the MongoDB tracker is "Rooms are tracked per guild";
  the owner ID is kept and not read; no TTL, and stale documents are "Rooms after a restart"; the
  migration of both is out of scope (B11).
- External dependencies (9): MongoDB and SQLiteAPI are gone; no HTTP, no credentials.
- Discord requirements (10): the intent is "Discovered by name"; Manage Channels and Manage Roles
  are in the smoke checklist, and refusals are "Copy refused", "Later step refused" and "Deletion
  refused"; the requests per room are "First join" and "Last member leaves".
- Concurrency (11): the gateway thread's ordering is the snapshot of `voice_states` and the guild's
  voice lock ("Gone before the plugin saw it", "Leaving during the creation"); the async REST chain
  is awaited step by step; `MemoryCacheDb`'s unordered writes and `JsonManager`'s locks are the
  store's data lock; the shared substitutor is per-render values.
- Bugs (12): 1 is "Command callbacks"; 2 is "Copy refused"; 3 is "Leaving during the creation";
  4 is "Rooms after a restart"; 5 is "Left while offline"; 6 is "The bot leaves"; 7 is "Binding
  again"; 8 is "Command payload" (voice channels only); 9 is "Bind" and "Unbind" through the core's
  `interaction_values`; 10 is "Typed text stays" and per-render values; 11 is "Discovered by name".
  The behavior to preserve is "Kept on purpose" and the scenarios above.
- Testability (13): `find_binding` is `find`; `format_room_name` is `room_name`; the decision table
  is split between the listener's snapshot and the creation and deletion handlers, tested through
  `on_voice_state_update`; the binding repository and the tracker semantics are `store.py`; the
  Discord doubles are `FakeVoiceChannel`, the REST recorder and the shared fakes.
- Assessment (14): the listener, `clone` and `set_permissions` are as suggested; the positions use
  raw PATCHes instead of `edit(position=...)` (Rooms); the tracker is the store with awaited writes,
  not aiosqlite or Motor; the per-guild lock and the reconciliation at READY are as suggested,
  without a periodic sweep; the group is built from the Lang instead of decorators, with a voice
  channel transformer instead of a `discord.VoiceChannel` annotation (which needs the cache).

## Risks / Trade-offs

- The raw position PATCHes go through discord.py's undocumented `HTTPClient.request` and `Route`,
  as IntervalPusher's REST ping does; a discord.py upgrade must keep them working (the tests record
  the requests there).
- Two members who join an empty lobby so close together that discord.py parses both voice updates
  before the first listener runs find the lobby with two members, and neither gets a room: they stay
  in the lobby, as a shared channel, until it empties. JDA handled each event before the next one.
- A guild's voice changes wait for each other: while Discord rate-limits a room's creation, the
  guild's other joins and leaves are handled later.
- A restart between the copy and the tracking (step 1 and 2) leaves two lobbies; an administrator
  deletes one.
- Rooms that v3 created are tracked only in v3's MongoDB: xincord never deletes them. At the switch
  they must be deleted by hand, or the deferred migration must look up each room's guild, which v3's
  documents do not hold.
- An unavailable guild is checked again only at the next READY; empty rooms there wait until a
  member leaves them.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [DynamicVoiceChannel]` in `config.yaml`, a category
with a voice channel `Lobby`, a voice channel outside any category, and two accounts (an
administrator and a member). The bot needs Manage Channels and Manage Roles, or Administrator.

1. Start the bot: the log lists `DynamicVoiceChannel` as loaded, and the ten files exist under
   `plugins/DynamicVoiceChannel/lang/`; no `config.yaml` is written there.
2. As the member, the command list does not show `dynamic-voice-channel`. As the administrator, the
   `channel` option of `bind` lists voice channels only.
3. Run `/dynamic-voice-channel bind channel:Lobby format-name-1:"| %dvc@custom_name%"
   format-name-2:x`: an ephemeral green `Bind success`. Bind the channel outside any category: a
   red `The channel must be under the category`.
4. As the member (display name `Bob - Gaming`), join `Lobby`: a new `Lobby` appears at the top of
   the category, the joined channel is renamed `| Bob` right below it, and the member can edit the
   room's name and permissions.
5. As the administrator, join the new `Lobby`: a second room. Join the member's room instead: no
   new room.
6. Leave the rooms: each is deleted when its last member leaves; the lobby stays.
7. Join `Lobby`, stop the bot, leave the room, start the bot: the empty room is deleted once the
   bot is ready.
8. Run `unbind channel:Lobby`: `Unbind success`; again: `Unbind fail, the channel was not found in
   settings`; joining `Lobby` creates no room.
9. Switch the administrator's client to zh-TW: the replies and the command names are v3's zh-TW
   ones.
10. Bind `Lobby` again, take Manage Roles away from the bot (keep Manage Channels), and join
    `Lobby`: the room is created, renamed and moved, and the log warns that the member's permissions
    were refused. Give the permission back.
11. Kick the bot and invite it again: its bindings are gone (the log names the guild).

## User-visible changes

Copy: the en-US `unbind-fail` title says "was not found" instead of "is not be found" (bundled
files only; existing `plugins/DynamicVoiceChannel/lang/` files keep v3's text).

1. `/dynamic-voice-channel bind` and `unbind` answer and change the bindings (v3: "thinking"
   forever since 2026-01-13, so bindings could only be added by editing files).
2. The `channel` option lists voice channels only.
3. Binding a lobby again replaces its formats instead of adding a duplicate.
4. A lobby whose copy Discord refuses stays a lobby (v3 deleted it once it emptied), and the log
   says why.
5. A member who leaves a new room at once no longer leaves an orphan room behind.
6. Rooms that emptied while the bot was offline are deleted when it is ready.
7. A refused step of the creation no longer skips the others; an unusable name (blank or over 100
   characters) keeps the room's old name but still moves it and gives the member their permissions,
   with a warning.
8. The copy keeps the lobby's NSFW flag, video quality and slowmode.
9. Leaving a guild deletes its rooms' records too, and an unavailable guild keeps its bindings.
10. Stage channels named like a lobby are ignored (v3 threw).
11. v3's bindings and its MongoDB rooms are not read: bindings must be made again until the deferred
    migration, and v3's leftover rooms are not deleted.
12. No `plugins/DynamicVoiceChannel/config.yaml`: v3's only key, `enabled`, is the core's `plugins`
    list.
