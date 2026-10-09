# ChatLogger — porting inventory (branch `main` @ 3a59607)

Citation prefixes used below:
- `CL/` = `Plugins/ChatLogger/src/main/kotlin/logger/chat/`
- `CLR/` = `Plugins/ChatLogger/src/main/resources/`
- `Core/` = `Core/src/main/kotlin/core/`
- `SQ/` = `Plugins/API/SQLiteAPI/src/main/kotlin/api/sqlite/`

Claims marked **[verified]** were checked by running the exact SQL/library calls against the same library
versions used on main (sqlite-jdbc 3.51.1.0, commons-text 1.15.0, JDA 6.4.1, Kotlin stdlib + Moshi
LinkedHashTreeMap) in a scratch sandbox, outside the repo. Claims marked **[unverified]** depend on Discord
server behavior I could not observe.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/ChatLogger` |
| Kotlin files / LOC | 11 files / 995 LOC (`ChatLogger.kt` 381, `DbManager.kt` 188, `Event.kt` 131, `JsonManager.kt` 119, `ChannelData.kt` 77, `command/Register.kt` 33, `command/CmdFileSerializer.kt` 23, `json/JsonData.kt` 15, `command/PlaceholderSerializer.kt` 14, `config/ConfigSerializer.kt` 11, `Exceptions.kt` 3) |
| Resource files | 18: `info.yaml`, `config.yaml`, 8 lang files per locale × 2 (`en-US`, `zh-TW`) |
| Gradle | `build.gradle.kts`: plugin `xs-plugin` + `compileOnly(project(":Plugins:API:SQLiteAPI"))`; `gradle.properties`: `version.patch=0` → version `3.4.0-SNAPSHOT`, coreApi `3.4` |
| Purpose | (a) Persist the text of every guild message into per-guild SQLite files; (b) when a stored message is edited or deleted, post an embed with before/after text to configured "listen" channels; (c) an admin-only ephemeral settings UI per listen channel (allow/block channel lists). |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`CL/Event.kt:23`), main class `tw.xinshou.discord.plugin.logger.chat.Event` |
| Listener flag | `true` → the object is registered as a JDA event listener |

`info.yaml` (`CLR/info.yaml`), all fields:

```yaml
author: ${author}        # expanded at build → "xinshoutw"
name: ${name}            # → "ChatLogger"
coreApi: ${coreApi}      # → "3.4"
version: ${version}      # → "3.4.0-SNAPSHOT"
main: "tw.xinshou.discord.plugin.logger.chat.Event"
component_prefix: "chat-logger@"
depend_plugins: ["SQLiteAPI"]           # hard dependency
require_intents: ["GUILD_MESSAGES", "MESSAGE_CONTENT"]
# not set: description, prefix (defaults to name), soft_depend_plugins, require_cache_flags,
#          require_member_cache_policies, depend_jars, soft_depend_jars
```

Terminology used in this report:
- **listen channel**: the channel in which `/chat-logger setting` was run; it is the log destination and owns one settings record.
- **detected channel**: a channel whose message edits/deletes are forwarded to a listen channel.
- **logged/stored channel**: a channel whose messages are written to SQLite (independent of listen settings when `log_all: true`).

---

## 2. Lifecycle

### load() (`CL/Event.kt:27-48`)
1. `super.load()` (Core): exports `lang/` from the jar to `plugins/ChatLogger/lang/` **without overwriting existing files** (unless the `-Flang` CLI flag) (`Core/plugin/PluginEvent.kt:23-29`), then reads `plugins/ChatLogger/config.yaml` (exported from the jar if missing) with kaml in strict mode (`Core/plugin/PluginEvent.kt:59-65`).
2. If `enabled == false`: log `warn "ChatLogger is disabled."` and return (localizers are not created).
3. Otherwise build `registerLocalizer` (file `register.yaml`) and `placeholderLocalizer` (file `placeholder.yaml`), both with default locale `zh-TW`. `StringLocalizer` throws if `lang/zh-TW/<file>` is missing (`Core/localizations/StringLocalizer.kt:66`).

Nothing else is initialized at load. `JsonManager`, `DbManager` and `ChatLogger` are Kotlin `object`s that initialize lazily on first access (see below).

### Lazy initializers (effectively the startup work)
- `ChatLogger` object (`CL/ChatLogger.kt:31-43`): creates `ComponentIdManager(prefix="chat-logger@", idKeys={"action": STRING})` and a v2 `MessageCreator` that reads every `plugins/ChatLogger/lang/<locale>/message/*.yaml` from disk.
- `DbManager` object (`CL/DbManager.kt:22-67`), first touched by the first `MessageReceivedEvent`/update/delete/`unload()`:
  1. `mkdir -p plugins/ChatLogger/data`.
  2. For every `data/*.db`: if `log_all == false` and the bot is not in guild `<filename>` → delete the file. (`jdaBot.getGuildById(name)` throws `NumberFormatException` for a non-numeric file name; this is outside the try block, so a stray `foo.db` breaks DbManager init entirely.)
  3. Open (and keep open) a connection under key `"CL:<guildId>"`, list tables (`SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'`). Each table name is a channel ID. If `log_all == false` and the channel no longer exists → schedule a drop; otherwise add the ID to the in-memory `channelTableCache`.
  4. Drop scheduled tables with `DROP TABLE IF EXISTS <id>;` — **unquoted numeric identifier is a syntax error** [verified: `near "1300000000000000001": syntax error`]; the exception is caught and logged per file (`CL/DbManager.kt:54-65`). Net effect: stale tables are never dropped.
- `JsonManager` object (`CL/JsonManager.kt:29-58`), first touched by a slash command, button, select, message update/delete event, or `unload()`:
  1. `mkdir -p plugins/ChatLogger/setting`; `JsonGuildFileManager` loads every `setting/*.json` (file name must parse as Long, `Core/json/JsonGuildFileManager.kt:16-18`).
  2. For each guild file: if the bot is not in that guild → `removeAndSave(guildId)` (deletes the file) **inside a 2-parameter `Map.forEach` → `ConcurrentModificationException` regardless of position** [verified] → `JsonManager` class init fails (`ExceptionInInitializerError`, then `NoClassDefFoundError` on every later access in the process). The file is already deleted, so the next restart succeeds.
  3. For each listen-channel entry: if the listen channel no longer exists → `data.remove(id)` inside a destructured `forEach` over Moshi's `LinkedHashTreeMap` → `ConcurrentModificationException` unless it is the last key [verified]. Here the file is **not** rewritten (the `save()` after the loop is never reached), so **every restart fails the same way** until the JSON is edited by hand.
  4. Otherwise the allow/block lists are filtered to channels that still exist, the record is written back, and `dataMap[listenChannelId] = ChannelData(...)`.

### unload() (`CL/Event.kt:50-55`)
Runs even when `enabled == false`: `DbManager.disconnect()` then `dataMap.clear()`, log `"ChatLogger unloaded."`. Touching `DbManager`/`dataMap` here triggers both lazy initializers if they had not run (creating directories, opening every DB, and possibly the CME above; an exception here aborts `BotLoader.stop()` for the remaining plugins, `Core/base/BotLoader.kt:164-187`).
`DbManager.disconnect()` iterates **listen channel IDs** and calls `SQLiteFileManager.disconnect("CL:<listenChannelId>")`, but connections are keyed `"CL:<guildId>"`; every call throws `NoSuchElementException`, which is swallowed (`CL/DbManager.kt:134-141`). Net effect: connections are never closed.

### reload() (`CL/Event.kt:57-80`)
`super.reload()` (re-export lang without overwrite, re-read config). If disabled → warn and return (in-memory state and DB connections remain). If enabled → rebuild both localizers and call `ChatLogger.reload()` (new `MessageCreator`, i.e. re-read message templates). `DbManager`/`JsonManager` are **not** re-initialized; a `log_all` change takes effect immediately for `isListenable` but startup cleanup is not re-run. Reload is triggered by the dashboard (enable toggle / config save → `BotLoader.reloadPluginStrict`, which also re-registers guild commands) (`Core/dashboard/CoreDashboardBackend.kt:131-224`).

### Background jobs
None (no schedulers, timers, coroutines or executors). Async work is only JDA `RestAction.queue()` callbacks (JDA callback pool).

### In-memory state
| State | Type | Content |
|---|---|---|
| `JsonManager.dataMap` | `HashMap<Long, ChannelData>` | listenChannelId → {mode, allow set, block set} (all guilds) |
| `DbManager.channelTableCache` | `LinkedHashSet<Long>` | channel IDs that have a SQLite table |
| `SQLiteFileManager.dbConn` (SQLiteAPI plugin) | `HashMap<String, PathConnection>` | `"CL:<guildId>"` → open JDBC connection |
| `ChatLogger.messageCreator` | v2 `MessageCreator` | parsed templates per locale |
| Core `Placeholder` caches | `HashMap<Long, Substitutor>` | per user/member substitutors, mutated by this plugin (see §12) |

---

## 3. Slash commands & context menus

One guild command; no context menus; no global commands. `Event.guildCommands()` returns it only when `enabled == true` (`CL/Event.kt:83-89`). Core registers guild commands in every guild by bulk overwrite at startup, on guild join and after a plugin reload (`Core/base/ListenerManager.kt:18-36`, `Core/base/BotLoader.kt:150-159`).

### `/chat-logger setting`
Definition (`CL/command/Register.kt:22-33`):

| Field | Value |
|---|---|
| Name / description (base) | `chat-logger` / `commands about chat logger` |
| Subcommand | `setting` / `set chat log in this channel` |
| Options | none |
| default_member_permissions | `ADMINISTRATOR` |
| Guild-only / NSFW | guild command (registered per guild); NSFW not set |
| Name localizations | en-US: `chat-logger` / `setting`; zh-TW: `訊息紀錄` / `設定` |
| Description localizations | en-US: `commands about chat logger` / `set chat log in this channel`; zh-TW: `有關訊息紀錄的指令` / `設定訊息紀錄在此頻道` |
| Localization source | `lang/<locale>/register.yaml`, keys flattened from **Kotlin property names**: `chatLogger.name`, `chatLogger.description`, `chatLogger.subcommands.setting.name`, `chatLogger.subcommands.setting.description` (`Core/localizations/StringLocalizer.kt:69-97`) |

Behavior, step by step:
1. Core `InteractionLogger` (registered before plugin listeners) calls `deferReply(ephemeral=true)` if `--auto-defer-interactions` (default true) and logs `[CMD] <user>: <commandString>` (`Core/logger/InteractionLogger.kt:25-30`, `Core/util/Arguments.kt:34-41`). The plugin never replies itself; it only edits the deferred response, so it depends on this Core behavior.
2. Return if `enabled == false`; return unless `fullCommandName == "chat-logger setting"` (`CL/Event.kt:91-95`).
3. `dataMap.computeIfAbsent(channelId)` → creates in-memory default settings (mode ALLOW, empty lists) for the current channel. **Not persisted** until a toggle/add (`CL/ChatLogger.kt:53-55`).
4. `Placeholder.get(event)` calls `guildChannel.asTextChannel()` (`Core/builtin/placeholder/Placeholder.kt:75`) → throws `IllegalStateException` in any channel that is not a plain TextChannel (voice-channel chat, thread, announcement, stage, forum post). In that case nothing is sent and the ephemeral "thinking…" response is never completed.
5. Render template `chat-logger@setting` in `event.userLocale` (§7) and `hook.editOriginal(...)` → ephemeral settings message.

No server-side permission check, no validation, no error templates.

Rendered settings message (en-US example; channel `logs`, ALLOW mode, allow = [111, 222], block empty):
- embed author `Message Log`; title `☛ logs's Channel Setting`; footer `❖ ORDERLY SERVER ❖`; no color;
- fields (non-inline): `Channel Mode` = `<ALLOW>` (literal `ALLOW`/`BLOCK`, not localized, `CL/ChatLogger.kt:362`); `Allowlist Channels` = ``<#111> (`111`)\n<#222> (`222`)`` (JDA trims the trailing `\n`); `Blocklist Channels` = `Empty` (zh-TW `無`);
- one action row: `Toggle Mode` (PRIMARY), `Modify Allowlist` (SUCCESS), `Modify Blocklist` (SECONDARY), `Delete` (DANGER) — zh-TW labels `切換模式`, `設定白名單`, `設定黑名單`, `刪除`.

---

## 4. Components

Routing: `Event` ignores components whose `componentId` does not start with `chat-logger@` (`CL/Event.kt:97-107`); `ComponentIdManager.parse` maps short key `a` back to `action` (`Core/util/ComponentIdManager.kt:154-191`). ID format = `<prefix><shortKey>:<value>` with `a` = `action` (first and only idKey). All components live on the ephemeral settings message, so only the command invoker sees them. No timeouts or expiry in code.

| custom_id | Type | Template | Behavior |
|---|---|---|---|
| `chat-logger@a:toggle_btn` | Button PRIMARY | `chat-logger@setting` | Flip mode for the listen channel (= `event.channel`) in memory; JSON: `getOrPut(id){allow_mode=false,[],[]}` then `allow_mode = <new mode>`; save. Then `deferEdit()` + `hook.editOriginal(settings menu)` (`CL/ChatLogger.kt:247-261`, `CL/JsonManager.kt:60-71`). |
| `chat-logger@a:modify_allow_btn` | Button SUCCESS | → `modify-allow` | `editMessage(...)` replaces the whole message with the channel select (no embed). No data change (`CL/ChatLogger.kt:229-239`). |
| `chat-logger@a:modify_block_btn` | Button SECONDARY | → `modify-block` | Same, block select. |
| `chat-logger@a:delete_btn` | Button DANGER | → `delete` | `dataMap.remove(listenChannelId)` and **delete the entire guild JSON file** `setting/<guildId>.json` (all listen channels of the guild), then `editMessage(delete template)` (`CL/ChatLogger.kt:263-277`, `CL/JsonManager.kt:107-113`). |
| `chat-logger@a:modify_allow_menu` | EntitySelect (CHANNEL), min 1, max 25 | → `chat-logger@setting` | Selected IDs are **added** (set union) to the allow list; JSON: `getOrPut(id){allow_mode=false,[],[]}` then `allow = <in-memory set>`; save. Then `deferEdit()` + `hook.editOriginal(settings menu)` (`CL/ChatLogger.kt:79-117`, `CL/JsonManager.kt:73-88`). |
| `chat-logger@a:modify_block_menu` | EntitySelect (CHANNEL), min 1, max 25 | → `chat-logger@setting` | Same for the block list (`CL/JsonManager.kt:90-105`). |

Select-menu details (`CLR/lang/*/message/modify-allow.yaml`, `modify-block.yaml`): placeholder `choose channels, categories or search here` / `選擇頻道、類別或在此搜尋`; `channel_types`: TEXT, VOICE, CATEGORY, NEWS, STAGE, FORUM, MEDIA, GUILD_NEWS_THREAD, GUILD_PUBLIC_THREAD, GUILD_PRIVATE_THREAD (Discord types 0, 2, 4, 5, 13, 15, 16, 10, 11, 12). No default values (current selections are not pre-filled).

Edge behavior:
- Unknown `action` on a button → silently ignored, interaction never acknowledged ("This interaction failed" on the client).
- Unknown `action` on a select → `throw Exception("Unknown key …")`, never acknowledged (`CL/ChatLogger.kt:104`).
- There is **no way to remove** individual channels from a list (add only; "Delete" wipes the guild file).
- Persist-then-render: the JSON is written before the menu is rendered; if rendering fails (e.g. list text > 1024 chars, §12) the change is saved but the user sees no update.

---

## 5. Events

All handlers return immediately when `enabled == false`.

| JDA event | Filter (`CL/Event.kt`) | Behavior (`CL/ChatLogger.kt`) |
|---|---|---|
| `SlashCommandInteractionEvent` | fullCommandName == `chat-logger setting` | §3 |
| `ButtonInteractionEvent` | id starts with `chat-logger@` | §4 |
| `EntitySelectInteractionEvent` | id starts with `chat-logger@` | §4 |
| `MessageReceivedEvent` | from guild; author ≠ bot itself (`:109-113`) | If `isListenable(channelId)` (`log_all` or channel has a table): `INSERT` (message_id, author_id, text, 0) into table `<channelId>` of `data/<guildId>.db`, creating the table if not in `channelTableCache` (`:119-130`). Other bots and webhooks are stored too; there is no message-type filter. Threads get their own table. |
| `MessageUpdateEvent` | from guild; author ≠ bot itself (`:115-119`) | See "edit flow" below (`:132-172`). |
| `MessageDeleteEvent` | from guild (`:121-125`) | See "delete flow" below (`:174-226`). |
| `GuildLeaveEvent` | — | If `log_all == false` → `SQLiteFileManager.deleteDatabase(guildId)`; the key should be `"CL:<guildId>"`, so this is a **no-op** (`CL/ChatLogger.kt:241-244`, `CL/DbManager.kt:125-127`, `SQ/SQLiteFileManager.kt:35-40`). JSON settings are not touched. |

Not handled: `MessageBulkDeleteEvent` (Core sets `setBulkDeleteSplittingEnabled(false)`, `Core/base/BotLoader.kt:61`, so purge/bulk deletes produce no `MessageDeleteEvent` and are **never logged**); reactions; pins (unless they arrive as a MESSAGE_UPDATE, see edit flow); attachments/stickers (never stored).

**Text extraction** `getMessageContent(message)` (`CL/ChatLogger.kt:298-317`) — exact algorithm:
- if the message has no embeds → `contentRaw`;
- else (content is **ignored**) for each embed, concatenated with no separator between embeds: `author.name + "\n"` if author present, then `"${title}\n\n"`, then `description`, then for each field `"${name}\n${value}\n\n"`. Null title/description are appended as the literal string `null` (Java `StringBuilder.append(null)`); there is no newline between the description and the first field name.

**Detected-channel computation** for a listen channel (`CL/ChannelData.kt:31-46`):
- ALLOW: resolve each allow ID in the listen channel's guild; a Category expands to its direct children (no threads); missing IDs are skipped.
- BLOCK: all guild channels from `guild.channels` (excludes threads [verified in JDA: `getChannels` filters `ICategorizableChannel` + categories]) minus the blocked channels (categories expanded the same way).
- Membership test uses channel equality (by ID). Evaluated at event time, so category membership is dynamic.

**Edit flow** (`MessageUpdateEvent`, channel C in guild G):
1. Return if not `isListenable(C)`.
2. `listenIds` = every listen channel (any guild) whose detected set contains C.
3. `DbManager.updateMessage`: ensure table; `SELECT message, user_id, update_count FROM '<C>' WHERE message_id = '<id>'`. If no row → `MessageNotFound` → return silently (sqlite-jdbc returns `null` for `getString` on an empty result; the Kotlin non-null check turns it into an NPE, which is mapped to `MessageNotFound`) [verified]. Messages sent before logging started are therefore never logged, and are not inserted on edit either.
4. Otherwise `update_count += 1`, `UPDATE … SET message = <new text>, update_count = <n>` (the stored text is overwritten; only the latest version is kept).
5. If `listenIds` is empty → return (DB still updated).
6. Substitutor = `Placeholder.get(event.member)` (author), or Core's **global** substitutor when `member` is null (webhooks), with `cl_msg_after_url` = jump URL, `cl_channel_mention`, `cl_change_count` = n (1 on the first edit), `cl_msg_before` = previous stored text, `cl_msg_after` = new text; `cl_category_mention` only if C has a parent category. `channel.asStandardGuildChannel()` throws for threads → **edits in threads are never forwarded** (DB is still updated).
7. Render `on-msg-update` in **`guild.locale`** and send to each listen channel (§"sendListenChannel" below).
- No equality check: any MESSAGE_UPDATE counts as an edit and increments `update_count`. JDA 6.4.1 dispatches `MessageUpdateEvent` for every MESSAGE_UPDATE payload with `author`+`type` [verified in bytecode]. Whether Discord sends such full payloads for link-preview unfurls or pin changes is **[unverified]**; if it does, an unfurl is logged as an edit whose "after" is the embed text (step "text extraction").

**Delete flow** (`MessageDeleteEvent`, channel C):
1. Return if not `isListenable(C)`; compute `listenIds` as above.
2. Query the row (the row is **not deleted**; content of deleted messages stays in SQLite). Not found → return silently.
3. If `listenIds` empty → return.
4. `guild.retrieveMemberById(stored user_id).queue { member -> … }` (cache first, else REST). On success: substitutor = `Placeholder.get(member)` + `cl_channel_mention`, `cl_change_count` (= number of recorded edits, 0 if never edited), `cl_msg_before` (stored text), `cl_category_mention` if the channel has a category; render `on-msg-delete` in `guild.locale`; send. The thread case again throws in `asStandardGuildChannel()`.
5. On failure (author left the guild: 10007 Unknown Member; webhook author IDs) JDA's default failure handler logs the error and **nothing is posted**. The `catch (ErrorResponseException)` fallback with code 10007 (`CL/ChatLogger.kt:212-224`) is dead code because `queue` is asynchronous.

**sendListenChannel** (`CL/ChatLogger.kt:279-295`): builds the message once, then for each listen ID: `guild.getGuildChannelById(id)`; if null → `DbManager.markChannelAsUnavailable(id)` (removes that ID from the *table* cache, not from settings) and `return` from the whole function (remaining listen channels are skipped); TextChannel or VoiceChannel → `sendMessage(...).queue()`; any other type (announcement, stage, thread) → `throw Exception("Unknown channel type")`. Note `guild` is the event's guild: a listen channel in another guild can never match anyway.

---

## 6. Configuration (`plugins/ChatLogger/config.yaml`, `CL/config/ConfigSerializer.kt:7-11`)

| Key | Type | Default (code / shipped file) | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` / `false` | Master switch. false → no commands registered, every handler returns early, no localizers; `unload()` still touches DB/JSON (see §2). Toggleable at runtime from the dashboard (`reload()` + command refresh). |
| `log_all` | Boolean | `true` / `true` | `isListenable(C) = log_all || C in channelTableCache` (`CL/ChatLogger.kt:378-381`). true → store/process messages from every channel. false → only channels that **already have a table** are processed, and new tables are only created for listenable channels, so the set of logged channels is frozen to channels seen while `log_all` was true (probable bug, §12). Also gates startup cleanup (delete DB of left guilds, drop tables of deleted channels — the latter is broken) and the (broken) guild-leave DB deletion. |

