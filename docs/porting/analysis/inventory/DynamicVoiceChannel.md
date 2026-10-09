# DynamicVoiceChannel — porting inventory (branch `main` @ 3a59607)

Citation prefixes used below:
- `DV/` = `Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/`
- `DVR/` = `Plugins/DynamicVoiceChannel/src/main/resources/`
- `Core/` = `Core/src/main/kotlin/core/`

**[verified]** = checked against JDA 6.4.1 bytecode / Kotlin stdlib behavior in a scratch sandbox.
**[unverified]** = depends on Discord server behavior I could not observe.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/DynamicVoiceChannel` |
| Kotlin files / LOC | 7 files / 539 LOC (`JsonManager.kt` 144, `DynamicVoiceChannel.kt` 136, `command/Register.kt` 90, `Event.kt` 79, `command/CmdFileSerializer.kt` 53, `json/JsonData.kt` 29, `config/ConfigSerializer.kt` 8) |
| Resource files | 12: `info.yaml`, `config.yaml`, 5 lang files per locale × 2 (`en-US`, `zh-TW`) |
| Gradle | `build.gradle.kts`: plugin `xs-plugin` only (no SQLiteAPI compile dependency); `gradle.properties`: `version.patch=0` → `3.4.0-SNAPSHOT` |
| Purpose | "Lobby" voice channels: when a member joins an **empty** bound lobby, that lobby channel becomes the member's room (renamed from a template, moved to position 1, owner gets Manage Channel + Manage Permissions) and a fresh copy of the lobby is created at position 0. Rooms created this way are tracked in MongoDB and deleted when they become empty. |
| Entry object | `internal object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`DV/Event.kt:21`; KDoc wrongly says "Economy plugin"), main class `tw.xinshou.discord.plugin.dynamicvoicechannel.Event` |
| Listener flag | `true` |

`info.yaml` (`DVR/info.yaml`), all fields:

```yaml
author: ${author}          # "xinshoutw"
name: ${name}              # "DynamicVoiceChannel"
coreApi: ${coreApi}        # "3.4"
version: ${version}        # "3.4.0-SNAPSHOT"
main: "tw.xinshou.discord.plugin.dynamicvoicechannel.Event"
depend_plugins: ["SQLiteAPI"]          # hard dependency, but SQLite is never used
require_intents: ["GUILD_VOICE_STATES"]
require_cache_flags: ["VOICE_STATE"]
require_member_cache_policies: ["VOICE"]
# component_prefix not set → Core derives "dynamicvoicechannel@" and logs a "name too long" warning
# (Core/base/PluginLoader.kt:277-285); the plugin has no components.
```

Terminology: **binding** = (category ID, lobby name, format strings); **lobby** = any voice channel in the bound category whose name equals the binding's `defaultName` exactly; **room** = a channel converted by the plugin and tracked in MongoDB.

---

## 2. Lifecycle

