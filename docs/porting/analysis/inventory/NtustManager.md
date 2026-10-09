# NtustManager — porting inventory (branch `main`)

All paths are relative to `Plugins/NtustManager/src/main/kotlin/ntustmanager/` unless prefixed.
Core paths are relative to `Core/src/main/kotlin/core/`.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/NtustManager` (Gradle `:Plugins:NtustManager`, `build.gradle.kts`, convention `xs-plugin-shadow` → shaded jar `NtustManager-3.4.0-SNAPSHOT.jar`) |
| Kotlin files / LOC | 11 files / 1,874 physical lines (`wc -l`) |
| Package | `tw.xinshou.discord.plugin.ntustmanager` |
| Entry | `internal object Event : PluginEventConfigure<ConfigSerializer>(false, ConfigSerializer.serializer())` (Event.kt:6) |
| Listener flag | `false`. The plugin is never registered as a JDA listener. |
| Commands / components / events | None |

File breakdown (LOC): Event 43, NtustManager 286, announcement/AnnouncementCacheManager 328, AnnouncementModels 19, AnnouncementParser 335, AnnouncementScheduler 294, AnnouncementTypes 50, config/ConfigSerializer 26, service/GeminiApiService 271, util/HtmlMinifier 134, util/UrlUtils 88.

**Purpose:** a background poster with no user interaction. Every `fetch-interval` seconds it polls 18 hard-coded NTUST announcement boards: Student Affairs 學務處 ×6, Academic Affairs 教務處 ×5, and Language Center 語言中心 ×7. It diffs each board's page-1 list against the last stored list. For each new entry it fetches the article, extracts the main HTML container, minifies it, and asks Google Gemini (`gemini-2.5-flash`) to convert it to Discord Markdown. The result goes to a hard-coded Announcement (news) channel in a hard-coded guild (`1407404369753931826`), split into ≤2000-char messages.

**info.yaml** (`src/main/resources/info.yaml`, placeholders expanded by `build-logic/convention/src/main/kotlin/xs-jvm-conventions.gradle.kts:65-81`):
- `author: xinshoutw`, `name: NtustManager`, `coreApi: "3.4"`, `version: "3.4.0-SNAPSHOT"` (root `gradle.properties` major 3 / minor 4 / snapshot true; plugin `gradle.properties` `version.patch=0`).
- `main: "tw.xinshou.discord.plugin.ntustmanager.Event"`.
- Not set: `description`; `prefix` (defaults to the name); `component_prefix` (defaults to `ntustmanager@`, PluginLoader.kt:277-285, and Core logs "Plugin name ... is too long" because the name is longer than 10 chars); `require_intents`; `require_cache_flags`; `require_member_cache_policies`; `depend_plugins`; `soft_depend_plugins`; `depend_jars`; `soft_depend_jars`.

---

## 2. Lifecycle

### Event.load() (Event.kt:7-19)
1. `super.load()`, which does three things:
   - Exports `lang/`. This is a no-op because the plugin has no `lang/`.
   - Reads `plugins/NtustManager/config.yaml`, exporting the default from the jar if the file is missing (PluginEvent.kt:59-65).
   - Decodes the YAML with kaml in **strict mode**: unknown keys raise an error (kaml default `strictMode=true`).
2. Logs `Starting NTUST announcement monitoring system...`.
3. If `!config.enabled`, logs a warning `NtustManager is disabled.` and returns. **The `NtustManager` object is not touched.**
4. Logs `NtustManager loaded`, then calls `NtustManager.startSystem()`.

### First access to `object NtustManager` (NtustManager.kt:15-95)
The object initializer runs in declaration order:
1. `guild = jdaBot.getGuildById(1407404369753931826L)!!` (NtustManager.kt:21). If the bot is not in that guild, this raises an NPE, wrapped as `ExceptionInInitializerError`. That is an `Error`, so Core's `catch (e: Exception)` does not catch it (Main.kt:29) and the **whole bot fails to start**.
2. 18 `by lazy` channel getters `guild.getNewsChannelById(<id>)!!` (22-39). They are evaluated on first post per type.
3. `init {}` → `initializeComponents()` (77-95):
   - `AnnouncementCacheManager(Event.pluginName)`. This opens Mongo DB `NtustManager` and both collections as `MemoryCacheDb`, loading them fully and synchronously. It then calls `initializeCache()`.
   - `GeminiApiService(Event.config)`. **This captures the config object at init time.**
   - `validateConfiguration()`. If it returns false, it throws `IllegalStateException("Invalid Gemini API configuration")`, which fails startup.
   - `AnnouncementScheduler(cacheManager, gemini, ::handleNewAnnouncement)`. This captures `fetchInterval` at construction (AnnouncementScheduler.kt:22).
4. Commented-out one-time cleanup that deletes all history in every announcement channel (NtustManager.kt:46-63). This is dead code.

### startSystem() (NtustManager.kt:69-72)
Calls `scheduler.startScheduler()`, which runs `scheduleAtFixedRate(task, initialDelay=0, period=fetchInterval, SECONDS)` (AnnouncementScheduler.kt:120-132). **The first cycle runs immediately on startup.** The task body is `runBlocking { checkAllAnnouncements() }`, wrapped in a try/catch that logs `Error during scheduled announcement check`.

### Event.unload() (Event.kt:21-31)
1. `super.unload()` logs `NtustManager unloaded with default.`
2. Logs `Shutting down NTUST announcement monitoring system...`.
3. If config is initialized and enabled, calls `NtustManager.shutdown()`. That calls `scheduler.shutdown()`, which:
   - calls `executor.shutdown()`,
   - waits `awaitTermination(5s)` and otherwise calls `shutdownNow()`,
   - calls `coroutineScope.cancel()` (AnnouncementScheduler.kt:261-272).
4. Logs `NtustManager unloaded`.

### Event.reload() (Event.kt:33-43)
This is called by `BotLoader.reloadPluginStrict`, for example from the Web-Dashboard "live config apply" (CoreDashboardBackend.kt:208-224). If reload throws, the dashboard rolls back the file and reloads again.

1. `super.reload()` re-reads `config.yaml`.
2. If disabled: calls `NtustManager.shutdown()` and returns. If the object was never initialized, this **initializes it**: Mongo load, guild lookup, and Gemini validation all run, just to shut down.
3. If enabled: calls `NtustManager.startSystem()` again. See the reload bugs in §12.

### Background jobs
| Job | Mechanism | Interval | What it does |
|---|---|---|---|
| Announcement cycle | `Executors.newScheduledThreadPool(2)` (AnnouncementScheduler.kt:26) + `scheduleAtFixedRate` | `fetch-interval` s (default 3600, min 60); initial delay 0 | `checkAllAnnouncements()` across 18 boards |
| Per-board check | `CoroutineScope(Dispatchers.IO + SupervisorJob())` (29), `async` per board, `Semaphore(5)` created per cycle (140) | per cycle | `checkAnnouncementUpdates(board)` |
| Mongo writes | Core `CacheDbServer.dbScope.launch(IO)` from MemoryCacheDb (MemoryCacheDb.kt:64-104) | per mutation | fire-and-forget upsert/delete |

### Cycle algorithm (normative)

**`checkAllAnnouncements()`** (AnnouncementScheduler.kt:137-153) launches all 18 boards concurrently, with at most 5 at a time, and awaits all of them. Per-board exceptions are caught and logged as `Error checking announcements for <TYPE>`.

**`checkAnnouncementUpdates(board)`** (158-208):
1. `boardData = boardParser(board)`. If the result is empty, log `No announcements found for <TYPE>` and **return without changing state**.
2. Compute `valid` as the entries with a non-blank `title` and a non-blank `url` (214-228). If `valid` is empty, warn and return.
3. Call `compareAnnouncementLists(type, valid)` (AnnouncementCacheManager.kt:199-224):
   - It compares the URL set in memory with the new URL set.
   - `added` = the entries of `valid` whose URL is not stored. Board order is kept, and a URL that appears twice on the page appears twice here.
   - `removed` = the stored entries whose URL is no longer present.
4. If `removed` is non-empty, delete their `announcement_data` docs, keyed `<TYPE>_<paragraphId|url>` (AnnouncementCacheManager.kt:272-278).
5. If `added` is non-empty, run `processNewAnnouncements(added)` (234-256). It works **sequentially, in board order**. For each link:
   - `data = contentParser(link)`. If `null`, warn `Failed to parse announcement content ...` and skip.
   - `saveAnnouncementData(data)`. **This persists before posting.**
   - Call `handleNewAnnouncement(data)` to post to Discord.
   - Any exception is logged and the loop continues.
6. **Unconditionally** call `updateCurrentAnnouncementList(type, valid)`. This updates the memory map and does an async Mongo upsert. **Items that failed in step 5 are never retried**, because they are now part of the stored list.

**First-ever run, or empty cache:** the stored list is empty, so every entry currently on page 1 of every board counts as "added". All of them are fetched, sent through Gemini, and posted.

**`boardParser(board)`** (AnnouncementParser.kt:33-59):
- Sends `GET board.url` with the java.net.http client: 30 s connect timeout and 30 s request timeout (21-26, 38-42). No custom headers or User-Agent, no cookies, and **redirects are not followed** (Java default).
- A status other than 200 logs a warning `HTTP <code> for <url>` and returns `[]`. Any exception logs an error and returns `[]`.
- Otherwise it returns `parseAnnouncementList(Ksoup.parse(body), board)`.

**`parseAnnouncementList`** (108-210):
- **Language Center types:**
  - Rows are `div.row.listBS` (117).
  - For each row, the link is the first `div.d-item.d-title.col-sm-12 div.mbox div.d-txt div.mtitle a` (121). Rows without one are skipped.
  - `title = a.text().trim()` (jsoup `text()` normalizes and collapses whitespace).
  - `url = constructCompleteUrl(a.attr("href"), board.url)`.
- **Student and Academic types:**
  - Find the first `table.listTB.table` (147). If there is none, warn `No announcement table found for <TYPE>` and return `[]`.
  - Rows are `tbody tr` (154), cells are `td`, and rows with fewer than 2 cells are skipped.
  - The title cell is `cells[0]` for Student Affairs and `cells[1]` for Academic Affairs (160-169). The date cell is ignored.
  - The link is the first `a` in the title cell. Rows without one are skipped.
  - `STUDENT_MAIN_OFFICE` only: entries whose title does not start with `【處本部】` are skipped (182).
- Any exception returns `[]`.

**`contentParser(link)`** (67-102):
1. `UrlUtils.validateUrlType(link.url)`. If the URL is not `NTUST_ANNOUNCEMENT`, return `AnnouncementData(link, title=link.title, content=null, releaseDate=today)` with no HTTP call (UrlUtils.kt:81-88).
2. `GET` the URL with the same client settings. A non-200 status or an exception returns `null`.
3. Find the container: the first `div#Dyn_2_3.M23`, otherwise the first `div.M23` (227-229). If neither exists, warn and return `null`.
4. `html = HtmlMinifier.minify(container.outerHtml())`.
5. `content = gemini.processHtmlContentWithRetry(html, link)`. If it returns `null`, log an error and return `null`.
6. Return `AnnouncementData(link, title=link.title, content, releaseDate=LocalDate.now() "yyyy-MM-dd", fetchedTimestamp=now ms)`. Both branches (262-274) use today's date; the board's date column is never used.