Parsing: kaml with default configuration (strict mode = true [verified default]) → unknown keys or wrong types throw; at load this aborts plugin loading (Core `PluginLoader.run()` has no per-plugin try/catch → bot startup fails), at dashboard reload the change is rolled back. Missing keys use defaults.

---

## 7. Localization & templates

Locales: `en-US`, `zh-TW`; default (fallback) locale `zh-TW` for both localizers and messages.

Files per locale (`CLR/lang/<locale>/`): `register.yaml`, `placeholder.yaml`, `message/chat-logger@setting.yaml`, `message/delete.yaml`, `message/modify-allow.yaml`, `message/modify-block.yaml`, `message/on-msg-delete.yaml`, `message/on-msg-update.yaml`. Templates are read from `plugins/ChatLogger/lang/...` on disk (exported once, user-editable).

| Source | Consumer | Keys |
|---|---|---|
| `register.yaml` (`CmdFileSerializer`) | command name/description localizations | YAML `chat-logger.{name,description,subcommands.setting.{name,description}}`; looked up as `chatLogger.*` (Kotlin property names) |
| `placeholder.yaml` (`PlaceholderSerializer`) | settings-menu list rendering | YAML `empty`, `allow_list_format`, `block_list_format`; looked up as `empty`, `allowListFormat`, `blockListFormat` |
| `message/*.yaml` | Core v2 `MessageCreator` (template key = file name without extension) | see below |

