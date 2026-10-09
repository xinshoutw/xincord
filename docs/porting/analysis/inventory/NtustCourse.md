# NtustCourse — porting inventory (branch `main`)

All paths are relative to `Plugins/NtustCourse/src/main/kotlin/ntustcourse/` unless prefixed.
Core paths are relative to `Core/src/main/kotlin/core/`.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/NtustCourse` (Gradle `:Plugins:NtustCourse`, **Groovy** `build.gradle` with `plugins { id("xs-plugin") }`, so the jar is not shaded: `NtustCourse-3.4.0-SNAPSHOT.jar`) |
| Kotlin files / LOC | 6 files / 407 physical lines: Event 62, NtustCourse 142, api/CourseApi 92, api/CourseMonitorService 76, command/Register 27, config/ConfigSerializer 8 |
| Package | `tw.xinshou.discord.plugin.ntustcourse` |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:14). Its KDoc says "RentSystem plugin", a copy-paste leftover. |
| Listener flag | `true`. Registered as a JDA listener; overrides only `onSlashCommandInteraction`. |

**Purpose:** a course-seat sniper for NTUST course selection.
- A coroutine polls the NTUST course query API **about every 1.5 s** for the full course catalogue of semester `1142`.
- Users register course codes per channel with slash commands.
- After a hard-coded go-live time (2025-12-26 09:00 local), the bot posts a mention message to each registering channel whenever a registered course is **not full**. This repeats on every poll; see §12.
- It posts a silent message when a course **becomes full**.

**info.yaml** (expanded):
- `author: xinshoutw`, `name: NtustCourse`, `coreApi: "3.4"`, `version: "3.4.0-SNAPSHOT"`.
- `main: "tw.xinshou.discord.plugin.ntustcourse.Event"`.
- Defaults: `prefix` = name; `component_prefix` = `ntustcourse@` (Core logs a "too long" warning because the name has 11 chars, PluginLoader.kt:280-282).
- No `require_intents`, cache flags, member-cache policies, dependencies or jars.

---

## 2. Lifecycle

**load()** (Event.kt:16-26):
1. `super.load()` reads or exports `plugins/NtustCourse/config.yaml` (kaml, strict).
2. If disabled, logs a warning `NtustCourse is disabled.` and returns.
3. Otherwise calls `NtustCourse.start()` and logs `NtustCourse loaded.`.

**First access to `object NtustCourse`** (NtustCourse.kt:15-20):
- `CacheDbManager(Event.pluginName)` opens Mongo DB `NtustCourse`.
- `recordCache = getCollection("generated_cache", memoryCache = true)`, a `MemoryCacheDb`. It loads the whole collection synchronously.
- `userRecordMap = ConcurrentHashMap<String, HashMap<Long, MutableList<String>>>()`.
- `monitorService = CourseMonitorService()`.

**`NtustCourse.start()`** (22-30):
1. `monitorService.start()`, which launches the poll loop (default semester `"1142"`).
2. `monitorService.subscribe("ALL") { processEvent(it) }`.
3. `recordCache.getTyped<HashMap<String, HashMap<Long, MutableList<String>>>>("user_record_map")`, then `putAll` into `userRecordMap` if non-null. **This always returns null; see §8.**

**unload()** (28-34): if config is initialized and enabled, calls `NtustCourse.stop()` (`job?.cancel()`). Then calls `super.unload()` and logs `NtustCourse unloaded.`.

**reload()** (36-47):
1. `super.reload()` re-reads the config.
2. If disabled: calls `NtustCourse.stop()` and warns. This initializes the object if it was never initialized.
3. If enabled: calls `stop()` then `start()`. Each `start()` adds **another `"ALL"` subscriber** (§12-1).

**guildCommands()** (49-55) returns `emptyArray()` when disabled, otherwise the three commands. Core collects these after load and reload and pushes them to **every guild** the bot is in (ListenerManager.kt:19-24, 32-35; BotLoader.kt:150-158).

**Background job.** `CourseMonitorService.start(semester = "1142")` (CourseMonitorService.kt:22-39):
- It creates a **new orphan** `CoroutineScope(Dispatchers.Default)` each time and launches a loop:
  ```
  while active:
      t0 = now_ms
      list = CourseApi.searchAllCourses(semester)   # [] on any failure
      if list non-empty: processUpdates(list)
      delay(max(100, 1500 - (now_ms - t0)))          # target ~1.5 s cadence, min 100 ms
  ```
- If `job` is active, `start()` is a no-op (line 23). `stop()` calls `job?.cancel()`.
- The scope has a plain `Job` and **no try/catch around `processUpdates`**. Any exception thrown by a subscriber kills the loop permanently until the next `start()`. See §12-4.

**In-memory state:**
- `userRecordMap`, which maps course code → channel ID → user IDs.
- `previousState: Map<CourseNo, Course>`, holding the last poll.
- `subscribers: ConcurrentHashMap<String, MutableList<(CourseEvent)->Unit>>`.

---

## 3. Slash commands & context menus

Defined in command/Register.kt:12-21. These are **guild commands**, registered by Core into every guild.

| Command | Options | Description |
|---|---|---|
| `course-add` | `id`: STRING, **required**, description `the course code to add` | `add a course` |
| `course-remove` | `id`: STRING, **required**, description `the course code to remove` | `remove a course` |
| `course-list` | none | `list all courses` |

Attributes common to all three:
- No subcommands or groups, choices, min/max length, or autocomplete.
- No `default_member_permissions`, so everyone can use them. Not NSFW.
- Guild-only implicitly, because they are guild commands.
- **No name or description localizations**: English only and hard-coded. There is no `lang/`.

**Routing** (Event.kt:57-61):
1. If `!config.enabled`, return.
2. If `GlobalUtil.checkSlashCommand(event, commandStringSet)` is true (it is true when `event.name` is **not** in `{course-add, course-remove, course-list}`, GlobalUtil.kt:49-50), return.
3. Otherwise call `NtustCourse.onSlashCommandInteraction(event)`.

**Response mechanics:**
- Core's `InteractionLogger` is registered before plugin listeners and calls `event.deferReply(true).queue()`, an **ephemeral** defer, for every slash command by default (`--auto-defer-interactions` default true; InteractionLogger.kt:25-30, Arguments.kt:34-41).
- The plugin **only** calls `event.hook.editOriginal(text)`, so **every reply is the ephemeral deferred response edited in place**.
- If Core auto-defer is disabled (`--no-auto-defer-interactions`), every reply fails because the interaction was never acknowledged.

**Common pre-checks** (NtustCourse.kt:32-41, in this order):
1. `!event.isFromGuild` → `This command can only be used in guilds.` This is effectively unreachable for guild commands.
2. `!event.channelType.isMessage` → `This command can only be used in text channels.`
   - JDA 6.4.1 `isMessage` is true for TEXT, PRIVATE, VOICE, GROUP, NEWS, STAGE and all thread types. This was verified by disassembling `ChannelType` in the bundled JDA 6.4.1.
   - So voice-chat, stage, news and thread channels **pass** the check, but break notifications later (§12-4).

**`/course-add id:<X>`** (58-67):
1. `courseId = option("id").asString`, verbatim: **no trim, no case normalization, no existence check**.
2. Append `userId` (String) to `userRecordMap[X][channelId]`, creating the levels as needed. **Duplicates are allowed**, so the same user can appear twice.
3. `recordCache.set("user_record_map", userRecordMap)`.
4. Reply `You have registered this course.` (always).

**`/course-remove id:<X>`** (69-76):
1. Run `userRecordMap[X]?.remove(channelId)?.remove(userId)`. **This removes the whole channel entry for course X, unregistering every user in that channel.** The trailing `.remove(userId)` acts on the detached list and has no effect (line 73).
2. Persist with the same call as `/course-add`.
3. Reply `You have unregistered this course.`. It is always sent, even if nothing was registered.

**`/course-list`** (78-92):
- For each `(courseId, channelMap)`, for each entry `e` in `channelMap[currentChannelId]`, add `courseId` if `e.contains(userId)`.
  - That check is a **String substring test**: the loop variable is misnamed `userIdList` but holds individual user-ID strings (lines 84-85).
- Only the **current channel's** registrations are considered. A duplicate registration lists the course twice.
- Reply `Your registered courses: ` + `courseIds.joinToString(", ")`. With no registrations, the reply ends in a trailing space and nothing else.

There is no error handling. An exception leaves the ephemeral "thinking…" state until Discord times it out.

---

## 4. Components

None. There are no buttons, selects or modals.

## 5. Events

- `onSlashCommandInteraction` only, as described in §3.
- Outbound only: `TextChannel.sendMessage` from the poll loop, described below.

**Poll → event generation** (CourseMonitorService.kt:51-76):
```
currentMap = associateBy(newList, CourseNo)      # last duplicate wins
for (id, new) in currentMap:
    old = previousState.get(id)
    if not new.isFull:                     notify(Available(new))          # LEVEL-triggered: every poll
    if old and not old.isFull and new.isFull: notify(BecameFull(new, old.currentCount))   # EDGE-triggered