---

## 3. Slash commands & context menus

**None.** There are no `guildCommands()` or `globalCommands()` overrides. The public helpers `NtustManager.getAllCurrentAnnouncementLists()`, `triggerManualCheck()` and `clearCache()` (NtustManager.kt:243-272) have **no callers anywhere in the repo** (verified by grep).

## 4. Components

None. There are no buttons, selects, modals or `ComponentIdManager` usage.

## 5. Events

None, because `listener=false`. All activity is outbound: HTTP scraping, Gemini calls and `sendMessage`.

---

## 6. Configuration (`plugins/NtustManager/config.yaml`)

`ConfigSerializer` is in config/ConfigSerializer.kt:6-26. The default file is at `src/main/resources/config.yaml`.

| Key | Type | Code default | Shipped default | Validation / use |
|---|---|---|---|---|
| `enabled` | Boolean | `false` | `false` | Gates load, start, reload and unload. |
| `fetch-interval` | Long (seconds) | `3600` | `3600` | When enabled, must be ≥ 60 (ConfigSerializer.kt:23). Used as the scheduler period, read once at construction. |
| `api-keys` | List<String> | **none, so the key is required even when disabled** | two copies of `sk-thisisatestkey1234567890abcdef1234567890` | When enabled: must be non-empty, and no entry may equal the placeholder key (17-20). `validateConfiguration()` also rejects any blank entry (GeminiApiService.kt:222). Duplicate keys share one rate-limit bucket. |
| `prompt` | String | **none, required** | Long Chinese template (config.yaml:8-105) | When enabled: must be non-blank (22). `validateConfiguration()` requires the substrings `{{page_url}}`, `{{base_url}}`, `{{now}}` and `{{html}}` (GeminiApiService.kt:230). `{{page_title}}` is optional. |