Fallback rules: command localizations fall back to zh-TW per key (`Core/localizations/LocalStringMap.kt:29-31`); message templates are selected by exact locale directory, any other locale (e.g. en-GB, zh-CN) gets the **zh-TW** templates, and a key missing in an existing locale directory throws (no per-key fallback) (`Core/builtin/messagecreator/v2/MessageCreator.kt:130-134`). Settings UI uses `event.userLocale`; log posts use `guild.locale` (non-Community guilds normally report en-US).

Template engine: all six files use the legacy (v1) `embeds:`/`components:` schema (`!ButtonsComponent`, `!EntitySelectMenu` tags), rendered by the v2 `MessageCreator`, which delegates to the v1 builder (`Core/builtin/messagecreator/v2/builder/MessageBuilder.kt:56-86`). Builder rules that matter for parity (`Core/builtin/messagecreator/v1/builder/MessageBuilder.kt`): every string goes through the placeholder substitutor; title/author/footer/thumbnail/image URLs are dropped unless the substituted value starts with `http`; `color_code` via `Color.decode`; fields are added with JDA `addField` (value trimmed, empty → U+200E, >1024 chars → `IllegalArgumentException`, embed >6000 chars → `IllegalStateException` [verified]).

Templates (en-US text / zh-TW text):
- `chat-logger@setting`: author `Message Log`/`訊息日誌`; title `☛ %channel_name%'s Channel Setting`/`☛ %channel_name% 的頻道設定`; footer `❖ ORDERLY SERVER ❖`; fields `Channel Mode`/`頻道模式` = `<%cl_channel_mode%>`, `Allowlist Channels`/`白名單頻道` = `%cl_allow_list_format%`, `Blocklist Channels`/`黑名單頻道` = `%cl_block_list_format%`; 4 buttons (§4).
- `delete`: author, same title, description `Deleted Successfully`/`刪除完成`, footer, color `#00FFFF`.
- `modify-allow` / `modify-block`: only the entity select (§4).
- `on-msg-update`: title `☛ Message Updated`/`☛ 變更訊息` with url `%cl_msg_after_url%`; thumbnail `%member_avatar_url%`; color `#D0D000`; footer; fields — en-US order: `` `Member` ``=`%user_mention%`, `` `Category` ``=`%cl_category_mention%`, `` `Channel` ``=`%cl_channel_mention%`, `` `Change Count` ``=`%cl_change_count%\n\n\n` (newlines trimmed away by JDA), `` `--> Before <--` ``=`%cl_msg_before%`, `` `==> After <==` ``=`%cl_msg_after%`; **zh-TW order differs**: 類別, 頻道, 使用者, 變更次數, 變更前, 變更後.
- `on-msg-delete`: title `☛ Message Deleted`/`☛ 刪除訊息` (no url); thumbnail `%member_avatar_url%`; color `#C02020`; fields en-US: Member, Category, Channel, Change Count, `` `--> Content <--` ``=`%cl_msg_before%`; zh-TW: 類別, 頻道, 使用者, 變更次數, 內容.

