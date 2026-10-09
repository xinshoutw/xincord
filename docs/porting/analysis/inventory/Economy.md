# Economy: porting inventory (branch `main`)

Paths below are relative to `/Users/xinshou/IdeaProjects/XsDiscordBotKt/Plugins/Economy/src/main/` unless they start with `Core/`.

Verification notes:
- The JSON formats below were produced by running the project's own data classes through Moshi 1.12.0 + `KotlinJsonAdapterFactory` in a scratch harness. The project uses Moshi 1.15.2; the field layout is the same.
- JDA behaviour (e.g. `OptionMapping.getAsInt`) was checked against the bytecode of JDA 6.4.1, bundled in `DevServer/Core-*.jar`.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/Economy` |
| Kotlin files / LOC | 11 files, 1182 lines (1015 non-blank): `Economy.kt` 203, `command/Register.kt` 204, `Event.kt` 174, `storage/JsonImpl.kt` 173, `storage/SheetImpl.kt` 156, `MessageReplier.kt` 69, `UserData.kt` 69, `command/CmdFileSerializer.kt` 59, `config/ConfigSerializer.kt` 42, `storage/IStorage.kt` 23, `json/JsonData.kt` 10 |
| Resources | 24 files: `config.yaml`, `info.yaml`, `lang/{en-US,zh-TW}/register.yaml`, `lang/{en-US,zh-TW}/message/*.yaml` (10 per locale) |
| Purpose | Per-guild virtual wallet. Each user has two integers: **money** (balance) and **cost** (cumulative spending). Configured admins can add/remove/set either. `/balance` shows the values. Leaderboards rank by money or by cost. Data is stored as one JSON file per guild, and there is a one-time migration from the old single-file format |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`kotlin/economy/Event.kt:26`) |
| Listener flag | `true` |
| Other objects | `Economy` (routing and handlers), `MessageReplier` (templates), `JsonImpl` (active storage), `SheetImpl` (Google Sheets storage; **dead code**), `UserData`, `DataContainer` |
| Build | `id("xs-plugin")` plus `compileOnly(project(":Plugins:API:GoogleSheetAPI"))`. `version.patch=0` → `3.4.0-SNAPSHOT` |

`info.yaml` after build-time expansion:
```yaml
author: xinshoutw
name: Economy
coreApi: "3.4"
version: 3.4.0-SNAPSHOT
main: "tw.xinshou.discord.plugin.economy.Event"
component_prefix: "economy@"
depend_plugins:
  - "GoogleSheetAPI"      # HARD dependency: Economy is not loaded if this plugin jar is absent
```
No `require_intents`, `require_cache_flags`, `require_member_cache_policies`, `soft_depend_plugins` or `depend_jars`.

## 2. Lifecycle

**`load()`** (`Event.kt:31-68`):
1. `super.load()`: exports `lang/` if missing, then reads `plugins/Economy/config.yaml`.
   - The `ConfigSerializer` init block validates `port in 1..65535`, `admin_id` non-empty and `board_user_show_limit in 1..25` (`config/ConfigSerializer.kt:37-41`).
   - This validation runs **even when `enabled: false`**. A violation throws, which aborts the whole bot.
2. If `!enabled`: warn `"Economy is disabled."` and return.
3. `MODE` is hard-coded to `Mode.Json` (`Event.kt:28`). The `Mode.GoogleSheet` branch is unreachable.
4. `migrateLegacyDataFileIfNeeded()` runs (see §8).
5. `JsonImpl.jsonGuildFileManager = JsonGuildFileManager(File(pluginDirectory,"data"), moshiAdapter<MutableMap<String,DataContainer>>, defaultInstance = mutableMapOf())`.
   - This loads **every** `data/*.json` eagerly and immediately re-saves each one.
   - A `*.json` whose stem is not a `Long` throws `NumberFormatException`, so the load fails (`Core/.../json/JsonGuildFileManager.kt:14-18`).
6. `storageManager = JsonImpl`.
7. `StringLocalizer(default = CHINESE_TAIWAN)` for `register.yaml`. The locale is hard-coded.
8. `storageManager.init()` builds the in-memory per-guild maps and boards. `sortMoneyBoard()` and `sortCostBoard()` then run, redundantly.

**`reload()`** (`Event.kt:74-111`): same as `load()`, plus `MessageReplier.reload()` to rebuild the v2 `MessageCreator`. The `JsonGuildFileManager` is recreated, which re-reads and re-saves all files, and `guildDataMap` is rebuilt.

**`unload()`**: only logs. Nothing needs flushing because every mutation is saved immediately.

**Background jobs:** none.

**In-memory state:**
- `JsonImpl.guildDataMap: HashMap<Long guildId, GuildData>`, where `GuildData` = `{ userData: HashMap<Long userId, UserData>, moneyBoard: ArrayList<UserData>, costBoard: ArrayList<UserData> }` (`storage/JsonImpl.kt:18-24`).
- `jsonGuildFileManager.mapper: Map<Long guildId, JsonFileManager>`.
- The Core per-user `Placeholder` substitutors, which receive `economy_*` keys.

For existing users, `UserData.data` **is the same `DataContainer` instance** as the map value inside the `JsonFileManager`. Mutations therefore hit the file model directly, before `save()` runs.

## 3. Slash commands

All nine are **guild commands** returned by `guildCommands()` when enabled (`Event.kt:113-119`).
- Routing: `Event.onSlashCommandInteraction` checks enabled and `event.name ∈ commandStringSet` (`command/Register.kt:11-21`).
- `Economy.onSlashCommandInteraction` then dispatches: `event.guild == null` → silent return (`Economy.kt:20`); names starting with `top-` → leaderboard; `balance`; otherwise money/cost mutation (`Economy.kt:19-32`).
- No NSFW flags, no autocomplete, no choices, no min/max values.

**Localization source:**
- `lang/<loc>/register.yaml`, with top keys `balance`, `top-money`, `top-cost`, `add-money`, `remove-money`, `set-money`, `add-cost`, `remove-cost`, `set-cost`.
- They are flattened through Kotlin property names: `balance.*`, `topMoney.*`, `topCost.*`, `addMoney.*`, `removeMoney.*`, `setMoney.*`, `addCost.*`, `removeCost.*`, `setCost.*` (`Register.kt:23-94`).

| Command (base) | Base description | Options (all `USER` "member" / `INTEGER` "value") | default_member_permissions | en-US name / description | zh-TW name / description |
|---|---|---|---|---|---|
| `balance` | Get current money from member | `member` USER **optional** ("Specify the member to query.") | `ENABLED` (everyone) | balance / get current balance detail from member | 金錢 / 取得成員金錢紀錄 |
| `top-money` | Get leaderboard for money | none | ADMINISTRATOR | top-money / get board from money | 餘額排行 / 取得餘額排行 |
| `top-cost` | Get leaderboard from log money | none | ADMINISTRATOR | top-cost / get board from cost | 消費紀錄排行 / 取得消費紀錄排行 |
| `add-money` | Add money to member's balance | `member` USER required ("Specify the member to modify."); `value` INTEGER required ("Specify the amount to add.") | ADMINISTRATOR | add-money / add money to member | 增加餘額 / 增加成員餘額 |
| `remove-money` | Remove money from member's balance | member req; value req ("Specify the amount to remove.") | ADMINISTRATOR | remove-money / remove money from member | 移除餘額 / 移除成員餘額 |
| `set-money` | Set money to member's balance | member req; value req ("Specify the new balance.") | ADMINISTRATOR | set-money / set money to member | 設定餘額 / 設定成員餘額 |
| `add-cost` | Add money log to member | member req; value req ("Specify the amount to add.") | ADMINISTRATOR | add-cost / add cost to member | 增加消費紀錄 / 增加成員消費紀錄 |
| `remove-cost` | Remove money log to member | member req; value req ("Specify the amount to remove.") | ADMINISTRATOR | remove-cost / remove cost from member | 移除消費紀錄 / 移除成員消費紀錄 |
| `set-cost` | Set money log to member | member req; value req ("Specify the new balance.") | ADMINISTRATOR | set-cost / set cost to member | 設定消費紀錄 / 設定成員消費紀錄 |

Option localizations (every command):
- `member`: en-US `member`/`who`; zh-TW `成員`/`誰`.
- `value`: en-US `value`/`how much`; zh-TW `金額`/`多少`.

**Two independent permission layers:**
1. Discord `default_member_permissions` (ADMINISTRATOR on 8 commands). Server admins can override this in the Integrations settings.
2. The plugin's own **admin list**: `invoker.id ∈ config.admin_id`, a global list of user IDs that is not per-guild (`Economy.kt:185-198`). A Discord admin who is not in `admin_id` gets the "no-permission" embed.

**Response mode.** Every response is `event.hook.editOriginal(...)` of the Core auto-deferred (`deferReply(true)`) interaction. **All Economy responses are therefore ephemeral.** The plugin never calls `event.reply` and breaks if Core auto-defer is disabled.

### `/balance [member]` (`Economy.kt:62-71`)
1. `target = invoker` if the invoker is not in `admin_id`. Otherwise `target = member option ?: invoker`. A non-admin's `member` option is **silently ignored**.
2. `query(guild, target)`. If the target has no record in this guild, one is created (`{"cost":0,"money":0}`) and **the guild file is saved**, so a read creates data (`JsonImpl.kt:128-141`).
3. Set the target's user placeholders `economy_money` and `economy_cost`.
4. Edit the original response to the `balance` embed rendered with the **target's** user substitutor.

### `/top-money`, `/top-cost` (`Economy.kt:42-53`, `MessageReplier.kt:44-68`, `JsonImpl.kt:90-120`)
1. Invoker not in `admin_id` → edit to the `no-permission` embed.
2. Render the template (`top-money` / `top-cost`) to get author, title and footer. Copy that embed and reset its description to `""`.
3. `count = min(boardSize, board_user_show_limit)`. For `i in 1..count`, append `parse(descriptionTemplate)` with `%index%` = i, `%name_mention%` = `<@userId>` and `%economy_board%` = money or cost.
   - These keys are written into the **invoker's** cached user substitutor (mutation).
4. **Board order:** descending by money or cost, using a stable sort.
   - Ties keep their previous list order. The initial order is the iteration order of a Java `HashMap<Long, UserData>`, and new users are appended. Tie order is therefore effectively unspecified.
   - All users that have a record are listed, including those at 0.
   - An empty board yields an embed with no description.
5. If the guild has no file yet, `getGuildData` creates `data/<guildId>.json` = `{}`.

### `/add-money | /remove-money | /set-money | /add-cost | /remove-cost | /set-cost` (`Economy.kt:73-139`)
1. Invoker not in `admin_id` → `no-permission` embed. This check runs **before** the value is read.
2. `value = getOption("value", 0) { it.asInt }`.
   - JDA 6.4.1 `getAsInt()` is `Math.toIntExact(getAsLong())`. A value outside int32 (Discord allows ±2^53) throws **`ArithmeticException`, which is uncaught**, so the user gets no response.
3. `value < 0` → edit original to the plain text **`Bad Value`** (not localized; `Economy.kt:174-179`). `0` is accepted.
4. `target = member option ?: invoker`. Admins always get here, and `member` is required.
5. Load the record (creating it if new), then mutate it using **Kotlin `Int` arithmetic (silent 32-bit wrap-around on overflow)** (`UserData.kt:21-68`):
   - `add-money`: `money += v`
   - `remove-money`: `money -= v; cost += v` (spending moves money into cost; money can go negative)
   - `set-money`: `money = v`
   - `add-cost`: `cost += v`
   - `remove-cost`: `cost -= v` (can go negative)
   - `set-cost`: `cost = v`
6. `saveData`: write the whole guild file. Then set placeholders:
   - always `economy_money` and `economy_cost`;
   - plus `economy_money_before` for add-/set-money;
   - plus both `economy_money_before` and `economy_cost_before` for remove-money;
   - plus `economy_cost_before` for add-/remove-/set-cost.
7. Edit the original response to the embed template named exactly like the command.
8. Re-sort `moneyBoard` and/or `costBoard`. Note that **every guild** is re-sorted.

## 4. Components

| custom_id | Producer | Who can use | Behaviour |
|---|---|---|---|
| any string starting with `economy@` (the prefix from `info.yaml`; no fields are parsed) | **None in this repo.** A repo-wide grep finds `economy@` only in `info.yaml`, so such buttons must come from hand-made or external messages | anyone | See the steps below (`Economy.kt:34-39, 55-60`) |

Button behaviour:
1. If the button is outside a guild, return without acknowledging, so the user sees "This interaction failed".
2. Otherwise call `deferReply(true)`. Then, on the JDA callback thread:
   - load or create the **clicker's** record in this guild (saving the file if new);
   - set the placeholders;
   - edit the ephemeral response to the `balance` embed.
3. There is no expiry.

No select menus, modals or text inputs.

## 5. Events

| JDA event | Filter | Behaviour |
|---|---|---|
| `onSlashCommandInteraction` | enabled; `event.name ∈ commandStringSet` | §3 |
| `onButtonInteraction` | enabled; `componentId.startsWith("economy@")` | §4 |

There is no `GuildLeaveEvent` handling. Data for guilds the bot has left is kept forever.

## 6. Configuration (`config.yaml`)

| Key | Type | Code default | Shipped value | Validation | Used for |
|---|---|---|---|---|---|
| `enabled` | Boolean | `false` | `false` | none | Gates load, commands and handlers |
| `client_id` | String | `""` | `"xxx.xxx.com"` | none | Sheets mode only (dead) |
| `client_secret` | String | `""` | `"xxx-xxx-xxx"` | none | Sheets mode only (dead) |
| `port` | Int | `8888` | `8888` | `1..65535` (always checked) | Sheets OAuth local receiver (dead) |
| `sheet_id` | String | `""` | `"ABCDEFG123456"` | none | Sheets only |
| `sheet_label` | String | `""` | `"Economy"` | none | Sheets only |
| `sheet_range_id` | String | `""` | `"A2:A"` | none | Sheets only |
| `sheet_range_money` | String | `""` | `"B2:B"` | none | Sheets only |
| `sheet_range_cost` | String | `""` | `"C2:C"` | none | Sheets only |
| `admin_id` | List<Long> | `[]` | `[810822763601461318, 270062130470846465]` | **must be non-empty** (always checked) | Plugin-level admin allow-list for all commands except `/balance`. It also decides whether the `member` option is honoured |
| `board_user_show_limit` | Int | `10` | `10` | `1..25` (always checked) | Leaderboard length |

- The shipped file contains long English and Chinese comment blocks describing Google OAuth setup (with reurl.cc links).
- Kaml runs in strict mode, so unknown keys are fatal.
- A validation failure throws during plugin load, and that **aborts the whole bot** (`Core/.../Main.kt:21-38`), even though the plugin may be disabled.

## 7. Localization and templates

- **Locales:** `en-US`, `zh-TW`. **Default and fallback: zh-TW**, hard-coded (`Event.kt:59,102`; `MessageReplier.kt:14-24`).
- **Files:** `lang/<loc>/register.yaml` and `lang/<loc>/message/{add-cost,add-money,balance,no-permission,remove-cost,remove-money,set-cost,set-money,top-cost,top-money}.yaml`.
- **Engine:** Core **v2** `MessageCreator` reading v1-shaped YAML (one embed each; no components).
- **Locale selection:** the user's locale if a directory exists for it, else zh-TW. A missing key inside an existing locale throws; there is no per-key fallback.

Shared embed elements:
- **Author icon:** every author has `icon_url: https://i.imgur.com/PsEXCuY.png`.
- **Footer:** every footer is `❖ ORDERLY SERVER ❖`.
- **Fields:** all non-inline.
- **Colour:** none, except `no-permission`, which is `#FF0000`.
- **Title:**
  - user templates: `☛ %user_name%'s Pocket` (en) / `☛ %user_name% 的口袋` (zh);
  - `top-money`: `☛ Money Board` / `☛ 餘額`;
  - `top-cost`: `☛ Cost Board` / `☛ 總消費`;
  - `no-permission`: `You have no permission ><` / `你沒有權限 ><`.
- **Currency suffix:** `$` (en) or `元` (zh).

| Template | Author (en / zh) | Fields: name = value (en; zh uses 餘額/總消費 and 元) |
|---|---|---|
| balance | Pocket Query / 口袋查詢 | Balance = `%economy_money% $`; Cost = `%economy_cost% $` |
| add-money | Pocket Add Balance / 口袋增值 | Balance [+] = `%economy_money_before% ➣ %economy_money% $`; Cost = `%economy_cost% $` |
| remove-money | Pocket Reduce Balance / 口袋扣款 | Balance [-] = `%economy_money_before% ➣ %economy_money% $`; Cost [+] = `%economy_cost_before% ➣ %economy_cost% $` |
| set-money | Pocket Set Balance / 口袋餘額設定 | Balance [=] = `…money_before% ➣ %economy_money% $`; Cost = `%economy_cost% $` |
| add-cost | **Pocket Add Balance** (copy-paste) / 口袋增值 | Balance = `%economy_money% $`; Cost [+] = `%economy_cost_before% ➣ %economy_cost% $` |
| remove-cost | **Pocket Reduce Balance** / 口袋扣款 | Balance = `%economy_money% $`; Cost [-] = `…cost_before% ➣ %economy_cost% $` |
| set-cost | Pocket Set Cost / 口袋總消費設定 | Balance = `%economy_money% $`; Cost [=] = `…cost_before% ➣ %economy_cost% $` |
| no-permission | Pocket Failed / 口袋失敗 | (none; red) |
| top-money / top-cost | Pocket Board / 口袋排行榜 | description template `%index%.\t%name_mention%\n%economy_board% $\n\n` (zh: `… 元\n\n`). The YAML `\t` and `\n` are real tab and newline characters |

**Placeholders defined by the plugin:**
- `economy_money` and `economy_cost`, set on the per-user cached substitutor by `Placeholder.update(user, …)` (`Economy.kt:141-155`).
- `economy_money_before` and `economy_cost_before`.
- `index`, `name_mention` and `economy_board`, used on the leaderboard.

**Core placeholders used:** `user_name` (= `User.name`, the unique username, not the display name). The others available are `user_id`, `user_mention`, `user_avatar_url`, `bot_id` and `bot_name`.

The cached user substitutor is **global across guilds**, keyed by user ID. It is refreshed immediately before each use, so the values shown are correct.

## 8. Persistence

**Active storage: JSON, one file per guild** (Core `JsonGuildFileManager` + `JsonFileManager`, Moshi).
- **Path:** `plugins/Economy/data/<guildId>.json`. The bot's working directory is the base.
- **Schema:** `{ "<userId as decimal string>": { "cost": <int32>, "money": <int32> }, ... }`.
- **Example** (Moshi output: compact, field order `cost` then `money`, key insertion order kept):
  ```json
  {"852521987557556284":{"cost":990,"money":0},"270062130470846465":{"cost":0,"money":1500}}
  ```
- **In memory:** see §2. Users whose key is not a `Long` are skipped in memory (`key.toLongOrNull()`) but **kept in the file**.
- **Write semantics:**
  - Every new record and every mutation rewrites the whole guild file with `File.writeText`. This is non-atomic: truncate then write.
  - Every file is also rewritten at load.
  - `IOException` on save is logged and swallowed (`Core/.../json/JsonFileManager.kt:100-113`).
- **Read semantics** (I verified each case with Moshi):
  - Quoted numbers such as `"cost":"7"` are accepted.
  - Unknown fields are ignored.
  - Any of the following raises `JsonDataException`:
    - a missing `cost` or `money`;
    - `null`;
    - a non-integer such as `1.5`;
    - a value beyond int32, such as `3000000000`.
- **Data-loss behaviour.** On any read error (malformed JSON, `JsonDataException`, IO), `JsonFileManager` falls back to `{}` **and immediately overwrites the file** (`JsonFileManager.kt:29-39, 41-67`). Combined with non-atomic writes, a crash mid-write followed by a restart wipes that guild's data.
- **Records are created by reads:** `/balance`, the button, and admin commands that target new users. A guild file is created by any command that touches the guild.
- **No deletion path:** there are no per-user deletions and no guild cleanup.

**Legacy migration** (`Event.kt:133-173`). It runs at every `load()` and `reload()`, before the file manager is created:
```
legacy = data/data.json
if not exists(legacy): done
if any regular file in data/ with extension "json" and a Long-parsable stem:      # e.g. "123.json", "-1.json"
    backup(legacy); warn("...moved to backup because guild json files already exist."); done
guilds = JDA guild cache (after awaitReady; unavailable guilds are not counted)
if len(guilds) == 1:
    if rename(legacy -> data/<thatGuildId>.json): info("Migrated ...")
    else: warn(...); backup(legacy)
    done
backup(legacy); warn("...could not be auto-mapped (guild count: N)...")
backup(f): delete data/data.legacy.bak if it exists; rename f -> data/data.legacy.bak (rename result ignored)
```

- **Legacy format.** The legacy `data.json` has exactly the per-guild schema; the old code used `JsonFileManager(File("data/data.json"))` (commit `b16ce46`).
- **No merge.** With 0 or 2+ guilds, legacy data is not merged; it is parked in `data.legacy.bak` and needs manual recovery.
- **Repeated backups overwrite each other.** Every run that takes a backup branch deletes the previous `data.legacy.bak` first. The successful single-guild rename branch does not touch the `.bak`.
- **Crash if the backup rename fails.** If `renameTo` fails, `data.json` stays, and `JsonGuildFileManager` then crashes on `"data".toLong()`, aborting startup.

**Dead storage: Google Sheets (`SheetImpl`).**
- **Layout:** one global sheet, not per guild; `guildId` is ignored (`SheetImpl.kt:32-55`). Columns are `sheet_label!A2:A` (user id), `B2:B` (money), `C2:C` (cost).
- **Writes:** `values.append`/`values.update` with `valueInputOption=RAW` and rows `["<id>","<money>","<cost>"]`.
- **Reads are broken.** Each row (a `List`) is turned into a string and then parsed as `Long` (`it.toString().toLong()` on `"[123]"`, `SheetImpl.kt:146-155`), so every read would throw `NumberFormatException`. This is my inference from the Google client type `List<List<Object>>`; it is not executed.
- **Initialisation:** the OAuth installed-app flow runs at `SheetImpl` object initialisation, so the first touch blocks for browser consent.

**Not used:** MongoDB (`CacheDbManager`, `MemoryCacheDb`, `DirectCacheDb`) and SQLite.

## 9. External dependencies

- **Gradle:** `compileOnly(project(":Plugins:API:GoogleSheetAPI"))`. At runtime that plugin's shadow jar provides `google-api-client 2.8.1`, `google-oauth-client-jetty 1.39.0`, `google-api-services-sheets v4-rev20251110-2.0.0` and `jackson-databind 2.21.0`.
- **Plugin dependency:** **hard `depend_plugins: [GoogleSheetAPI]`**. Economy refuses to load without it, even though JSON mode never uses it. The only call sites are `SheetsService(ConfigSerializer(clientId, clientSecret, port), pluginDirectory).sheets.spreadsheets().values()` (`SheetImpl.kt:20-22`) and the subsequent `get`/`batchGet`/`append`/`update`.
- **HTTP (JSON mode):** none. In Sheets mode (dead): Google OAuth2, with a local Jetty receiver on `localhost:<port>` and tokens in `plugins/Economy/tokens/`, plus the Sheets API v4.
- **Credentials:** `client_id` and `client_secret` in `config.yaml` (Sheets only).
- **Static asset:** `https://i.imgur.com/PsEXCuY.png`, the author icon in all templates.

## 10. Discord requirements

- **Privileged intents:** none needed by this plugin.
- **Cache flags:** none. **Member cache:** none. The USER option is resolved from the interaction payload.
- **Bot channel permissions:** none. Every response goes through the interaction webhook (ephemeral).
- **Requests per command:** 1 defer (Core) + 1 webhook edit. The button costs 1 defer + 1 edit.
- **Hot path:** disk I/O, because the whole guild file is rewritten per mutation. There is no Discord rate-limit concern.

## 11. Concurrency

- **Slash commands** run sequentially on the JDA gateway thread (Core sets no event pool).
- **The button path** does its work inside `deferReply(true).queue { … }` (`Economy.kt:36-38`), on JDA's callback pool. So `JsonImpl`'s `HashMap`/`ArrayList` structures, the Moshi map inside `JsonFileManager` and the `DataContainer` fields can be touched concurrently from two threads.
  - `JsonFileManager.save()` is `@Synchronized` per file, but the mutations are not.
  - Possible results: `ConcurrentModificationException` during `toJson` or sort, and lost updates.
- **Read-modify-write is not atomic.** This only matters with the callback-thread overlap.
- **Placeholder substitutor cache:** Core's plain `HashMap`, mutated from both threads.

## 12. Bugs, quirks, dead code

Probable bugs or risks to fix:
1. **int32 overflow wraps silently** (`UserData.kt:22,33-34,50,55`): `2147483647 + 1` gives `-2147483648`, and that is persisted.
2. **An out-of-range INTEGER option** (|v| > 2^31-1) throws `ArithmeticException` in `asInt`, so there is no response (`Economy.kt:78`).
3. **Corrupt or invalid files are silently replaced by `{}`** (Core). Writes are non-atomic, so a crash can lead to total data loss for a guild.
4. **Reads create records** (`/balance` on a new user saves a zero record), which inflates leaderboards with zero entries.
5. **The hard dependency on GoogleSheetAPI** is never used in the hard-coded JSON mode (`Event.kt:28`, `info.yaml:11-12`).
6. **Config validation runs while disabled.** An empty `admin_id` or a bad `port`/`board_user_show_limit` aborts the whole bot, even with `enabled: false`.
7. **`economy@` buttons have no producer in the repo.** The handler is reachable only from externally crafted messages (`Economy.kt:34-39`).
8. **The legacy migration heuristic** (single guild gets everything; otherwise backup) parks data when the bot is in 0 or 2+ guilds. The `.bak` file is overwritten on the next run, and a failed rename crashes startup.
9. **`/balance member:` from a non-admin silently shows the invoker's own balance**, with no message saying the option was ignored (`Economy.kt:185-188`).
10. **Leaderboard tie order is unspecified** (HashMap order plus a stable sort).
11. **`Bad Value` is not localized** and is plain content (`Economy.kt:177`).
12. **en-US template copy-paste:** `add-cost` uses author "Pocket Add Balance" and `remove-cost` uses "Pocket Reduce Balance".
13. **`event.guild == null` leaves the deferred interaction unresolved** (`Economy.kt:20`). Unreachable for guild commands.
14. **Concurrency hazards** from the button callback thread (§11).
15. **Sheets mode is broken and not guild-aware** (§8). It is dead because `MODE` is constant.

Behaviour to preserve (unless the spec says otherwise):
- **Separate wallets per guild.**
- **Two permission layers:** Discord ADMINISTRATOR defaults plus the config `admin_id` allow-list.
- **Non-admins can only see their own balance.**
- **`remove-money` semantics:** money goes down and cost goes up.
- **0 is allowed; negative input is rejected** with `Bad Value`.
- **Balances may go negative.**
- **All responses are ephemeral.**
- **Leaderboard format and limit:** default 10, range 1-25.
- **zh-TW is the fallback locale.**
- **The on-disk JSON format**, needed for data import.

Dead code:
- `SheetImpl` and `Mode.GoogleSheet`.
- The `IStorage.init()` implementation in `SheetImpl`.
- The return values of `UserData.add*/remove*/set*`.
- The `sortMoneyBoard()`/`sortCostBoard()` calls after `init()`, which already sorted (`Event.kt:64-65`).
- No TODO or FIXME comments.

## 13. Testability

Pure functions to extract:
- **`resolve_target(invoker_id, member_option, admin_ids) -> user_id`** and **`is_admin(invoker_id, admin_ids)`**.
- **`validate_value(raw_int) -> int | Error`.** Covers the negative case, and the int32 range if kept.
- **`apply_op(op, money, cost, v) -> (money, cost, before_values)`.** Use int32 wrap semantics if preserved, or reject overflow.
- **`build_board(records, kind, limit) -> list[(rank, user_id, value)]`.** Define a deterministic tie-break in the spec, e.g. by user id.
- **`render_board_description(template, rows)`.**
- **Repository:** `load_guild(path) -> dict`, `save_guild(path, dict)` (atomic write), `get_or_create(guild, user)`.
- **`migrate_legacy(data_dir, guild_ids) -> Action`.** One test per branch: no legacy file; numeric json files exist; exactly 1 guild with the rename succeeding or failing; 0 or ≥2 guilds; an existing `.bak`.
- **JSON parsing compatibility:** quoted ints, extra fields, non-numeric keys preserved, and invalid files (must not be wiped in the port).

Needs Discord doubles:
- An interaction with an already-deferred ephemeral response (`edit_original_response`).
- The user option resolution.
- `userLocale`.
- The button interaction (defer plus edit).

## 14. Porting assessment

**Difficulty: Medium.** The command logic is simple and mechanical. Most of the work is in:
- the on-disk format and the legacy migration semantics;
- deciding which quirks to keep (int32 wrap, read-creates-record, tie order, non-admin option ignored, hard GoogleSheetAPI dependency);
- the dual permission model.

discord.py mapping:
- **Commands:** a `commands.Cog` with 9 `@app_commands.command`s, registered per guild.
  - Use `@app_commands.default_permissions(administrator=True)` on 8 of them and `@app_commands.guild_only()`.
  - Option types: `member: discord.User`, and `value: int`. Optionally `app_commands.Range[int, 0, 2**31-1]` to let the client enforce the range. Doing so changes the observable "Bad Value" path for negative values, so put it in the spec.
- **Localizations:** a `Translator` backed by `register.yaml`.
- **Responses:** `await interaction.response.defer(ephemeral=True)` (or rely on the ported Core auto-defer), then `edit_original_response(embed=…)`.
- **Storage:** a small repository class per guild with an `asyncio.Lock` and atomic writes (`tempfile` + `os.replace`). Keep the file layout `plugins/Economy/data/<guildId>.json`, or import it into a new store.
- **Migration:** a one-shot step on startup after `on_ready`, so the guild count is known.
- **Button:** if it must be kept, use a `ui.DynamicItem[ui.Button]` with template `economy@.*`, or an `on_interaction` listener that checks the `custom_id` prefix. Register it in `setup_hook`.
- **Drop SheetImpl and the GoogleSheetAPI dependency**, or make it soft. That is a behaviour change at the plugin-loading level.

Risks:
- Data loss during migration if the port also wipes unparseable files.
- Python's unbounded `int` silently changes overflow semantics.
- Concurrent writes if handlers are spread over threads. Keep everything on the event loop.