**Enabled-flag semantics:**
- With `enabled: false`, none of the validation in `ConfigSerializer.init` runs, but the keys `api-keys` and `prompt` must still exist, or kaml fails on the missing property.
- Any decode or validation exception in `load()` propagates through `PluginLoader.run()` (which has no try/catch, PluginLoader.kt:145-155) and aborts bot startup. The same applies to unknown YAML keys under kaml strict mode.

**Prompt template tokens.** These are the plugin's own `{{…}}` tokens, not Core `%…%` placeholders. `materializePrompt` (GeminiApiService.kt:120-128) replaces them sequentially:

| Order | Token | Replacement |
|---|---|---|
| 1 | `{{page_title}}` | `link.title` |
| 2 | `{{page_url}}` | `link.url` |
| 3 | `{{base_url}}` | `"https://" + extractDomainFromBaseUrl(link.url)` |
| 4 | `{{now}}` | `LocalDateTime.now()` formatted `yyyy-MM-dd HH:mm:ss`, in the JVM default time zone |
| 5 | `{{html}}` | the minified HTML |

The default prompt tells the model to:
- output only Discord Markdown;
- keep h1–h3 and turn h4–h6 into bold lines;
- make links absolute against `{{base_url}}` and strip `utm_*`/`ct` parameters;
- never use image syntax, writing `[圖片：…](URL)` instead;
- flatten tables to `**欄1｜欄2**` plus `• a｜b` lines;
- produce fenced code blocks with language detection;
- link the title as `# [標題](URL)`;
- output `*(無可轉換內容)*` when there is nothing to convert;
- stay **under 10,000 characters**.

**Hard-coded values that should become config in the port:**
- guild ID;
- 18 channel IDs;
- 18 board URLs;
- model `gemini-2.5-flash`;
- temperature `0.1`;
- 10 requests/min/key over a 60 s window;
- maximum of 10 retries and the backoff schedule;
- concurrency 5;
- HTTP timeouts of 30 s;
- message split sizes;
- the `【處本部】` filter.