Placeholders (exact names) and sources:
| Placeholder | Source |
|---|---|
| `%cl_channel_mode%`, `%cl_allow_list_format%`, `%cl_block_list_format%` | `getSettingMenu` (`CL/ChatLogger.kt:360-366`) |
| `%allowlist_channel_mention%`, `%allowlist_channel_id%`, `%blocklist_channel_mention%`, `%blocklist_channel_id%` | plain `String.replace` inside `placeholder.yaml` formats (`<#id>` and `id`) before substitution |
| `%cl_msg_after_url%`, `%cl_channel_mention%`, `%cl_change_count%`, `%cl_msg_before%`, `%cl_msg_after%`, `%cl_category_mention%` | edit/delete flows (§5) |
| `%user_mention%`, `%member_avatar_url%` (+ unused `user_id`, `user_name`, `user_avatar_url`, `member_display_name`, `member_fixed_name`) | Core `Placeholder.get(member)` |
| `%channel_name%` (+ `channel_id`, `language`, `component_*`, `command_*`, `subcommand_name`, `channel_category_name`) | Core `Placeholder.get(<interaction event>)` |
| `%bot_id%`, `%bot_name%` | Core global substitutor |

Substitution semantics (Core `Substitutor` = Apache commons-text `StringSubstitutor("%", "%", escape '$')`) [verified]: unknown placeholders are left verbatim; resolved values are themselves recursively substituted; a self-reference raises `IllegalStateException("Infinite loop in property interpolation…")`; `$%x%` renders as the literal `%x%`.