previousState = currentMap
notify(id, ev): subscribers[id]* then subscribers["ALL"]*   # only "ALL" is ever subscribed
```
- `isFull` is `currentCount >= limit`, where `limit = Restrict2.toIntOrNull() ?: 0` (CourseApi.kt:42-43).
- A non-numeric or empty `Restrict2` therefore means limit 0, so the course is always full and **never** produces an `Available` event.

**`processEvent`** (NtustCourse.kt:94-138):
1. If `userRecordMap` is empty, return.
2. `now = LocalDateTime.now()` in the JVM default time zone. If `now < 2025-12-26T09:00`, return (lines 97-100).
3. **`Available(course)`:**
   - For each `(channelId, userIds)` in `userRecordMap[course.id]` (an exact, case-sensitive key match), get `ch = jdaBot.getGuildChannelById(channelId) as TextChannel?`. Skip if it is null; **throw `ClassCastException` if it is not a `TextChannel`**.
   - Send this content:
     ```
     "{now.second} ||<@u1> <@u2> …||\n[Course Available: {course.name}](https://courseselection.ntust.edu.tw/First/A06/A06) \n```\n{course.id}\n```"
     ```
     with `mentionUsers(userIds)`, so only those users are pingable. `now.second` is 0–59 without padding. The mentions sit inside a spoiler, and spoilered mentions still ping.
4. **`BecameFull(course, prevCount)`:**
   - The same channel loop and cast.
   - Content: `"Course Became Full: {course.name} ({course.id})"` with `mentionUsers(userIds)`. The content has no mention tokens, so **nobody is pinged**. `prevCount` is unused.
5. Sends use `.queue()`, which is fire-and-forget. The poll loop never waits for Discord.

---

## 6. Configuration (`plugins/NtustCourse/config.yaml`)

| Key | Type | Default (code / shipped) | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` / `false` | Gates load, reload, command registration and command handling. |