---

## 7. Localization & templates

- No `lang/` resources, no `StringLocalizer`, no MessageCreator (v1 or v2), no Modal templates, no Core placeholders. The import list was verified.
- The only user-visible text is the posted announcement, built in code (NtustManager.kt:151-183):
  - `HEADER` = 15 × U+FF3F FULLWIDTH LOW LINE (`＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿`, line 152).
  - **When content is null** (external link, PDF, etc.), one message: `HEADER + "\n# [" + title + "](" + url.trim() + ")"`. There is no length check and the title is not escaped for Markdown.
  - **When content is non-null:** let `full = content.trim()`.
    - If `len(full) <= 1990 - 15 = 1975`, send one message: `HEADER + "\n" + full`.
    - Otherwise `segs = splitContentIntoSegments(content.trim(), 1980)`. Message 1 is `HEADER + "\n" + segs[0]`, and messages 2..n are `segs[i]` with no header.
    - In practice anything up to 1,980 chars still produces one message, of at most 1,996 chars.
- `splitContentIntoSegments` (105-142). The Kotlin default `maxLength = 1950` is never used; the caller always passes 1980. Exact algorithm:
  ```python
  def split(content, max_len):
      if len(content) <= max_len: return [content]
      segs, rem = [], content
      while len(rem) > max_len:
          cut = rem.rfind('\n', 0, max_len + 1)  # == Kotlin lastIndexOf('\n', max_len)
          end = cut if cut > 0 else max_len      # a newline at index 0 counts as "none"
          segs.append(rem[:end])
          rem = rem[end + 1:] if cut > 0 else rem[end:]   # drop the newline at the cut
      if rem: segs.append(rem)
      return segs
  ```
  Lengths are **UTF-16 code units** in Kotlin. Python `len()` counts code points, so the two differ for astral characters such as emoji. Pick one rule and pin it in tests.

---

## 8. Persistence

The store is embedded MongoDB, started by Core (`CacheDbServer`, Mongo 8.2, data dir `<cwd>/mongodb-data` or the `XS_MONGODB_*` env overrides, CacheDbServer.kt:38-41,128,155-171). The database name is the plugin name, **`NtustManager`** (AnnouncementCacheManager.kt:14). Both collections are `MemoryCacheDb` (`memoryCache = true`, lines 17-20):
- `get` and `loadAll` read from memory.
- `put` and `remove` update memory, then write to Mongo asynchronously with no ordering guarantee.
- `containsKey` and `count` are **not overridden**, so they query Mongo directly (MemoryCacheDb.kt; CacheCollectionManager.kt:91-109).

Core document envelope: `{ _id: <String key>, value: <BSON>, timestamp: <Int64 epoch ms of last write> }` (CacheCollectionManager.kt:31-38).

### Collection `current_announcement_lists` (the critical dedupe state)
- `_id` is an `AnnouncementType` enum name, for example `"STUDENT_DORMITORY"`.
- `value` is a Core `TypedListWrapper`, serialized by Moshi (CacheCollectionManager.kt:143-154):
  ```json
  {"_id":"ACADEMIC_COURSE",
   "value":{"items":[{"type":"ACADEMIC_COURSE","url":"https://www.academic.ntust.edu.tw/p/406-1048-138746,r1416.php?Lang=zh-tw","title":"..."}],
            "itemTypeName":"tw.xinshou.discord.plugin.ntustmanager.announcement.AnnouncementLink"},
   "timestamp":1759565000000}
  ```
  An empty list is stored as `"value":{"items":[]}`; Moshi omits the null `itemTypeName`.
- **What happens on restart:**
  - Core calls `Class.forName(itemTypeName)` from the Core class loader (CacheCollectionManager.kt:213). Plugin classes are not visible there, so the call fails and the items come back as `List<Map>`.
  - The plugin's "legacy" converter (AnnouncementCacheManager.kt:30-68, 105-109) rebuilds the objects from the `type`, `url` and `title` fields.
  - So the "legacy" path is in fact the normal path after every restart.
- Error handling on load:
  - An unknown `_id` enum name logs a warning and skips the entry, without deleting it.
  - An unknown `type` inside an item drops that item.

### Collection `announcement_data` (write-only archive)
- `_id` is `"<TYPE>_<paragraphId>"`. `paragraphId` is `/p/([^.]+)\.php` group 1, for example `406-1053-139292,r1436`. If that regex does not match, the full URL is used instead (AnnouncementCacheManager.kt:230-235).
- `value` is `AnnouncementData`, serialized by Moshi:
  ```json
  {"link":{"type":"STUDENT_DORMITORY","url":"https://student.ntust.edu.tw/p/406-1053-139292,r1436.php?Lang=zh-tw","title":"..."},
   "title":"...", "content":"<gemini markdown>", "releaseDate":"2026-10-08", "fetchedTimestamp":1759900000000}
  ```
  `content` is **omitted** when null.