---

## 8. Persistence

### 8.1 Message store — SQLite (via SQLiteAPI plugin)
- File: `plugins/ChatLogger/data/<guildId>.db` (one per guild); connection key `"CL:<guildId>"` in the shared `SQLiteFileManager` (`CL/DbManager.kt:164-166`).
- One table per channel/thread, named by the decimal channel ID and referenced as a single-quoted string (SQLite accepts it as an identifier) (`CL/DbManager.kt:168-187`):

```sql
CREATE TABLE '<channelId>' (
  message_id   INT  PRIMARY KEY NOT NULL ON CONFLICT FAIL,  -- not a rowid alias ("INT", not "INTEGER")
  user_id      INT  NOT NULL,                               -- author id at receive time
  message      TEXT NOT NULL,                               -- extracted text (§5), latest version only
  update_count INT  NOT NULL                                -- number of MESSAGE_UPDATEs seen
)
```
- Example row (table `1290000000000000001`): `(1290000000000004321, 300000000000000045, 'hello world', 2)`.
- Operations: insert on receive (duplicate id → constraint error [verified]); update text+count on edit; read-only on delete.
- Retention/expiry: **none**. Rows are never deleted (not on message delete, not on channel delete with `log_all: true`, not on guild leave — the guild-leave path is a no-op bug). No size limit. No timestamp column (creation time is derivable from the snowflake: `(message_id >> 22) + 1420070400000` ms).
- Privacy: with the shipped `log_all: true`, the text of every message (users, other bots, webhooks; not this bot) in every channel and thread the bot can read is stored indefinitely, including the last version of edited and the content of deleted messages; deleted content is re-posted to log channels. Requires the privileged MESSAGE_CONTENT intent. No opt-out or purge command.
- Startup maintenance (`CL/DbManager.kt:22-67`): only when `log_all == false`: delete DB files of guilds the bot left; drop tables of deleted channels (always fails: unquoted identifier).