That is the whole schema (config/ConfigSerializer.kt:5-8). Under kaml strict mode, unknown keys fail the decode.

**Hard-coded values that should become config:**

| Value | Location |
|---|---|
| Semester `"1142"` | CourseMonitorService.kt:22 |
| Poll target 1500 ms, minimum sleep 100 ms | :35 |
| API URL `https://querycourse.ntust.edu.tw/QueryCourse/api//courses` (note the `//`) | CourseApi.kt:52 |
| Test-server URL `https://querycourse.xinshou.tw/querycourse/api/courses`, commented out | :53 |
| Connect timeout 5 s | :57 |
| Go-live gate 2025-12-26 09:00 local | NtustCourse.kt:99 |
| Course-selection link `https://courseselection.ntust.edu.tw/First/A06/A06` | :115 |

---

## 7. Localization & templates

None. There is no `lang/`, no `StringLocalizer`, no MessageCreator or ModalCreator, and no Core `%placeholders%`. Every user-visible string is a hard-coded English literal (quoted in §3 and §5).

---

## 8. Persistence

Storage is embedded Mongo (Core), DB **`NtustCourse`**, collection **`generated_cache`** (`MemoryCacheDb`), a single document:
```json
{"_id":"user_record_map",
 "value":{"CS1001301":{"1407406663752880261":["270062130470846465","810822763601461318"]}},
 "timestamp":1766710800000}
```
- Shape: `value[courseId][channelId as string][] = userId string`. Moshi writes the Long channel keys as JSON names, which was verified locally with Moshi (`{"CS1001301":{"123456789012345678":["111","222"]}}`).
- Writes:
  - `MemoryCacheDb.upsert` stores the **live map object** in its memory cache.
  - It then asynchronously serializes `ConcurrentHashMap → Moshi(Any) → Document.parse` (CacheCollectionManager.kt:140-161).