- It is never read back: `getAnnouncementData` and `hasAnnouncementData` are unused. Entries are deleted when their URL drops off the board's page 1.

### Migration concerns
- **The port must import `current_announcement_lists`, or seed it without posting, before going live.** Otherwise the first cycle re-posts every page-1 item on all 18 boards (roughly 18 × page size).
- Dedupe identity is the **exact URL string**. Any change to URL shape, such as an added `?Lang=` parameter, causes a mass re-post.
- `announcement_data` can be dropped or kept for parity, since nothing reads it.

---

## 9. External dependencies

**Gradle** (`build.gradle.kts:5-8`, shaded into the plugin jar):
- `com.fleeksoft.ksoup:ksoup:0.2.5`, a jsoup port.
- `com.google.genai:google-genai:1.37.0`, the Google Gen AI Java SDK.

**HTTP endpoints.** All are GET, unauthenticated, via `java.net.http.HttpClient`. Students = `https://student.ntust.edu.tw/p/`, Academic = `https://www.academic.ntust.edu.tw/p/`, LC = `https://lc.ntust.edu.tw/p/` (AnnouncementScheduler.kt:32-115).

| Type | Board URL | Channel ID (AnnouncementTypes.kt:24-45) |
|---|---|---|
| STUDENT_DORMITORY 學生宿舍公告 | `…student…/403-1053-1436-1.php` | 1407406663752880261 |
| STUDENT_AID 助學措施 | `…student…/403-1053-1437-1.php` | 1407406688373575702 |
| STUDENT_GUIDANCE 生輔組 | `…student…/403-1053-1439-1.php` | 1407406727657296087 |
| STUDENT_ACTIVITY 活動組 | `…student…/403-1053-1440-1.php` | 1407406747148226634 |
| STUDENT_RESOURCE_ROOM 資源教室 | `…student…/412-1053-8272.php` (a "412" page, not a "403" list) | 1407406773589114963 |
| STUDENT_MAIN_OFFICE 學務處本部公告 | `…student…/403-1053-1435-1.php` (filter `【處本部】`) | 1409519988368347146 |
| ACADEMIC_MAIN_OFFICE 處本部公告 | `…academic…/403-1048-1413-1.php` | 1407406813460168776 |
| ACADEMIC_GRADUATE_EDUCATION 研教組公告 | `…academic…/403-1048-1414-1.php` | 1407406841826246666 |
| ACADEMIC_REGISTRATION 註冊組公告 | `…academic…/403-1048-1415-1.php` | 1407406862302712030 |
| ACADEMIC_COURSE 課務組公告 | `…academic…/403-1048-1416-1.php` | 1407406884180332554 |
| ACADEMIC_COMPREHENSIVE_BUSINESS 綜合業務組公告 | `…academic…/403-1048-1417-1.php` | 1407406911413948457 |
| LANGUAGE_CENTER_RECRUITMENT 語言中心徵才公告 | `…lc…/403-1070-1626-1.php` | 1407406935837245582 |
| LANGUAGE_CENTER_EXEMPTION_REWARD 抵免與獎勵 | `…lc…/403-1070-1627-1.php` | 1407406976681513092 |
| LANGUAGE_CENTER_HONOR_LIST 榮譽榜單 | `…lc…/403-1070-1051-1.php` | 1407406997049049249 |
| LANGUAGE_CENTER_FRESHMAN 新生相關公告 | `…lc…/403-1070-1628-1.php` | 1407407017185771600 |
| LANGUAGE_CENTER_ENGLISH_WORDS 英文單字 | `…lc…/403-1070-1828-1.php` | 1407407034030358699 |
| LANGUAGE_CENTER_EXTERNAL 校外公告 | `…lc…/403-1070-1829-1.php` | 1407407057992417400 |
| LANGUAGE_CENTER_ACTIVITY 活動公告 | `…lc…/403-1070-1050-1.php` | 1418253510864011304 |

The guild ID is **1407404369753931826** (NtustManager.kt:21). Only page 1 of each board is fetched, since every URL ends in `-1.php`. There is no pagination.

**Article pages:** any URL matching `^https://.*\.ntust\.edu\.tw/p/[0-9\-,r]+\.php.*$` (UrlUtils.kt:56, Kotlin `matches` = full match).

**URL helpers** (UrlUtils.kt):
- `extractParagraphId` uses `/p/([^.]+)\.php` (first match).
- `extractDomainFromBaseUrl` uses `https://([^/]+)` (first match) and falls back to `"ntust.edu.tw"`.
- `constructCompleteUrl(href, base)` (68-74):
  - an `https://…` href is kept as is;
  - a `/…` href becomes `"https://" + domain(base) + href`. A protocol-relative `//x` therefore becomes `https://domain//x`;
  - anything else is kept verbatim, including `http://…` and bare relative paths.
- `validateUrlType` (53-60): `NTUST_ANNOUNCEMENT` if the regex matches, else `RELATIVE_PATH` if the URL starts with `/`, else `THIRD_PARTY`. `RELATIVE_PATH` is effectively unreachable, because board links are already absolutized. Non-NTUST links, including NTUST PDFs or `/var/file/` URLs, are posted as a title link with `content=null`.