### 8.2 Listen settings — JSON (`JsonGuildFileManager` + Moshi)
- File: `plugins/ChatLogger/setting/<guildId>.json` (`CL/JsonManager.kt:20-24`).
- Schema (`CL/json/JsonData.kt:5-15`): object keyed by listen channel ID (string) → `{ "allow_mode": bool, "allow": [long…], "block": [long…] }`.
- Example: `{"1290000000000000777":{"allow_mode":true,"allow":[1290000000000000001,1290000000000000100],"block":[]}}`.
- `allow_mode: true` = ALLOW mode, `false` = BLOCK mode.
- New entries created by add-allow/add-block are written with `allow_mode: false` while the in-memory mode is ALLOW (default), so the mode **flips to BLOCK after a restart** unless the user pressed Toggle (§12).
- Corrupt JSON → logged and replaced by `{}` on disk (`Core/json/JsonFileManager.kt:29-67`).

### Migration / compat
- Python `sqlite3` can open these files as-is; quote numeric table names (`"…"`); keep `INT PRIMARY KEY` semantics (no rowid alias). Consider adding an index-free migration only if new columns (e.g. `created_at`) are introduced.
- JSON IDs are 64-bit integers (safe in Python). Keys are strings. Tolerate stale IDs (must not crash, unlike the Kotlin init).
- Decide whether to normalize the `allow_mode` default bug when reading existing files (cannot be detected after the fact).