**Load is broken; registrations do not survive a restart:**
- After a restart, the cached value is a BSON `Document`.
- `getTyped<HashMap<…>>` (ICacheDb.kt:92-112) asks Moshi for an adapter for `java.util.HashMap<String, HashMap<Long, List<String>>>`. Moshi only supports the collection *interfaces*, so it throws `IllegalArgumentException: No JsonAdapter for java.util.HashMap… you should probably use Map instead of HashMap`. This was reproduced locally with Moshi 1.12. The factory semantics are unchanged in 1.15.x, which the project uses.
- `getTyped` swallows the error and returns `null`, so the map starts empty.
- The next `/course-add` or `/course-remove` then **overwrites** the old document with only the post-restart registrations.
- Within one process, reload does not lose data, because the singleton map stays in memory.

**Migration:**
- The document is plain nested BSON, so a Python port can read it directly. It may contain older registrations, since it is overwritten only on the first mutation after each restart.
- Course codes are user-controlled and used as Mongo field names. Codes containing `.` or starting with `$` may break writes (unverified). In the port, validate the code against something like `^[A-Z0-9]+$`, or use an array-of-records schema.

---

## 9. External dependencies

- **Gradle:** none beyond Core. The plugin uses Core's Moshi (`moshi-kotlin`) through class-loader delegation.
- **HTTP endpoint** (CourseApi.kt:68-92):
  - `POST https://querycourse.ntust.edu.tw/QueryCourse/api//courses`.
  - Java `HttpClient` with **HTTP/2 preferred**, connect timeout 5 s, **no request/read timeout** (a stalled server blocks the poll loop indefinitely).
  - Header `content-type: application/json; charset=utf-8`. No auth, cookies or custom User-Agent.
  - Request body (Moshi, constructor order):
    ```json
    {"Semester":"1142","CourseNo":"","CourseName":"","CourseTeacher":" ","Dimension":"","CourseNotes":"","CampusNotes":"","ForeignLanguage":0,"OnlyGeneral":0,"OnleyNTUST":0,"OnlyMaster":0,"OnlyUnderGraduate":0,"OnlyNode":0,"Language":"zh"}
    ```
    `CourseTeacher: " "` (a single space) is the trick that returns all courses (comment at line 70). `OnleyNTUST` is the API's own misspelling and must be kept.
  - Response: a JSON array of objects. These fields are read; unknown fields are ignored:

    | Field | Type | Notes |
    |---|---|---|
    | `CourseNo` | String | → `id` |
    | `CourseName` | String | → `name` |
    | `ChooseStudent` | Int, required | enrolled count |
    | `Restrict2` | String, required | the cap. A JSON number is also accepted, because Moshi's `nextString` takes numbers. |
    | `CourseTeacher` | String? | — |

  - Moshi uses `KotlinJsonAdapterFactory` via `addLast` (CourseApi.kt:60-62). `@JsonClass(generateAdapter=true)` is present but no codegen is configured; the reflective factory falls back to reflection when the generated class is missing (verified in the moshi-kotlin source).
  - Failure modes, all handled the same way: non-200 status, IO error, JSON error, or a missing or null required field. Each returns `[]`, logs only via `println("請求失敗: …")` to stdout, and that poll is skipped.