**Gemini** (service/GeminiApiService.kt):
- SDK `Client.builder().apiKey(key).build()` calls the Gemini Developer API with API-key auth. **A new `Client` is built for every attempt and never closed** (112-117).
- Request (131-150): `models.generateContent("gemini-2.5-flash", Content.fromParts(Part.fromText(prompt)), GenerateContentConfig{temperature=0.1})`.
- Response: the text of all parts of the **first candidate**, concatenated and trimmed. A blank result counts as `null`, which is a failed attempt.
- **Rate limiter** (client side, per key; 35-109):
  - Each key has a sliding window of timestamps; one is pruned when `now - t > 60_000`.
  - A key is usable if `window.size < 10`.
  - `findAvailableKey()` scans round-robin from `apiKeyIndex % n`, picks the first usable key, and sets `apiKeyIndex = idx + 1`.
  - Usage is recorded **before** the call.
- **Retry loop** (155-218), `maxRetries = 10`:
  - If no key is free, wait `calculateWaitTime()` without consuming an attempt. That value is the minimum over keys of `60000 - (now - oldest)`. It is 0 if some key has an empty list, and keys with no map entry are skipped. If the result is 0, sleep 1 s instead.
  - If a call fails or returns blank, the attempt counter increases and, if attempts remain, the loop sleeps:

    | After failed attempt | Sleep |
    |---|---|
    | 1 | 60 s |
    | 2 | 300 s |
    | 3 | 900 s |
    | 4 and later | 1800 s |

  - The worst case for **one** announcement is about 12,060 s (≈3 h 21 min) of sleeping. After 10 failures it logs `Gemini 2.5 Flash failed after 10 attempts` and returns `null`.
- **No plugin dependencies.**

---

## 10. Discord requirements

- **Intents:**
  - No privileged intent is needed by this plugin. It only needs the guild and channel cache, which Core's default gateway setup provides.
  - Core force-enables `GUILD_MEMBERS` (privileged), `SCHEDULED_EVENTS` and `GUILD_EXPRESSIONS` for every deployment (BotLoader.kt:68-72). That comes from Core, not from this plugin.
- **Cache flags / member cache:** none.
- **Bot permissions:** View Channel and Send Messages in the 18 target channels.
  - The channels **must be Announcement (news) channels**. `getNewsChannelById` returns null for a normal text channel, which leads to an NPE in `handleNewAnnouncement`. That is caught and logged per announcement (AnnouncementScheduler.kt:252-254), and the announcement is **already marked seen**.
  - JDA checks permissions on the client side, so missing permission throws synchronously and gets the same handling.
- **No crosspost/publish.** Posts in announcement channels are not published to following servers.
- **Allowed mentions are not restricted.** Nothing in the repo calls `setDefaultMentions` or `setAllowedMentions`, and the JDA 6.4.1 default parses all mention types (`AllowedMentionsData` static default = `EnumSet.allOf(MentionType)`, verified in the bundled jar). If Gemini output contains `@everyone` or a role mention, it would ping if the bot has the permission.
- **Rate-limit-sensitive operations:**
  - The first-run or cache-loss backfill posts every page-1 item.
  - Each long article becomes up to about 6 messages, because the prompt caps output at 10k chars.
  - Messages for one announcement are queued in order. JDA preserves per-route order.

---

## 11. Concurrency

- Each cycle runs on a `ScheduledThreadPoolExecutor(2)` thread that is blocked by `runBlocking`. A periodic task never overlaps itself, but **a second scheduled task**, added by reload, can run concurrently on the second thread.
- Boards run in parallel, up to 5 at a time, on `Dispatchers.IO`. A permit is held for the whole board, **including Gemini backoff sleeps of up to hours**, so 5 slow boards starve the rest of the cycle.
- `currentAnnouncementLists` is a `ConcurrentHashMap`. Each board type is touched by one coroutine at a time, unless the scheduler is duplicated.
- The Gemini limiter uses a `ReentrantLock` around each map access, but `findAvailableKey()` followed by `recordApiKeyUsage()` is not atomic, so concurrent boards can overshoot 10/min on a key slightly. `generateContent` is a blocking SDK call on IO threads.
- Mongo writes are fire-and-forget coroutines on Core's `dbScope`. Two writes to the same key may be reordered, and writes pending at shutdown may be lost.
  - Core closes Mongo **before** unloading plugins (Main.kt:31-33: `CacheDbServer.close()` runs before `BotLoader.stop()`).
- `shutdown()` waits 5 s and then interrupts. In-flight Gemini calls or sends may still finish after JDA has shut down.

---

## 12. Bugs, quirks, dead code, hard-coded values