---

## 9. External dependencies

- Gradle: `compileOnly(project(":Plugins:API:SQLiteAPI"))` (SQLiteAPI bundles `org.xerial:sqlite-jdbc:3.51.1.0` and Exposed 1.0.0, unused here). Core provides JDA 6.4.1, Moshi 1.15.2, kaml 0.104.0, commons-text 1.15.0.
- Hard plugin dependency `SQLiteAPI`, used through the static object `SQLiteFileManager` (`getConnection`, `connect`, `disconnect`, `deleteDatabase`) (`SQ/SQLiteFileManager.kt:8-46`). `connect` throws `KeyAlreadyExistsException` if the key exists; `getConnection` is unsynchronized.
- No HTTP endpoints, no credentials, no soft dependencies.

---

## 10. Discord requirements

- Intents: `GUILD_MESSAGES`, **`MESSAGE_CONTENT` (privileged)**; Core always adds `GUILD_MEMBERS` (privileged), `SCHEDULED_EVENTS`, `GUILD_EXPRESSIONS` (`Core/base/BotLoader.kt:68-75`).
- Cache flags / member cache: none required by this plugin (Core default member cache policy OWNER|VOICE, so `retrieveMemberById` usually hits REST).
- Bot permissions (not checked in code): View Channel in monitored channels (otherwise the gateway does not deliver their messages); View Channel, Send Messages, Embed Links in listen channels.
- Rate-limit-sensitive operations: one REST member fetch per forwarded delete (uncached members); one message per listen channel per edit/delete (5 msgs/5 s per channel). Synchronous SQLite write per received message on the gateway thread (latency, not a Discord limit).

---

## 11. Concurrency

- JDA dispatches gateway events sequentially on the WebSocket thread (no event pool configured), so receive/update/delete DB work is single-threaded.
- The delete-flow send happens in a REST callback thread: it calls `Placeholder.get(member)` (unsynchronized `HashMap` + shared mutable `Substitutor`) and `markChannelAsUnavailable` (unsynchronized `LinkedHashSet`) concurrently with gateway-thread handlers → rare data races; a concurrent edit and delete by the same member can leak `cl_*` values into each other's render.
- `channelTableCache`, `dataMap` (`HashMap`) are unsynchronized; settings UI and gateway events both run on the WS thread, so practical risk is low.
- `SQLiteFileManager.getConnection` + `connect` race is theoretical (single WS thread).
- `JsonFileManager.save/delete` are `@Synchronized`.
- `messageCreator` is a non-volatile `var` swapped by `reload()` from a dashboard thread.

---

## 12. Bugs, quirks, dead code, hard-coded values

