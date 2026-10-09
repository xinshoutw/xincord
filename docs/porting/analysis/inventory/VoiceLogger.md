# VoiceLogger — porting inventory (branch `main` @ 3a59607)

Citation prefixes used below:
- `VL/` = `Plugins/VoiceLogger/src/main/kotlin/logger/voice/`
- `VLR/` = `Plugins/VoiceLogger/src/main/resources/`
- `Core/` = `Core/src/main/kotlin/core/`

**[verified]** = checked against the same library versions in a scratch sandbox (JDA 6.4.1, commons-text 1.15.0,
Kotlin stdlib, Moshi LinkedHashTreeMap). **[unverified]** = depends on Discord server behavior I could not observe.

VoiceLogger shares ~70% of its code with ChatLogger (copy-paste): `ChannelData.kt`, `JsonManager.kt`,
`json/JsonData.kt`, the settings UI and the component scheme are identical apart from names. The JSON bugs
documented for ChatLogger apply verbatim; they are restated briefly here.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/VoiceLogger` |
| Kotlin files / LOC | 9 files / 835 LOC (`VoiceLogger.kt` 439, `JsonManager.kt` 117, `Event.kt` 110, `ChannelData.kt` 77, `command/Register.kt` 32, `command/CmdFileSerializer.kt` 23, `json/JsonData.kt` 15, `command/PlaceholderSerializer.kt` 14, `config/ConfigSerializer.kt` 8) |
| Resource files | 26: `info.yaml`, `config.yaml`, 12 lang files per locale × 2 (`en-US`, `zh-TW`) |
| Gradle | `build.gradle.kts`: plugin `xs-plugin` only (Core compileOnly); `gradle.properties`: `version.patch=0` → `3.4.0-SNAPSHOT` |
| Purpose | Post an embed to configured "listen" text channels when a member joins / leaves / switches voice channels, and when a voice channel's status text is set / changed / cleared (with the actor taken from the audit log). Admin-only ephemeral settings UI per listen channel (allow/block lists of voice channels/categories). |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`VL/Event.kt:23`; its KDoc wrongly says "Economy plugin"), main class `tw.xinshou.discord.plugin.logger.voice.Event` |
| Listener flag | `true` |

`info.yaml` (`VLR/info.yaml`), all fields:

```yaml
author: ${author}          # "xinshoutw"
name: ${name}              # "VoiceLogger"
coreApi: ${coreApi}        # "3.4"
version: ${version}        # "3.4.0-SNAPSHOT"
main: "tw.xinshou.discord.plugin.logger.voice.Event"
component_prefix: "voice-logger@"
require_intents: ["GUILD_VOICE_STATES"]
require_cache_flags: ["VOICE_STATE"]
require_member_cache_policies: ["VOICE"]
# not set: description, prefix, depend_plugins, soft_depend_plugins, depend_jars, soft_depend_jars
```

Terminology: **listen channel** = channel where `/voice-logger setting` was run = log destination; **detected
channel** = voice channel whose activity is posted to a listen channel.

---

## 2. Lifecycle

- `load()` (`VL/Event.kt:27-48`): Core exports `lang/` (no overwrite) and reads `config.yaml` (kaml strict). If `enabled == false` → `warn "VoiceLogger is disabled."` and return. Else build `registerLocalizer` (`register.yaml`) and `placeholderLocalizer` (`placeholder.yaml`), default locale zh-TW.
- `unload()`: not overridden → Core default (log line only). No cleanup.
- `reload()` (`VL/Event.kt:50-73`): Core re-export + config re-read; if disabled → return; else rebuild localizers and `VoiceLogger.reload()` (new `MessageCreator`). `JsonManager` state is not reloaded.
- Lazy initializers:
  - `VoiceLogger` object (`VL/VoiceLogger.kt:29-49`): `ComponentIdManager(prefix="voice-logger@", {"action": STRING})` and v2 `MessageCreator` (reads `plugins/VoiceLogger/lang/*/message/*.yaml`).
  - `JsonManager` object (`VL/JsonManager.kt:17-58`), first touched by the first voice event / status event / settings interaction: loads `plugins/VoiceLogger/setting/<guildId>.json`, prunes data for guilds the bot left and listen channels that no longer exist, filters allow/block IDs to existing channels, fills `dataMap`. Same `ConcurrentModificationException` defects as ChatLogger: any stale guild file → init fails once (file already deleted); a deleted non-last listen channel → init fails on every restart (file not rewritten) [verified pattern]. A failed init makes every later access throw `NoClassDefFoundError` for the process lifetime → no voice logging at all.
- Background jobs: none. Async work = JDA `RestAction` chains only.
- In-memory state: `JsonManager.dataMap: HashMap<Long, ChannelData>` (listenChannelId → mode/allow/block, all guilds); `messageCreator`; localizers; Core `Placeholder` caches (mutated, see §12).

---

## 3. Slash commands & context menus

One guild command, registered only when `enabled == true` (`VL/Event.kt:75-81`; Core bulk-overwrites guild commands at startup, guild join and plugin reload).

### `/voice-logger setting`
Definition (`VL/command/Register.kt:23-32`):

| Field | Value |
|---|---|
| Name / description (base) | `voice-logger` / `commands about voice logger` |
| Subcommand | `setting` / `set voice log in this channel` |
| Options | none |
| default_member_permissions | `ADMINISTRATOR` |
| Guild-only / NSFW | guild command; NSFW not set |
| Name localizations | en-US `voice-logger` / `setting`; zh-TW `語音紀錄` / `設定` |
| Description localizations | en-US `commands about voice logger` / `set voice log in this channel`; zh-TW `有關語音紀錄的指令` / `設定語音紀錄在此頻道` |
| Localization keys | `voiceLogger.name`, `voiceLogger.description`, `voiceLogger.subcommands.setting.name`, `voiceLogger.subcommands.setting.description` (Kotlin property names; YAML root key is `voice-logger`) |

Behavior (identical to ChatLogger's settings command):
1. Core auto-defers ephemerally (`Core/logger/InteractionLogger.kt:25-30`).
2. Return if disabled or `fullCommandName != "voice-logger setting"` (`VL/Event.kt:83-87`).
3. `dataMap.computeIfAbsent(channelId)` → in-memory default (ALLOW, empty lists), not persisted (`VL/VoiceLogger.kt:51-57`).
4. `Placeholder.get(event)` throws unless the channel is a plain TextChannel (`Core/builtin/placeholder/Placeholder.kt:75`) → the deferred response never completes.
5. `hook.editOriginal(<voice-logger@setting rendered in userLocale>)`.

Rendered settings message: author `Voice Log`/`語音日誌`; title `☛ %channel_name%'s Channel Setting`/`☛ %channel_name% 的頻道設定`; footer `❖ ORDERLY SERVER ❖`; fields `Channel Mode`/`頻道模式` = `<ALLOW>`|`<BLOCK>`, `Allowlist Channels`/`白名單頻道` = list or `Empty`/`無`, `Blocklist Channels`/`黑名單頻道`; list line format ``<#id> (`id`)`` + `\n`; buttons `Toggle Mode`/`切換模式` (PRIMARY), `Modify Allowlist`/`設定白名單` (SUCCESS), `Modify Blocklist`/`設定黑名單` (SECONDARY), `Delete`/`刪除` (DANGER).

---

## 4. Components

Prefix check `voice-logger@` (`VL/Event.kt:89-99`); ID format `voice-logger@a:<action>` (`a` = `action`). All on the ephemeral settings message; no expiry handling.

| custom_id | Type | Behavior |
|---|---|---|
| `voice-logger@a:toggle_btn` | Button PRIMARY | Flip mode in memory; JSON `getOrPut(id){allow_mode=false,[],[]}.allow_mode = mode`; save; `deferEdit` + `hook.editOriginal(settings)` (`VL/VoiceLogger.kt:199-213`). |
| `voice-logger@a:modify_allow_btn` | Button SUCCESS | `editMessage(modify-allow)` (select only) (`:186-196`). |
| `voice-logger@a:modify_block_btn` | Button SECONDARY | `editMessage(modify-block)`. |
| `voice-logger@a:delete_btn` | Button DANGER | `dataMap.remove(listenChannelId)`; **delete the whole guild JSON file**; `editMessage(delete)` (`:215-229`, `VL/JsonManager.kt:107-113`). |
| `voice-logger@a:modify_allow_menu` | EntitySelect CHANNEL, types **VOICE, CATEGORY**, min 1, max 25 | Union into allow list; JSON entry created with `allow_mode=false` if absent; save; `deferEdit` + `editOriginal(settings)` (`:77-115`). |
| `voice-logger@a:modify_block_menu` | same | Union into block list. |

Placeholder text of selects: `choose channels, categories or search here` / `選擇頻道、類別或在此搜尋`. Unknown button action → ignored and unacknowledged; unknown select action → `throw Exception` (`:102`). No removal of individual entries.

---

## 5. Events

All handlers return early when `enabled == false`.

| JDA event | Behavior |
|---|---|
| `SlashCommandInteractionEvent`, `ButtonInteractionEvent`, `EntitySelectInteractionEvent` | §3/§4 |
| `GuildVoiceUpdateEvent` (`VL/Event.kt:106-109`) | Classified by `channelJoined`/`channelLeft` (`VL/VoiceLogger.kt:144-161`) — table below |
| `ChannelUpdateVoiceStatusEvent` (`VL/Event.kt:101-104`) | Actor lookup + classification (`VL/VoiceLogger.kt:117-141`) — table below |

Event → log mapping:

| Change | Condition | Template | Listen channels chosen when | Variables set |
|---|---|---|---|---|
| Join | `left == null`, `joined != null` | `on-channel-join` | `joined ∈ detected` (`:278-297`) | `vl_channel_join_mention`, `vl_channel_join_name`, `vl_channel_join_url`, `vl_category_join_mention` (only if category) |
| Leave | `joined == null` | `on-channel-left` | `left ∈ detected` (`:331-350`) | `vl_channel_left_mention`, `vl_channel_left_name`, `vl_channel_left_url`, `vl_category_left_mention` (if category) |
| Switch/move | both non-null | `on-channel-switch` | `joined ∈ detected OR left ∈ detected` (`:299-329`) | `vl_channel_join_url`, `vl_channel_join_name`, `vl_channel_left_mention`, `vl_channel_left_name`, `vl_channel_left_url`, `vl_category_join_mention`/`vl_category_left_mention` (if category). **`vl_channel_join_mention` is NOT set** although the template uses it. |
| Status set | `old == ""` | `on-status-new` | `channel ∈ detected` (`:163-184`) | `vl_channel_mention`, `vl_channel_url`, `vl_status_after`, `vl_category_mention` (if category) |
| Status changed | `old != ""`, `new != ""` | `on-status-update` | same (`:231-253`) | + `vl_status_before`, `vl_status_after` |
| Status cleared | `new == ""` | `on-status-delete` | same (`:255-276`) | `vl_status_before` (+ mention/url/category) |
| Mute, deafen (self/server), Go Live stream, video, suppress, request-to-speak | — | **not handled** | — | — |

Member placeholders (`%user_mention%`, `%member_avatar_url%`, …) come from `Placeholder.get(member)`: for voice updates the member whose state changed (a moderator's disconnect/move is attributed to the moved member; bots are logged too); for status updates the audit-log actor (below).

`GuildVoiceUpdateEvent` fires only when the member's channel changes; JDA emits separate events for self/guild mute, self/guild deafen, suppress, stream, video and request-to-speak, none of which this plugin handles [verified in JDA `VoiceStateUpdateHandler`]. JDA needs the VOICE_STATE cache to report `channelLeft`; Core disables that cache unless a plugin requests it, which this plugin does.

Status-change flow details (`VL/VoiceLogger.kt:117-141`):
1. JDA fires the event only when the new `status` differs from its cached value; both values are non-null strings, `""` meaning "no status" [verified in JDA `VoiceChannelStatusUpdateHandler`: `getString("status", "")`].
2. `event.channel.asVoiceChannel()`; `guild.retrieveAuditLogs().limit(1).type(VOICE_CHANNEL_STATUS_UPDATE)` → `it[0]` → `retrieveMemberById(entry.userIdLong)` → classify (`new == ""` → delete; else `old == ""` → new; else update) → render/send. All of it runs inside REST callbacks.
3. Attribution defects: always uses action type 192 (`VOICE_CHANNEL_STATUS_UPDATE`); clearing a status is logged by Discord as 193 (`VOICE_CHANNEL_STATUS_DELETE`) [verified enum values], so a clear is attributed to whoever last *set* a status; the entry is not matched to the channel or time; audit entries may lag the gateway event; with no type-192 entry at all, `it[0]` throws (`IndexOutOfBoundsException`) and nothing is posted; without View Audit Log permission the REST call fails and nothing is posted. If Discord clears statuses automatically when a channel empties [unverified], those clears are attributed to the last setter.
4. The computed `locale` (zh-TW for non-Community guilds, else `guild.locale`) in both handlers is **never used** (`:119-121`, `:146-148`); messages always use `guild.locale`.

Detected-channel computation (`VL/ChannelData.kt:31-46`): ALLOW → allowed channels + direct children of allowed categories (stage channels included via categories; the select itself offers only VOICE and CATEGORY); BLOCK → all non-thread guild channels minus blocked (categories expanded). Evaluated at event time.

`sendListenChannel` (`VL/VoiceLogger.kt:352-364`): builds once in `guild.locale`; for each listen ID: missing channel → `return` (remaining listen channels skipped, nothing cleaned up); TextChannel/VoiceChannel → `sendMessage().queue()`; other types → `throw Exception("Unknown channel type")`.

Not handled: `GuildLeaveEvent` (settings of left guilds are only pruned at the next startup), channel delete events.

---

## 6. Configuration (`plugins/VoiceLogger/config.yaml`, `VL/config/ConfigSerializer.kt:5-8`)

| Key | Type | Default (code / shipped) | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` / `false` | false → command not registered, all handlers return early, localizers not built. Runtime toggle via dashboard → `reload()` + command refresh. |

Strict kaml decoding (unknown keys/wrong types are errors).

---

## 7. Localization & templates

Locales `en-US`, `zh-TW`; default zh-TW. Files per locale: `register.yaml`, `placeholder.yaml`, `message/{voice-logger@setting, delete, modify-allow, modify-block, on-channel-join, on-channel-left, on-channel-switch, on-status-new, on-status-update, on-status-delete}.yaml`.

- `register.yaml` → command localizations (§3). `placeholder.yaml` → `empty` (`Empty`/`無`), `allow_list_format`, `block_list_format` (both ``%…_channel_mention% (`%…_channel_id%`)\n``), looked up as `empty`, `allowListFormat`, `blockListFormat`.
- Templates are legacy (v1) `embeds`/`components` YAML rendered by Core v2 `MessageCreator` → v1 builder (URL fields kept only if they start with `http`; field values trimmed; >1024 chars throws).
- Locale selection: settings UI → `event.userLocale`; log posts → `guild.locale`; unknown locales → zh-TW templates; missing key in a present locale → exception.

Log templates (all: thumbnail `%member_avatar_url%`, footer `❖ ORDERLY SERVER ❖`, fields non-inline; first field `` `Member` ``/`` `使用者` `` = `%user_mention%\n\n\n` with the newlines trimmed away by JDA):

| Template | Title en-US / zh-TW | Title URL | Color | Remaining fields (en-US / zh-TW) |
|---|---|---|---|---|
| `on-channel-join` | `☛ Voice Channel Joined` / `☛ 進入語音頻道` | `%vl_channel_join_url%` | `#0EE000` | `Category`/`類別` = `%vl_category_join_mention%`; `Channel`/`頻道` = `%vl_channel_join_mention% (%vl_channel_join_name%)` |
| `on-channel-left` | `☛ Voice Channel Left` / `☛ 退出語音頻道` | `%vl_channel_left_url%` | `#C02020` | `Category` = `%vl_category_left_mention%`; `Channel` = `%vl_channel_left_mention% (%vl_channel_left_name%)` |
| `on-channel-switch` | `☛ Voice Channel Switch` / `☛ 轉換語音頻道` | `%vl_channel_join_url%` | `#D0D000` | `Category Left`/`退出類別`, `Channel Left`/`退出頻道` = `%vl_channel_left_mention% (%vl_channel_left_name%)`, `Category Join`/`進入類別`, `Channel Join`/`進入頻道` = `%vl_channel_join_mention% (%vl_channel_join_name%)` |
| `on-status-new` | `☛ New Voice Status` / `☛ 新增語音狀態` | `%vl_channel_url%` | `#0EE000` | `Category` = `%vl_category_mention%`; `Channel` = `%vl_channel_mention%`; `--> Content <--`/`--> 狀態 <--` = `%vl_status_after%` |
| `on-status-update` | `☛ Voice Status Updated` / `☛ 變更語音狀態` | `%vl_channel_url%` | `#D0D000` | Category, Channel, `--> Before <--`/`--> 變更前 <--` = `%vl_status_before%`, `==> After <==`/`==> 變更後 <==` = `%vl_status_after%` |
| `on-status-delete` | `☛ Voice Status Deleted` / `☛ 移除語音狀態` | `%vl_channel_url%` | `#C02020` | Category, Channel, `--> Status <--`/`--> 狀態 <--` = `%vl_status_before%` |
| `delete` | author `Voice Log`/`語音日誌`, title `☛ %channel_name%'s Channel Setting`, description `Deleted Successfully`/`刪除完成` | — | `#00FFFF` | — |

Placeholder sources: `vl_*` → this plugin (§5) and `getSettingMenu` (`vl_channel_mode`, `vl_allow_list_format`, `vl_block_list_format`, `VL/VoiceLogger.kt:423-429`); `%allowlist_channel_mention%`/`%allowlist_channel_id%`/`%blocklist_*%` → plain `String.replace`; `user_*`/`member_*` → Core `Placeholder.get(member)`; `channel_name` → Core `Placeholder.get(<interaction>)`; `bot_id`/`bot_name` → Core global. Substitution is recursive with `$` escape and cycle errors (Core semantics, [verified]).

---

## 8. Persistence

Only listen settings, JSON, identical schema to ChatLogger:
- File `plugins/VoiceLogger/setting/<guildId>.json` (`VL/JsonManager.kt:20-24`).
- `{ "<listenChannelId>": { "allow_mode": bool, "allow": [long…], "block": [long…] } }` (`VL/json/JsonData.kt:5-15`).
- Example: `{"1290000000000000888":{"allow_mode":true,"allow":[1290000000000000500],"block":[]}}` (500 = a voice channel or category).
- New entries created via add-allow/add-block are saved with `allow_mode=false` while memory says ALLOW → flips to BLOCK after restart.
- "Delete" removes the whole guild file.
- No log history is stored anywhere (posts only). No Mongo, no SQLite.

Migration: read files as-is; tolerate stale IDs; corrupt JSON is reset to `{}` by Core (`Core/json/JsonFileManager.kt:41-67`).

---

## 9. External dependencies

None beyond Core (no Gradle deps, no HTTP, no credentials, no plugin dependencies). Uses Core `MessageCreator` v2, `ComponentIdManager`, `Placeholder`, `StringLocalizer`, `JsonGuildFileManager`.

---

## 10. Discord requirements

- Intents: `GUILD_VOICE_STATES` (non-privileged); Core adds `GUILD_MEMBERS` (privileged) etc.
- Cache flags: `VOICE_STATE` (required for join/leave/move detection); member cache policy `VOICE` (Core default already includes it).
- Permissions (not checked in code): **View Audit Log** (status attribution); View Channel, Send Messages, Embed Links in listen channels.
- Rate-limit-sensitive: one message per listen channel per voice event (busy servers can generate bursts on the same log channel, 5 msgs/5 s per channel); one audit-log REST call (+ possible member fetch) per status change.

---

## 11. Concurrency

- Voice updates and settings interactions run on the single JDA gateway thread.
- Status-change handling (dataMap scan, shared per-member `Substitutor` mutation, message build, send) runs on JDA REST callback threads, concurrently with gateway-thread voice handling that mutates the same per-member substitutor → possible cross-event variable bleed; `dataMap` (`HashMap`) read concurrently with `computeIfAbsent` from the settings command.
- No locks; `JsonFileManager` methods are `@Synchronized`.

---

## 12. Bugs, quirks, dead code, hard-coded values

Probable bugs to fix:
1. `JsonManager` init CME on stale guild/listen-channel entries → plugin silently dead (`VL/JsonManager.kt:33-45`) [verified pattern].
2. `allow_mode=false` default on first add; "Delete" wipes all listen channels of the guild (`VL/JsonManager.kt:66,83,100,112`).
3. Switch embed's `Channel Join` uses `%vl_channel_join_mention%`, never set by the switch handler → shows the member's previous join mention (stale, from the shared per-member substitutor) or the literal placeholder (`VL/VoiceLogger.kt:308-314`).
4. Category placeholders only set when a category exists → stale value or literal placeholder otherwise (shared per-member substitutor, also shared with other plugins).
5. Status actor attribution (type 192 only, newest entry guild-wide, no channel/time match, `it[0]` on empty list) (`VL/VoiceLogger.kt:126-140`).
6. `sendListenChannel` stops at the first missing listen channel; non-Text/Voice listen channels throw (`VL/VoiceLogger.kt:356,361`).
7. `/voice-logger setting` only works in plain TextChannels (Core `Placeholder.get`).
8. Placeholder injection: channel names / status text containing `%…%` are expanded; a status containing `%vl_status_after%` (or a name referencing itself) makes rendering throw → no log [verified mechanism].
9. Fields > 1024 chars throw (lists of ≈22+ IDs break the settings menu permanently, persist-then-render).

Behavior to preserve (or explicitly decide):
- Only channel changes are logged (no mute/deafen/stream/video).
- Switch is one event, posted to every listen channel detecting either side.
- Bots are logged; moderator moves/disconnects are attributed to the moved member.
- Log locale = `guild.locale`; UI locale = user locale; zh-TW fallback.
- Settings model (ALLOW/BLOCK, add-only lists, category expansion at event time).

Dead code: `locale` computation and the `guildId`/`locale` fields of `StatusEventData`/`VoiceEventData` (`VL/VoiceLogger.kt:118-121,145-148,366-381`); `data.member?.let` null branch (member is never null). KDoc says "Economy plugin" (`VL/Event.kt:20-22`). No TODO/FIXME.

Hard-coded: footer text, colors, `CHINESE_TAIWAN` default, `"COMMUNITY"` feature string, `ALLOW`/`BLOCK`, select limits 1..25.

---

## 13. Testability

Pure logic to extract:
- `classify_voice_update(before_channel_id, after_channel_id) -> join | leave | switch | none`.
- `classify_status(old, new) -> new | update | delete` (exact rule: `new == ""` first, then `old == ""`).
- `detected_channels(...)` and `listen_targets(event_channels, settings)` (switch = union of both sides).
- Variable map builders per event type (incl. category-present/absent cases) → template rendering → embed dict with limits.
- Actor resolution policy as a pure function over audit-log entries (`(entries, channel_id, action_type, event_time) -> user_id | None`) so the attribution fix is testable.
- Settings repository (shared with ChatLogger: one implementation for both plugins).
- custom_id build/parse `voice-logger@a:<action>`.

Needs Discord doubles: voice state before/after (incl. stage channels, bot members), channel/category graph, audit-log fetch (empty / wrong type / forbidden), member fetch, channel send, interaction responses, raw status gateway events.

---

## 14. Porting assessment — Low (Medium if voice status logging must be kept)

Reasons: no database, one command, six component IDs, two events; logic is mostly reused from ChatLogger. The only hard part is the voice-channel-status event.

discord.py mapping:
- `on_voice_state_update(member, before, after)`; ignore updates where `before.channel == after.channel` (discord.py also fires for mute/deafen/stream, unlike JDA's `GuildVoiceUpdateEvent`).
- Voice channel status: discord.py exposes `VoiceChannel.edit(status=...)`, but I could not confirm a high-level event for the `VOICE_CHANNEL_STATUS_UPDATE` gateway event or a `discord.AuditLogAction` member for types 192/193 in the docs; plan for a raw-gateway hook (e.g. `on_socket_raw_receive` / `on_socket_event_type` with `enable_debug_events=True`, or a custom parser) and raw audit-log fetching — verify against the pinned discord.py version before committing to parity.
- `app_commands.Group("voice-logger", default_permissions=administrator, guild_only=True)` + `setting`; `ui.View(timeout=None)` with exact custom_ids; `ChannelSelect(channel_types=[voice, category], min_values=1, max_values=25)`.
- Share the settings/ChannelData module with ChatLogger.

Risks: status-event support in discord.py; deciding the attribution fix (match channel ID and action type, time window); preserving the switch semantics; placeholder-engine parity; existing JSON with the `allow_mode` ambiguity.