**Behavior to preserve (or explicitly decide):**
1. **First cycle runs immediately at startup**; the period after that is `fetch-interval` (AnnouncementScheduler.kt:121-129).
2. Dedupe is a **page-1 snapshot diff by URL**, per board (AnnouncementCacheManager.kt:199-224).
3. New items in one board post **in board order**, which is usually newest first, so the channel shows them in reverse chronological order within a cycle (AnnouncementScheduler.kt:234-256, `filter` keeps order).
4. `STUDENT_MAIN_OFFICE` only keeps titles starting with `【處本部】` (AnnouncementParser.kt:182).
5. Non-NTUST-article links post as `HEADER\n# [title](url)` with no fetch and no Gemini call (UrlUtils.kt:81-88; NtustManager.kt:153-157).
6. The message format and split rules in §7, including the 15× U+FF3F header on the first message only.
7. `releaseDate` is always the fetch date. It is stored only and never shown.

**Probable bugs to fix (each needs a decision in the spec):**
1. **A failed item is never retried.** The list update at AnnouncementScheduler.kt:201 is unconditional, so items whose fetch, container lookup, Gemini call or send failed are permanently skipped.
2. **The item is saved before it is posted** (245 before 248). If the send fails, for example a null or non-news channel or missing permission, the item is still marked seen.
3. **Re-post risk:**
   - An item that drops off page 1 and later reappears is deleted from state and re-posted as new.
   - A transient partial page, non-empty but missing items, causes a mass re-post on recovery.
   - A URL repeated within one page is processed and posted twice (the `filter` keeps duplicates).
4. **Reload, enabled to enabled:** `startSystem()` schedules a second periodic task on the same executor (Event.kt:42 + AnnouncementScheduler.kt:121). The result is duplicate polling, possible concurrent processing of the same board, and duplicate posts.
5. **Reload, disabled then enabled:** the executor was shut down, so `scheduleAtFixedRate` throws `RejectedExecutionException`. The dashboard rolls back, and re-enabling requires a full restart.
6. **Reload ignores `api-keys`, `prompt` and `fetch-interval`.** They were captured at object init (NtustManager.kt:83; AnnouncementScheduler.kt:22).
7. **Reload while disabled initializes the whole object** (Mongo load, guild `!!`, Gemini validation) just to call `shutdown()` (Event.kt:36-38).
8. **Hard-coded guild and channel IDs with `!!`.** Enabling the plugin in any other deployment crashes startup with `ExceptionInInitializerError` (NtustManager.kt:21).
9. A Gemini backoff that can last hours blocks a semaphore slot and the whole cycle. Combined with `scheduleAtFixedRate` catch-up, the next cycles can start back to back.
10. A new Gemini `Client` is created on every attempt and never closed, which is a resource leak (GeminiApiService.kt:184).
11. The board fetch does not follow redirects, so any 3xx response leaves the board empty and logs a warning every cycle.
12. `constructCompleteUrl` does not absolutize bare relative hrefs (`foo.php`) and mangles protocol-relative `//host` hrefs (UrlUtils.kt:68-74).
13. The Markdown title is not escaped in the null-content message (`]` or `)` in the title breaks the link). There is no length guard: `setContent` throws if the result exceeds 2000 chars.
14. The warning at AnnouncementScheduler.kt:170-174 says "empty/missing content", but it actually counts entries with a blank title or URL.
15. `STUDENT_RESOURCE_ROOM` points at a `412-…` page. Whether that page has `table.listTB.table` is **unverified**; if it does not, the board yields nothing and logs a warning every cycle.

**Dead code:**
- `HtmlMinifier.minifyAggressive` and `validateHtml` (60-123).
- In `AnnouncementCacheManager`: `getAnnouncementData`, `hasAnnouncementData`, `removeUrlFromAnnouncementList` and `getCacheStats` (243-257, 285-300, 320-328).
- `AnnouncementScheduler.getSchedulerStats` and `triggerManualCheck`.
- `GeminiApiService.getApiStats`.
- `NtustManager.getAllCurrentAnnouncementLists`, `triggerManualCheck` and `clearCache`.
- The `UrlType.RELATIVE_PATH` branch.
- The `ClassCastException` branch in `initializeCache`.
- The commented-out channel purge (NtustManager.kt:46-63).

**Hard-coded values:** see §6 and §9. In addition, the time zone is the JVM default (`LocalDate.now()` and `LocalDateTime.now()`). Using Asia/Taipei explicitly is recommended.

---

## 13. Testability

There are no existing tests: `src/test/` contains only `.DS_Store`.

**Pure logic, unit-testable with fixtures:**
- `UrlUtils.extractParagraphId`, `extractDomainFromBaseUrl`, `validateUrlType`, `constructCompleteUrl`, and an external-link data factory with an injected clock.
- `HtmlMinifier.minify`. Port the exact regex sequence:
  1. `<!--[\s\S]*?-->` → `""`
  2. `>\s+<` → `"><"`
  3. `^\s+` (multiline) → `""`
  4. `\s+$` (multiline) → `""`
  5. `\s{2,}` → `" "`
  6. `\n\s*\n` → `"\n"`. This step is effectively a no-op after step 5.
  7. Trim.

  **Java `\s` is ASCII-only** (`[ \t\n\x0B\f\r]`), so use `re.ASCII` in Python. Otherwise U+3000 and NBSP common in Chinese pages get collapsed, which differs from the Kotlin output.