Probable bugs to fix (the port should not replicate; tests should pin the corrected behavior):
1. `JsonManager` init throws `ConcurrentModificationException` when any settings file belongs to a guild the bot left (one-time) or when a non-last listen channel was deleted (every restart) → all settings UI and forwarding dead (`CL/JsonManager.kt:33-45`) [verified].
2. New JSON entries get `allow_mode=false` while memory says ALLOW → mode flips after restart (`CL/JsonManager.kt:66,83,100`).
3. "Delete" deletes the whole guild file, not just this listen channel (`CL/JsonManager.kt:107-113`).
4. `log_all: false` freezes logging to channels that already have tables; it never consults listen settings (`CL/ChatLogger.kt:378-381` + `CL/DbManager.kt:168-187`).
5. Startup `DROP TABLE IF EXISTS <id>` syntax error (`CL/DbManager.kt:57`) [verified].
6. Guild-leave DB deletion uses key `<guildId>` instead of `CL:<guildId>` → no-op (`CL/DbManager.kt:125-127`).
7. `disconnect()` uses listen channel IDs instead of guild IDs → connections never closed (`CL/DbManager.kt:134-141`).
8. Delete of a message whose author left / webhook message → no log (dead fallback, `CL/ChatLogger.kt:190-225`).
9. Fields >1024 chars (messages longer than 1024 chars, or allow/block lists of ≈22+ IDs) throw → no log / settings menu can no longer be rendered (so it can't be deleted from the UI either). Suggest truncation.
10. Thread edits/deletes never forwarded (`asStandardGuildChannel()` throws, `CL/ChatLogger.kt:157,197`).
11. `sendListenChannel` returns on the first missing listen channel (skips the rest) and removes the wrong cache entry (`CL/ChatLogger.kt:284-287`); non-Text/Voice listen channels throw (`:292`).
12. Placeholder injection: message text is recursively substituted — `%bot_id%` etc. in a user message are expanded; including `%cl_msg_after%` in an edit or `%cl_msg_before%` in a message makes the render throw (`Infinite loop…`) → the edit/delete is **not logged** (a log-evasion vector) [verified]; `$%x%` loses the `$`.
13. Stale `%cl_category_mention%`: only set when the channel has a category, on a cached per-member substitutor shared across events and plugins → a channel without category shows the previous category or the literal `%cl_category_mention%`. Webhook edits mutate Core's **global** substitutor.
14. Embed text extraction ignores message content when embeds exist and appends literal `null` for missing title/description (`CL/ChatLogger.kt:298-317`).
15. `/chat-logger setting` only works in plain TextChannels (Core `Placeholder.get` → `asTextChannel()`), otherwise the deferred reply hangs.
16. Bulk deletes not logged (Core disables bulk-delete splitting; plugin ignores `MessageBulkDeleteEvent`).
17. Stray non-numeric `*.db` / `*.json` file names break DbManager / JsonManager init.

Behavior to preserve (deliberate or harmless):
- Bot's own messages are not stored; other bots/webhooks are.
- `update_count` semantics (edit: count after this edit; delete: edits so far).
- Only the latest text version is stored; deleted rows retained (decide explicitly with the user — privacy).
- Settings UI is ephemeral, admin-only by default permission, add-only lists, ALLOW/BLOCK literals.
- Log posts use `guild.locale`, UI uses user locale; zh-TW default.

Hard-coded values: footer `❖ ORDERLY SERVER ❖` and all colors in templates; default locale `DiscordLocale.CHINESE_TAIWAN` (`CL/Event.kt:37,44,67,74`, `CL/ChatLogger.kt:41,48`); `"CL:"` key prefix; `"ALLOW"`/`"BLOCK"` strings; select `min 1`/`max 25`.

Dead code: `ErrorResponseException` 10007 branch (`CL/ChatLogger.kt:212-224`); unused `JsonManager.logger` (`CL/JsonManager.kt:18`). No TODO/FIXME comments in the plugin.

---

## 13. Testability

Pure logic to extract (unit-testable without Discord):
- `extract_text(content, embeds) -> str` (decide whether to keep the `null`/content-ignoring quirks).
- `detected_channels(mode, allow, block, guild_channels, children_of) -> set[int]` and `listen_targets(channel_id, settings_by_listen_channel) -> list[int]`.
- `render_id_list(ids, fmt, empty_text) -> str` and mode label.
- Message repository: `insert`, `apply_edit -> (old_text, author_id, new_count) | None`, `lookup -> (text, author_id, count) | None`; table naming/quoting; schema compatibility with existing files.
- Settings repository: toggle/add/delete semantics and startup validation (stale guild/channel pruning without crashing).
- custom_id build/parse (`chat-logger@a:<action>`).
- Placeholder substitution engine (Core-level) incl. escaping policy for user content.
- Template rendering to embed dict + Discord limit enforcement/truncation.

Needs Discord test doubles: message create/edit/delete gateway payloads (incl. webhook author, thread channel, uncached message), member fetch success/404, channel send, interaction responses (defer ephemeral, edit original, update message, deferred update), guild channel/category graph, guild leave.

---

## 14. Porting assessment — Medium

Reasons: small surface (1 command, 6 component IDs, 4 events) but stateful (SQLite + JSON), privacy-sensitive, and full of quirks that need explicit keep/fix decisions; discord.py's message-edit/delete events are cache-dependent, so raw events must be used.

Suggested discord.py mapping:
- `commands.Cog` with listeners `on_message`, `on_raw_message_edit` (JDA fires regardless of cache; discord.py `on_message_edit` only for cached messages), `on_raw_message_delete`, optionally `on_raw_bulk_message_delete` (currently not handled — decide), `on_guild_remove`.
- `app_commands.Group(name="chat-logger", default_permissions=Permissions(administrator=True), guild_only=True)` with subcommand `setting`; name/description localizations via an `app_commands.Translator`. Respond with `interaction.response.defer(ephemeral=True)` + `edit_original_response(...)` to mirror Core auto-defer.
- `discord.ui.View(timeout=None)` with `Button`s / `ChannelSelect(channel_types=[…], min_values=1, max_values=25)` using the exact custom_ids; register a persistent view or a global `on_interaction` prefix router (Core's routing model) so old ephemeral messages keep working after restart.
- Storage: `aiosqlite` (or `sqlite3` in an executor) for the message store; JSON files with atomic writes for settings.
- No `tasks.loop` needed (unless a retention job is added).

Risks: MESSAGE_CONTENT approval; behavior parity for embed extraction and update semantics; per-field 1024-char limit (truncation policy); placeholder engine parity (recursive substitution, `$` escape); deciding retention/privacy policy; migrating existing settings with the `allow_mode` ambiguity; Discord MESSAGE_UPDATE payload variations (unfurls/pins) [unverified].