- **Plugin dependencies:** none.

---

## 10. Discord requirements

- **Intents:** none beyond Core defaults. Slash commands need none, and the guild channel cache comes from the default gateway setup. Nothing privileged is used by this plugin.
- **Cache flags / member cache:** none.
- **Bot permissions** in each registered channel: View Channel and Send Messages. JDA checks these on the client side and throws synchronously, which kills the poll loop (§12-4).
- **Commands:** the application must be allowed to create guild commands in every guild, because Core pushes them everywhere.
- **Rate-limit-sensitive behavior:**
  - The school API is polled about every 1.5 s with a full-catalogue request: roughly 40 requests per minute, or about 57,600 per day.
  - After the gate, **one message per poll per registered available course per channel**. That exceeds Discord's per-channel send limit (about 5 per 5 s), so JDA's queue backlog grows without bound.

---

## 11. Concurrency

- Commands run on JDA event threads, while `processEvent` runs on `Dispatchers.Default`.
- Both share `userRecordMap`. The outer map is concurrent, but the inner `HashMap` and `ArrayList` are not. Iterating them in `processEvent` while a command mutates them can throw `ConcurrentModificationException` inside the poll loop, killing it (§12-4).
- The async Mongo serialization reads the same live map, so a CME there loses the write.
- `subscribers` is a concurrent map holding non-thread-safe lists. A reload-time `subscribe` can race with `notifySubscribers` iteration.
- `previousState` is a non-volatile `var`, touched only by the poll coroutine.
- Each `start()` uses a fresh orphan scope. `stop()` cancels only the tracked job. The blocking `client.send` inside `withContext(IO)` is not interruptible, so cancellation takes effect after the in-flight request returns.

---

## 12. Bugs, quirks, dead code, hard-coded values

**Behavior to preserve (or decide):**
- Commands, option names, the ephemeral reply semantics, and the exact reply strings (§3).
- `BecameFull` is edge-triggered and silent. `Available` messages include the masked course-selection link and the course code in a code block for copying.
- Registrations are scoped per channel; the notification goes to the channel where the user registered.
- `isFull` semantics, including a non-numeric cap counting as full.

**Probable bugs to fix:**
1. **Duplicate subscriber on every reload-while-enabled** (Event.kt:45-46 + NtustCourse.kt:24). Each reload doubles every notification.
2. **`/course-remove` unregisters all users in the channel** for that course (NtustCourse.kt:73).
3. **Persistence never loads** (§8), so registrations are lost on restart and the old document is overwritten.
4. **The poll loop dies permanently** on any exception inside `processEvent`:
   - `ClassCastException` when a registered channel is not a `TextChannel` (news, thread, voice or stage chat, all of which `/course-add` accepts) (NtustCourse.kt:108, 127);
   - `InsufficientPermissionException` from `sendMessage`;
   - `ConcurrentModificationException` (§11).
   There is no try/catch and no supervisor (CourseMonitorService.kt:25-38).