- `parseAnnouncementList(html, board)` against saved HTML fixtures for each of the three layouts, plus the `【處本部】` filter. Capture fixtures from the live sites.
  - Python must mimic jsoup `text()`: collapse whitespace runs and trim. Verify NBSP handling against the fixtures.
- Container extraction: `div#Dyn_2_3.M23`, with `div.M23` as the fallback.
- `compareAnnouncementLists`, the valid-entry filter, and the `processNew…` ordering and side-effect ordering.
- `createDiscordMessages` and `splitContentIntoSegments`: the boundaries at 1975, 1980 and 1981 chars, newline at index 0, no newline at all, and runs of consecutive newlines.
- `materializePrompt` with an injected clock.
- `validateConfiguration` and `ConfigSerializer` rules.
- Rate limiter and key rotation with an injected clock: window pruning `>` vs `>=`, `calculateWaitTime` edge cases, and round-robin index behavior.
- Backoff schedule as a pure function of the attempt number.
- Legacy and normal cache-document conversion: map-shaped items, unknown type, empty list, missing `itemTypeName`.

**Needs test doubles:**
- HTTP for the boards and articles (respx or aioresponses).
- Gemini client: a fake returning text, blank, or an exception.
- Discord: a channel registry fake (news channel present, missing, or wrong type) and a `send` recorder that checks order and content.
- Mongo, or a repository abstraction (mongomock or an in-memory store).
- Clock and sleep, so the hour-long backoffs can be tested without waiting.

---

## 14. Porting assessment

**Difficulty: Medium.**
- The core logic is small, and about 40% of the LOC is logging or dead code.
- The risk is in external contracts: three HTML layouts, LLM output, a key-rotating rate limiter with very long backoffs, Mongo document compatibility for the dedupe state, and hard-coded IDs.

**Suggested discord.py mapping:**
- A `commands.Cog` with **no app commands**.
- An `asyncio.Task` or `discord.ext.tasks.loop(seconds=fetch_interval)` started in `cog_load`. `tasks.loop` also runs its first iteration immediately. Change the interval on reload, or restart the loop, so the reload bugs are not inherited.
- `asyncio.Semaphore(5)` with `asyncio.gather(..., return_exceptions=True)` across boards.
- `httpx.AsyncClient` (timeout=30, `follow_redirects=False` for parity, or a deliberate True) with `selectolax` or `BeautifulSoup` (soupsieve supports all the selectors used).
- The `google-genai` Python SDK: `genai.Client(api_key=k).aio.models.generate_content(model=..., contents=prompt, config=GenerateContentConfig(temperature=0.1))`, then `resp.text`. Keep one client per key and reuse it.
- Storage: keep Mongo via `motor`/`pymongo` with the same document shapes (`_id`/`value.items[]`/`timestamp`), or migrate. Either way, carry over or seed the per-board URL lists before the first run.
- Channel lookup: `bot.get_channel(id)`; check `isinstance(ch, discord.TextChannel) and ch.is_news()` if parity with the "news only" rule is wanted.
- `await ch.send(content, allowed_mentions=AllowedMentions.none())` is recommended, which is a deliberate change. Optionally call `await msg.publish()`.
- Move guild, channel and URL mappings into config.

**Risks:**
- A mass re-post on cutover if the state is not migrated.
- LLM non-determinism: tests must stub Gemini.
- The `gemini-2.5-flash` model may be deprecated by Google, so make the model configurable.
- The school sites may change markup.
- Length semantics: UTF-16 in Kotlin vs code points in Python.
- Blocking or long-sleeping tasks during Cog unload must be cancellable.

---

## Appendix: scenario seeds (for OpenSpec / pytest)

- **First run, empty state:** every valid page-1 entry of every board is processed and posted. (State that this is the current behavior, then decide between keeping it and seeding.)
- A board returning a non-200 status or no entries leaves the stored list untouched.
- A new NTUST-article URL fetches the page, finds `div#Dyn_2_3.M23` (else `div.M23`), calls Gemini, posts `HEADER\n<markdown>`, and stores `<TYPE>_<paragraphId>`.
- A new external URL posts `HEADER\n# [title](url)` and makes no Gemini call.
- Content of 1,981+ chars splits at the last `\n` at or before index 1980 (exclusive of the newline). Only the first part carries the header.
- An entry no longer on page 1 has its `announcement_data` doc deleted. The board list is replaced by the new valid list even if processing failed.
- Gemini returning blank or raising consumes an attempt and sleeps 60 s, 300 s, 900 s, then 1800 s. After 10 attempts it returns null and the item is skipped permanently.
- When all keys have 10 uses in the last 60 s, the loop sleeps until the oldest use expires without consuming an attempt.
- Config with `enabled: true` and the placeholder key, a blank prompt, `fetch-interval < 60`, or a prompt missing `{{page_url}}`, `{{base_url}}`, `{{now}}` or `{{html}}` fails plugin load.