- `load()` (`DV/Event.kt:24-37`): Core exports `lang/` (no overwrite) and reads `config.yaml` (kaml strict). If `enabled == false` → `warn "DynamicVoiceChannel is disabled."` and return. Else build `localizer` (`register.yaml`, default zh-TW).
- `unload()`: not overridden (Core default log line).
- `reload()` (`DV/Event.kt:39-54`): re-read config; if disabled → return; else rebuild localizer and `DynamicVoiceChannel.reload()` (new `MessageCreator`; this also forces the object's initializer, i.e. MongoDB access).
- Lazy initializers:
  - `DynamicVoiceChannel` object (`DV/DynamicVoiceChannel.kt:19-33`): `CacheDbManager(Event.pluginName)` → MongoDB database `DynamicVoiceChannel`; `generatedCache = getCollection("generated_cache", memoryCache = true)` → `MemoryCacheDb`, which loads every document into a `ConcurrentHashMap` at construction (`Core/mongodb/MemoryCacheDb.kt:25-46`); `MessageCreator(pluginDirectory, zh-TW)` without a component manager. Requires Core's embedded MongoDB to be running (Core starts it before the bot, `Core/Main.kt:24`).
  - `JsonManager` object (`DV/JsonManager.kt:30-87`), first touched by the first voice update whose joined channel has exactly one member (`getData`) or by a guild leave: loads `plugins/DynamicVoiceChannel/data/<guildId>.json` and validates each binding inside a `try/catch(Exception)`:
    1. bot not in the guild → `removeAndSave(guildId)` (deletes the file) inside a destructured `forEach` → `ConcurrentModificationException` unless it was the last guild [verified pattern]; the exception is caught and logged ("Initialization failed"), leaving bindings of later guilds **unloaded** until the next restart (the file is gone then, so the next start is clean);
    2. drop the binding if the category no longer exists;
    3. drop the binding if no voice channel named exactly `defaultName` (case-sensitive, `getVoiceChannelsByName(name, false)`) exists under that category;
    4. rewrite the guild file with the surviving bindings; add survivors to `dataSet` (set semantics by `(categoryId, defaultName)`: if the file holds duplicates, the **first** one wins).
    Logs `[JsonManager] Initialization complete. Loaded N valid data entries.`
- Background jobs: none scheduled. Every tracker write/delete launches a fire-and-forget coroutine on Core's `CacheDbServer.dbScope` (`Dispatchers.IO + SupervisorJob`) (`Core/mongodb/MemoryCacheDb.kt:64-94`).
- Startup cleanup: only the binding validation above. **No reconciliation of rooms**: rooms that became empty while the bot was offline are not deleted, and tracker documents for channels that no longer exist are never removed.
- In-memory state: `JsonManager.dataSet` (`ConcurrentHashMap.newKeySet<DataContainer>()`), `generatedCache` mirror (`ConcurrentHashMap<String, Any>` channelId → owner user ID), `messageCreator`, `localizer`.

---

## 3. Slash commands & context menus

One guild command with two subcommands, registered only when `enabled == true` (`DV/Event.kt:56-62`). **On main both subcommands are unreachable** (see the routing defect below).

Definition (`DV/command/Register.kt:44-89`):

| Field | Value |
|---|---|
| Command | `dynamic-voice-channel` / `commands about dynamic voice channel`; default_member_permissions `ADMINISTRATOR`; guild command |
| `bind` | `bind a voice channel`; options: `channel` (CHANNEL, required, desc `voice channel to bind`, **no channel_types restriction**), `format-name-1` (STRING, required, `format name 1`), `format-name-2` (STRING, required, `format name 2`); no choices/min/max/autocomplete |
| `unbind` | `unbind a voice channel`; option `channel` (CHANNEL, required, `voice channel to unbind`) |
| Name localizations | en-US: `dynamic-voice-channel`, `bind`, `channel`, **`name-format-1`**, **`name-format-2`**, `unbind`; zh-TW: `動態語音頻道`, `綁定`, `頻道`, `名稱格式1`, `名稱格式2`, `解綁` |
| Description localizations | en-US: `Dynamic Voice Channel`, `Bind a voice channel`, `Voice channel`, `Name format 1`, `Name format 2`, `Unbind a voice channel`, `Voice channel`; zh-TW: `動態語音頻道`, `綁定語音頻道`, `語音頻道`, `名稱格式1`, `名稱格式2`, `解綁語音頻道`, `語音頻道` |
| Localization keys | Kotlin property paths: `dynamicvc.name`, `dynamicvc.subcommands.bind.options.formatName1.name`, … (YAML root `dynamic-voice-channel`, YAML option keys `format-name-1`/`format-name-2`) |

Note: the en-US localized option names (`name-format-1/2`) differ from the base names (`format-name-1/2`).

### Routing defect (current observable behavior)
`Event.onSlashCommandInteraction` returns early when `GlobalUtil.checkSlashCommand(event, commandStringSet)` is true (`DV/Event.kt:64-68`). `checkSlashCommand` tests `event.name !in set` (`Core/util/GlobalUtil.kt:49-50`); `event.name` is the top-level name `dynamic-voice-channel`, while the set contains `dynamic-voice-channel bind` / `dynamic-voice-channel unbind` (`DV/command/Register.kt:39-42`). The check is therefore always true → the handler never runs. Introduced in commit `ea14fbf` (2026-01-13), which turned a previously ignored call into `if (...) return`. Observable result on main: Core's auto-defer shows an ephemeral "thinking…" that is never completed; nothing is saved. Bindings can only be created by editing the JSON file by hand.

### Intended behavior (handler code, `DV/DynamicVoiceChannel.kt:35-89`), for the port
Both subcommands rely on Core's ephemeral auto-defer and answer with `hook.editOriginal(<template rendered in event.userLocale>)`; `Placeholder.get(event)` is evaluated for the reply, which throws outside plain TextChannels (`Core/builtin/placeholder/Placeholder.kt:75`).

`bind`:
1. `channel` option cast to `VoiceChannel` (non-voice channel → `ClassCastException`, no reply).
2. If the channel has no parent category → reply `must-under-category`.
3. Else `JsonManager.addData(guildId, DataContainer(category.id, channel.name, fmt1, fmt2))`: append to the guild JSON list **without removing an existing entry for the same (category, name)**; in memory, replace the matching binding (`DV/JsonManager.kt:89-102`). Log `Added DynamicVoiceChannel binding for guild <id> → <name>`.
4. Reply `bind-success`.

`unbind`:
1. Same cast and category check (`must-under-category`).
2. `removeData(guildId, categoryId, channel.name)`: remove from memory unconditionally; remove all matching entries from the JSON list; returns `true` when nothing was removed from JSON (`DV/JsonManager.kt:104-128`).
3. Reply `unbind-fail` if nothing was removed, else `unbind-success`. Matching uses the channel's **current** name, so the user must pick a channel that still carries the lobby name.

No server-side permission checks.

---

## 4. Components

None (no buttons, selects or modals). Derived component prefix `dynamicvoicechannel@` is unused.

---

## 5. Events

All handlers return early when `enabled == false`.

| JDA event | Behavior |
|---|---|
| `SlashCommandInteractionEvent` | dead routing (§3) |
| `GuildLeaveEvent` (`DV/Event.kt:70-73`) | `JsonManager.removeGuild(guildId)`: delete `data/<guildId>.json`; remove in-memory bindings with `categoryId.toString().startsWith(guildId.toString())` — wrong predicate, so in practice nothing is removed from memory (`DV/JsonManager.kt:130-136`). Tracker documents are not touched. |
| `GuildVoiceUpdateEvent` (`DV/Event.kt:75-78`) | join/leave/move only (JDA does not fire it for mute/deafen/stream); algorithm below |

Voice update algorithm (`DV/DynamicVoiceChannel.kt:94-110`), executed on the gateway thread:

```
joined = event.channelJoined; left = event.channelLeft
if joined != null and joined.members.size == 1:              # the joiner is alone (bots count)
    b = bindings.first(categoryId == joined.parentCategoryIdLong and defaultName == joined.name)
    if b: firstJoin(member, joined.asVoiceChannel(), b)       # asVoiceChannel throws for a stage channel
if left != null and left.members.isEmpty():
    if tracker.containsKey(left.id):                          # synchronous MongoDB query, not the memory mirror
        left.delete().queue()
        tracker.remove(left.id)                               # memory now, MongoDB async
```

`firstJoin` (`DV/DynamicVoiceChannel.kt:112-135`):

```
lobby.createCopy()                        # POST; copies name, bitrate, user limit, RTC region, parent category,
                                          # all role AND member overwrites [verified JDA VoiceChannelMixin.createCopy];
                                          # not copied: position, NSFW, video quality, status
  .flatMap { copy -> copy.manager.setPosition(0) }                   # PATCH copy
  .flatMap { lobby.manager                                           # one PATCH on the joined channel
               .setPosition(1)
               .setName(format(b.formatName1))
               .putMemberPermissionOverride(member.id,
                    allow = [MANAGE_CHANNEL, MANAGE_PERMISSIONS], deny = []) }   # bits 4 and 28 [verified]
  .queue()
tracker.put(lobby.id, member.id)           # immediately, before any REST call has completed
```

Creation rule summary: a member joins (or moves into) a voice channel that ends up with exactly one member, whose parent category matches a binding and whose name equals that binding's `defaultName` exactly. The **joined channel becomes the room** (the member is not moved); the **copy becomes the new lobby**. Existing overwrites stay on the room; the owner override is added on top.

Deletion rule summary: a member leaves (or moves out of) a channel that is then empty and whose ID is in MongoDB `generated_cache` → delete it and untrack. Untracked channels are never deleted.

Name template (`DV/DynamicVoiceChannel.kt:119-123`): `Placeholder.get(member)` plus `dvc@custom_name` = `member.effectiveName.split(" - ").first()` (nickname, else global name, else username, cut at the first `" - "`), then substitution of `formatName1`. JDA `setName` then requires non-blank, trims, and requires ≤ 100 chars [verified]; violations throw inside the chain, so position, name and owner override are all skipped while the copy already exists. Available placeholders: `%dvc@custom_name%`, `%user_id%`, `%user_mention%`, `%user_name%`, `%user_avatar_url%`, `%member_display_name%`, `%member_avatar_url%`, `%member_fixed_name%`, `%bot_id%`, `%bot_name%` (plus stale `cl_*`/`vl_*` keys other plugins left on the shared per-member substitutor). Substitution is recursive (a display name containing `%…%` is expanded; a self-reference throws). `formatName2` is stored but never used. The sample in `DV/JsonManager.kt:18-27` uses `%dvc@custom-name%` and `%dvc@info%`, neither of which exists.

Race conditions and failure modes:
1. **Write-behind vs synchronous read**: `put` updates memory and writes MongoDB asynchronously, but `containsKey` queries MongoDB directly (`MemoryCacheDb` does not override `contains`/`containsKey`, `Core/mongodb/CacheCollectionManager.kt:91-97`). A member who joins an empty lobby and leaves before the async upsert lands leaves behind an **orphan room** (renamed, tracked later, deleted only after someone else joins and leaves it).
2. **Tracking before success**: if `createCopy` fails (missing permission, 500-channel or 50-per-category cap, rate limit), no copy and no rename happen, but the lobby itself is already tracked → when it empties, the **lobby is deleted**; at the next restart the binding is dropped because no channel with the lobby name exists.
3. Rename failure (name blank/>100/placeholder cycle) → two channels with the lobby name; the tracked original is deleted when empty (self-heals).
4. Delete racing the rename: room emptied quickly → delete queued; the pending rename then fails with Unknown Channel (logged).
5. Two members joining the same empty lobby back to back: JDA updates the voice cache per event, so only the first sees `size == 1`; both end up in the first member's room.
6. A rendered room name equal to `defaultName` makes the room a lobby again; any manually created channel with the lobby name in the bound category is also a lobby.
7. Every empty-channel leave performs a blocking MongoDB round-trip on the gateway thread.
8. Core closes MongoDB before plugins unload (`Core/Main.kt:31-33`), so in-flight async writes can be lost at shutdown.

---

## 6. Configuration (`plugins/DynamicVoiceChannel/config.yaml`, `DV/config/ConfigSerializer.kt:5-8`)

| Key | Type | Default (code / shipped) | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` / `false` | false → command not registered, all handlers return early, localizer not built, MongoDB not touched. Runtime toggle via dashboard (`reload()` + command refresh). |

Strict kaml decoding.

---

## 7. Localization & templates

Locales `en-US`, `zh-TW`; default zh-TW. Files per locale: `register.yaml`, `message/bind-success.yaml`, `message/must-under-category.yaml`, `message/unbind-fail.yaml`, `message/unbind-success.yaml`.

- `register.yaml` → all command name/description localizations (§3). There is no `placeholder.yaml`.
- Message templates (legacy v1 schema, rendered by Core v2 `MessageCreator`, one embed with a title and color, no placeholders), selected by `event.userLocale` with zh-TW fallback:

| Key | en-US title | zh-TW title | Color |
|---|---|---|---|
| `bind-success` | `Bind success` | `綁定成功` | `#00FF00` |
| `must-under-category` | `The channel must be under the category` | `語音頻道必須在類別(Category)下` | `#FF0000` |
| `unbind-fail` | `Unbind fail, the channel is not be found in settings` | `取消綁定失敗，找不到設定記錄` | `#FF0000` |
| `unbind-success` | `Unbind success` | `取消綁定成功` | `#00FF00` |

- Channel-name placeholders: §5 (`%dvc@custom_name%` and Core member placeholders).

---

## 8. Persistence

### 8.1 Bindings — JSON
- File: `plugins/DynamicVoiceChannel/data/<guildId>.json` (`DV/JsonManager.kt:36-40`).
- Schema: JSON array of objects with Moshi/Kotlin property names (`DV/json/JsonData.kt:3-29`):
  `{"categoryId": long, "defaultName": string, "formatName1": string = "", "formatName2": string = ""}`.
  Identity/equality = `(categoryId, defaultName)` only.
- Example: `[{"categoryId":1290000000000000300,"defaultName":"《🔊》新語音頻道","formatName1":"｜%dvc@custom_name%","formatName2":""}]`
- Duplicates are possible (bind appends); after restart the first duplicate wins, at runtime the last bind wins.
- Corrupt JSON → replaced with `[]` by Core (logged). A non-numeric file name breaks `JsonGuildFileManager` construction, which happens outside the try/catch → `JsonManager` init fails.

### 8.2 Room tracker — MongoDB (Core embedded server)
- Server: flapdoodle embedded MongoDB 8.2 started by Core; data dir `./mongodb-data` (or `mongodb-data-<XS_MONGODB_INSTANCE>`, or `XS_MONGODB_DB_PATH`); port random (or `XS_MONGODB_PORT`) (`Core/mongodb/CacheDbServer.kt:38-42,128,155-186`).
- Database `DynamicVoiceChannel` (= plugin name), collection `generated_cache`, accessed via `MemoryCacheDb` (memory mirror loaded at init, async write-through; `containsKey` reads MongoDB directly).
- Document (`Core/mongodb/CacheCollectionManager.kt:31-38`): `{ "_id": "<roomChannelId>", "value": NumberLong(<ownerUserId>), "timestamp": NumberLong(<epoch ms of write>) }`.
- The owner ID is never read back. No TTL; documents for deleted channels persist forever.

Migration: bindings JSON is trivially readable; the tracker is tiny and can be migrated from MongoDB (`_id` string, `value` int64) to SQLite/JSON if the port drops MongoDB. A startup reconciliation step is needed either way.

---

## 9. External dependencies

- Core embedded MongoDB (`CacheDbManager`/`MemoryCacheDb`, Core depends on the MongoDB sync driver and flapdoodle).
- Declared hard dependency `SQLiteAPI` (info.yaml) is unused; it only prevents loading when SQLiteAPI is absent.
- No HTTP endpoints, no credentials, no soft dependencies, no extra Gradle dependencies.

---

## 10. Discord requirements

- Intents: `GUILD_VOICE_STATES`; cache flag `VOICE_STATE` (needed for `members` counts and `channelLeft`); member cache `VOICE`.
- Bot permissions (not checked in code): Manage Channels (create/edit/move/delete), Manage Roles a.k.a. Manage Permissions (write overwrites). Discord only lets a bot write overwrite bits it holds itself (copied lobby overwrites and the granted Manage Channels/Manage Permissions), so in practice Administrator is the reliable setup.
- Rate-limit-sensitive: each room creation = 1 POST + 2 PATCH; each room removal = 1 DELETE; join/leave churn produces channel create/delete churn. Each channel is renamed once, so Discord's per-channel rename limit is rarely hit. Guild/category channel caps make `createCopy` fail (see race 2).

---

## 11. Concurrency

- Gateway events are processed sequentially on JDA's WebSocket thread; the member-count check is consistent with JDA's cache at dispatch time.
- REST chains (`createCopy → setPosition → manager PATCH`) run asynchronously; the tracker update is synchronous and precedes them.
- `MemoryCacheDb`: `ConcurrentHashMap` mirror; MongoDB writes on IO coroutines with no ordering guarantee between a `put` and a later `remove` for the same key; `containsKey` blocks the gateway thread on MongoDB.
- `JsonManager`: `ConcurrentHashMap.newKeySet` + `synchronized` blocks around `dataSet`/file updates.
- The shared Core per-member `Substitutor` is mutated (`dvc@custom_name`) inside a REST callback thread.

---

## 12. Bugs, quirks, dead code, hard-coded values

Probable bugs to fix:
1. Slash commands unreachable since `ea14fbf` (`DV/Event.kt:66` + `Core/util/GlobalUtil.kt:49-50`).
2. Lobby tracked before REST success → lobby deleted after a failed copy (`DV/DynamicVoiceChannel.kt:114-134`).
3. Async tracker write vs synchronous MongoDB read → orphan rooms on fast join/leave (`DV/DynamicVoiceChannel.kt:105`, `Core/mongodb/MemoryCacheDb.kt`).
4. No startup reconciliation of rooms; stale tracker documents.
5. `JsonManager` init CME on a stale guild file (caught, partial load) (`DV/JsonManager.kt:48-55`).
6. `removeGuild` in-memory predicate (`DV/JsonManager.kt:133`).
7. `addData` appends duplicates; restart vs runtime pick different duplicates (`DV/JsonManager.kt:91-99`).
8. `channel` option lacks `channel_types=[voice]`; cast throws for other types (`DV/command/Register.kt:54`, `DV/DynamicVoiceChannel.kt:38,59`).
9. Replies use `Placeholder.get(event)` → fail outside plain TextChannels.
10. Placeholder injection through member display names; shared per-member substitutor leaks keys across plugins.
11. Unneeded `SQLiteAPI` dependency.

Behavior to preserve (or confirm with the user):
- Joined lobby becomes the room; a copy becomes the new lobby at position 0; room at position 1 (raw positions; ties are ordered by Discord by ID).
- Owner gets Manage Channel + Manage Permissions on the room; lobby overwrites are copied to the new lobby and kept on the room.
- `%dvc@custom_name%` = effective name cut at the first `" - "`.
- Rooms are deleted only when empty and tracked; bots also get rooms.
- Bindings keyed by (category ID, exact case-sensitive lobby name); lobby must be inside a category.
- `unbind-fail` when no stored binding matched.

Dead code / unused: `formatName2`; `generatedCache` value (owner ID); component prefix; `logger` in `DynamicVoiceChannel` object unused; `DataContainer` sample comment. No TODO/FIXME.

Hard-coded: default locale zh-TW; separator `" - "`; positions 0/1; granted permissions; collection name `generated_cache`.

---

## 13. Testability

Pure logic to extract:
- `find_binding(bindings, category_id, channel_name) -> Binding | None`.
- `format_room_name(template, display_name, extra_vars) -> str` (split on `" - "`, substitution, trim, blank/100-char validation).
- `plan_voice_update(joined, left, joined_count_after, left_count_after, bindings, tracked_ids) -> [CreateRoom(...), DeleteRoom(...)]` — the whole decision table without I/O.
- Binding repository: add-or-replace (fix duplicates), remove → found flag, startup validation (guild/category/lobby existence).
- Tracker semantics: track only after success, untrack on delete, reconcile on startup (`tracked ∩ existing`, delete empty ones).

Needs Discord doubles: voice state cache (member counts per channel), channel clone/edit/delete with injectable failures (403, 404, 429, caps), guild leave, slash command invocation with channel options; a tracker store double (Mongo/SQLite).

---

## 14. Porting assessment — Medium

Reasons: small code, but correctness depends on ordering of async REST calls and persistent tracking; the current main has a dead command path and several race/failure modes that must be designed out rather than copied; MongoDB dependency needs a decision.

discord.py mapping:
- Cog listener `on_voice_state_update(member, before, after)`; act only when `before.channel != after.channel`; use `len(after.channel.members) == 1` (requires `Intents.voice_states` and member cache) for the first-join check.
- `new_lobby = await lobby.clone()` (verify that discord.py's `clone` copies the same fields as JDA's `createCopy`: overwrites, category, bitrate, user limit, RTC region), `await new_lobby.edit(position=0)`, `await lobby.edit(name=..., position=1, overwrites={**lobby.overwrites, member: PermissionOverwrite(manage_channels=True, manage_permissions=True)})`; track only after success; `await channel.delete()` on empty.
- Per-guild or per-channel `asyncio.Lock` to serialize create/delete decisions; persist the tracker with awaited writes (aiosqlite, or motor if MongoDB is kept).
- One-shot reconciliation in `on_ready`/`setup_hook` (delete empty tracked rooms, drop missing IDs); optionally a `tasks.loop` sweep.
- `app_commands.Group("dynamic-voice-channel", default_permissions=administrator, guild_only=True)` with `bind(channel: discord.VoiceChannel, format_name_1: str, format_name_2: str)` (rename parameters to `format-name-1` etc. via `@app_commands.rename`) and `unbind(channel: discord.VoiceChannel)`; respond with `defer(ephemeral=True)` + `edit_original_response`.

Risks: race semantics under asyncio; permission errors when copying overwrites; channel caps and rate limits; replacing embedded MongoDB; deciding whether `formatName2` gets a meaning; existing JSON duplicates.