5. **`Available` is level-triggered** (CourseMonitorService.kt:58-60), so the alert is re-sent about every 1.5 s while seats exist. The `"{now.second} "` prefix suggests repeated messages were expected, but combined with Discord rate limits this produces an unbounded backlog. **Decision needed:** edge-trigger with a cooldown, or keep it level-triggered with a throttle.
6. `/course-list` uses substring matching (`String.contains`) instead of equality (84-85). Duplicates are allowed on add (63-64).
7. Course codes are case- and whitespace-sensitive with no validation. A typo silently never matches.
8. The `isFromGuild` check is dead for guild commands. The `isMessage` check is too permissive (see 4).
9. There is no request timeout (CourseApi.kt:55-58,77-81). Errors go to stdout via `println` (89).
10. The time gate and semester are hard-coded and already stale: gate 2025-12-26, semester 1142, while today is 2026-10-08. Polling runs even before the gate, and even when nobody is registered.
11. `CourseMonitorService.subscribe(courseNo)` per-course subscriptions are never used; only `"ALL"` is subscribed (NtustCourse.kt:24).

**Dead code:**
- `CourseEvent.BecameFull.previousCount` is unused.
- `Course.teacher` is unused.
- The commented-out test-server URL.

---

## 13. Testability

There are no existing tests: `src/test/` contains only `.DS_Store`.

**Pure, unit-testable:**
- `Course.limit` and `isFull` parsing for `Restrict2` values such as `"40"`, `""`, `"abc"`, and a JSON number.
- `processUpdates` as a pure function `diff(prev_state, new_list) -> list[Event]`:
  - first poll;
  - full to not full;
  - not full to full;
  - a duplicate `CourseNo`;
  - limit 0.
- The registration store operations (add, remove, list), covering both the current buggy behavior (if parity tests are wanted) and the fixed behavior.
- Message builders for `Available` and `BecameFull`, with an injected clock for `now.second`.
- The time gate, with an injected clock and time zone.
- Request payload serialization (exact JSON keys, including `OnleyNTUST`).
- Response parsing, with fixtures for valid, missing-field, null-field and non-array responses.
- Mongo document round-trip `{course:{channel:[user]}}`.

**Needs test doubles:**
- HTTP (respx or aioresponses).
- Discord `Interaction`: check that `response.defer(ephemeral=True)` and `edit_original_response(content=…)` are called with the exact strings.
- A channel registry and `send` recorder (text channel, missing, wrong type, missing permission).
- A clock and sleep for the 1.5 s cadence.
- The persistence layer.

---

## 14. Porting assessment

**Difficulty: Low.** The code is small; the real work is the behavior decisions in §12.

**Suggested discord.py mapping:**
- A `commands.Cog` with three `app_commands.command`s (`course-add`, `course-remove`, `course-list`, each `id: str` with a description), registered as guild commands in every guild. Use `tree.copy_global_to(guild)` and sync per guild, or define them as global with `guild_only=True`, which is a deliberate change.
- Each handler calls `await interaction.response.defer(ephemeral=True, thinking=True)`, or relies on a Core-level auto-defer, then `await interaction.edit_original_response(content=...)`.
- The poll loop is an `asyncio.Task`, or `tasks.loop(seconds=1.5)` with a manual sleep adjustment, using `aiohttp`/`httpx` (HTTP/2 via `httpx[http2]` if parity is wanted) with an explicit total timeout.
- Wrap each iteration in `try/except Exception` so the loop never dies.
- Notification:
  - `channel = bot.get_channel(id)`; check `isinstance(channel, discord.abc.Messageable)` rather than casting.
  - `await channel.send(content, allowed_mentions=discord.AllowedMentions(users=[discord.Object(u) for u in ids], everyone=False, roles=False))`.
  - Add a per-channel throttle.
- Persistence: keep the Mongo document shape (motor/pymongo), or move to a simple JSON/SQLite store with a one-time import.
- Make semester, gate, cadence and API URL config keys.

**Risks:**
- Hammering the school API: confirm the acceptable rate.
- Discord rate limits from the level-triggered alerts.
- Global vs per-guild command registration differences in discord.py.
- Restoring old registrations that users believed were lost.
- The semester rolls over every term.
