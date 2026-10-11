## Context

v3's NtustCourse (`Plugins/NtustCourse`, 6 Kotlin files, 407 lines), which the owner renamed
NtustCourseWatch, is a JDA listener for three guild slash commands (`Event.kt:49-61`,
`command/Register.kt:12-28`) with a background job. `Event.load()` reads `config.yaml` (`enabled`
only, `ConfigSerializer.kt:5-8`) and starts `NtustCourse`, which subscribes `processEvent` to
`CourseMonitorService` and tries to load its registrations from MongoDB (`NtustCourse.kt:22-30`).
The monitor asks NTUST's course query for the whole catalogue of semester `1142`
(`CourseApi.kt:68-92`; `CourseTeacher: " "` returns every course) about every 1.5 seconds
(`CourseMonitorService.kt:22-39`), turns each course that is not full into an `Available` event at
every poll and each course that was not full and now is into a `BecameFull` event (`51-76`). From
2025-12-26 09:00 local time (`NtustCourse.kt:97-100`) `processEvent` posts to each channel that
registered the course: the available alert pings the channel's registered members in a spoiler,
with the course-selection link and the code in a code block; the full alert pings nobody
(`102-137`). `/course-add`, `/course-remove` and `/course-list` edit the core's ephemeral deferral
with fixed English texts (`32-92`). The inventory is
`docs/porting/analysis/inventory/NtustCourse.md`; its section 12 lists the behavior to preserve and
11 probable bugs.

## Goals / Non-Goals

**Goals:** v3's commands, options, replies and alert texts; registrations per channel; v3's
`isFull` (a cap that is not a number counts as 0); level alerts with a mention per registered
member and an edge alert when a course fills; v3's polling interval as the default; the semester and
the go-live time in config (C1); the inventory's bugs fixed; a loop that ends with the plugin; logs
that do not flood.

**Non-Goals:** v3's dead code (per-course subscriptions, `previousCount`, `Course.teacher`, the
commented-out test server URL, the `isFromGuild` and `isMessage` checks); the v3 data import itself;
the Web Dashboard (B13).

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/ntust_course_watch/`: `__init__.py` (metadata and
  `setup`), `config.py` (the model), `courses.py` (pure: course codes, the request body, the
  answer, v3's `isFull`), `store.py` (the registrations document), `alerts.py` (pure: the alerts'
  texts, their mentions and their throttle), `web.py` (aiohttp: the course query), `watch.py` (one
  step of the loop), `cog.py` (the commands, the loop and the posts), `config.yaml` and `lang/`.
  Entry point `NtustCourseWatch = "xincord.plugins.ntust_course_watch"`; `migrate_v3.RENAMED`
  already maps `NtustCourse` to it and moves v3's `plugins/NtustCourse/` there.
- `INTENTS = discord.Intents.none()`: slash commands need no intent and the alerts go through
  partial messageables, which need no cache. `DEPENDS` and `SOFT_DEPENDS` are empty, as in v3's
  `info.yaml`. No component IDs: v3 had no components (its derived `ntustcourse@` prefix was
  unused).
- `lang/en-US/` holds v3's English texts, verbatim, and is the default locale, because every v3
  text was English: `register.yaml` (the names and descriptions) and `text.yaml` (the replies and
  the alerts, with `%ncw@...%` placeholders). `lang/zh-TW/` translates them (the skill's rule for
  texts that v3 hard-coded in one language, as Ticket's). Command names and the option name stay
  v3's in every locale (both `register.yaml` files repeat them), so members type the same commands.
- The bundled `config.yaml` holds v3's values with comments: the plugin loads as it is, and the
  `--no-online` and image checks need no example values.

### NTUST's TLS context, shared

- `xincord.plugins.ntust_tls` (a package without an entry point, as `xincord.plugins.failures`):
  `ntust_context()`, NtustAnnouncements' `web.page_context` moved unchanged (certificates and host
  names verified, `VERIFY_X509_STRICT` cleared, TWCA's intermediate loaded), and
  `twca-secure-ssl-ca.pem` moved with it. NtustAnnouncements imports it; its tests of the context
  stay in its `test_web.py`. `querycourse.ntust.edu.tw` fails the strict checks too (HANDOFF,
  2026-10-11).

### Config

- `Config(Model)` with kebab-case keys, like NtustAnnouncements' (v3 had only `enabled`, which now
  only warns): `semester` (letters and digits, 1 to 16, `1142` by default; the model sets
  `coerce_numbers_to_str`, so an unquoted `1151` is the text `1151`, as TicketAwayNotice's
  `prefix`), `start` (pydantic's `AwareDatetime`, `2025-12-26T09:00:00+08:00` by default: v3 compared
  `LocalDateTime.now()` with 2025-12-26 09:00 on the owner's host in Taiwan, and a time without its
  offset would be read in the container's UTC), `interval` (`float`, 1 to 86400, 1.5 by default)
  and `alert-interval` (`float`, 10 to 86400, 60 by default). Floats refuse infinities and NaN.
- Every key has v3's value as its default, so v3's file (`enabled: false`) loads unchanged and
  behaves as v3 did; the bundled file holds the same values with comments that ask the operator to
  set the semester and the start for each course selection.
- `interval`'s minimum is 1 second: with one request per step, the plugin never asks NTUST more
  than once a second (v3: once every 1.5 seconds at most, with a far heavier request).

### Course query

- v3 asked for the whole catalogue (`CourseTeacher: " "`) every 1.5 seconds. On 2026-10-11 that
  request for semester `1151` got no answer in 60 seconds, then a 500 (`{"Message": "..."}`) after
  120 seconds; asking for one code (`CourseNo`, which the site matches as a prefix) answered in
  under a second. The plugin therefore asks about the registered codes only, one request per step:
  the request is light for NTUST, and a course's state comes within `interval` times the number of
  registered codes.
- `courses.query_body(semester, code)`: the body that the course query site sends today
  (`app.cbe19373.js`, 2026-10-11), in its order: `Semester`, `CourseNo` (the code), `CourseName`,
  `CourseTeacher` and `Dimension` empty, `CourseNotes` and `CampusNotes` empty strings,
  `ForeignLanguage`, `OnlyIntensive`, `OnlyGeneral`, `OnleyNTUST` (the API's spelling, kept),
  `OnlyMaster`, `OnlyUnderGraduate` and `OnlyNode` 0, `Language` `zh` (course names in Chinese, as
  v3). It is compact JSON, sent with `content-type: application/json; charset=utf-8`.
- `web.Api.course(semester, code)`: `POST https://querycourse.ntust.edu.tw/QueryCourse/api//courses`
  (v3's URL, with its `//`), no redirect followed (Java's `HttpClient` followed none), a 5-second
  connect timeout (v3's) and a 30-second total (v3 had none, so a stalled answer stopped the loop),
  TLS through `ntust_context()`. A status other than 200 raises `QueryError`; the text is read as
  UTF-8 with replacement characters.
- `courses.read_course(answer, code)`: the answer must be a JSON array (`AnswerError` otherwise);
  the entries whose `CourseNo` is the code (the site's prefix match returns others too, and lists a
  course twice) give the course, the last one winning as v3's `associateBy`; that entry needs text
  `CourseName`, an integer `ChooseStudent` and a `Restrict2` that is text or a number
  (`AnswerError` otherwise); other entries are not read, so one malformed course no longer fails
  every course (v3: the whole poll). No entry: the course is unknown.
- `Course.limit` is `Restrict2` read as Kotlin's `toIntOrNull()` (a sign and decimal digits of any
  script in the BMP, since Kotlin's strings are UTF-16, within 32 bits), else 0; a number counts as its JSON text, as Moshi's `nextString` read it
  (60 is `"60"`, 60.0 is `"60.0"`, 0). `full` is `ChooseStudent >= limit`, so a cap of 0 or text is
  always full, as in v3.

### Registrations and the v3 data import

- `store.py`: namespace `NtustCourseWatch`, key `user_record_map` (v3's `_id`), value v3's
  document: `{"<code>": {"<channel ID>": ["<user ID>", ...]}}`, IDs as decimal text (Moshi wrote
  the channel's `Long` keys as JSON names and the user IDs as strings). Reading checks the shape
  (an object of objects of lists of decimal strings, channel keys decimal) and raises `DataError`
  otherwise; a member listed twice (v3 allowed it) counts once. Codes are read as `/course-add`
  reads them, since v3 stored them as typed: codes that read as one are merged, and those that are
  no course code (empty, too short, a course's name) are left out, so the loop never asks about
  them, and the next change writes the document without them.
- `add`, `remove` and `forget` (a channel) run under `store.lock("NtustCourseWatch:user_record_map")`
  with `get`, then `put` only when something changed; a course or channel left without members is
  dropped, and the document is deleted with its last registration. A broken document raises and is
  left as it is.
- v3's registrations never survived a restart (`getTyped` asked Moshi for a `HashMap` adapter and
  got null), and the next change overwrote the document with the registrations made since; the
  store keeps them across restarts.
- **v3 data to import:** v3's embedded MongoDB, database `NtustCourse`, collection
  `generated_cache`, document `{"_id": "user_record_map", "value": {...}, "timestamp": <epoch
  ms>}`. The import puts `value` under namespace `NtustCourseWatch` and key `user_record_map`
  unchanged (the plugin reads its codes as `/course-add` does, merging and leaving out as above);
  `timestamp` is dropped. The document holds the registrations made since v3's
  last restart (older ones were overwritten at the first change after each restart). The local copy
  `XsDiscordBotKt/Server/` has v3 3.2.0's jar and no `plugins/NtustCourse/` directory.

### Commands

- `cog.command(name)` builds `course-add`, `course-remove` and `course-list` from the `COMMANDS`
  table: names and descriptions from `register.yaml` (`lang.command`, v3's texts by default), a
  required string option renamed `id` (the parameter is `code`) described in one `describe` call;
  guild commands, no default permissions (every member), deferred ephemerally by the command tree,
  as v3's core did. Replies edit the deferral with the text in the member's locale
  (`interaction.locale`, per key falling back to en-US).
- `courses.course_code(text)`: NFKC (full-width letters and digits become ASCII), stripped, upper
  case; valid when it is 9 to 20 ASCII letters and digits (NTUST's codes have 9: `CE162A001`,
  `3N1154701`): the course query matches a code as a prefix, so a shorter one would ask about a
  department or most of the catalogue at every round (found in the cross-review). An invalid code
  gets `invalid-code` (new) and changes nothing.
- `/course-list`: the member's codes in the command's channel, sorted, comparing member IDs exactly;
  over 2000 characters, the last codes give way to `...`.

### Loop

- `cog_load` creates one task, `_run`: `bot.wait_until_ready()` (nothing runs before READY or under
  `--no-online`), opens the session (`open_api`, an attribute that tests replace), then repeats a
  step and `sleep(max(0.1, interval - elapsed))`, v3's pacing (`CourseMonitorService.kt:34-36`).
- `watch.Watcher.step()`: before `start` (`now`, the cog's injected aware clock) or with nothing
  registered it forgets its states and returns; else it reads the registrations, takes the next
  code after the last one asked about (sorted, wrapping around), asks about it and handles the
  answer: the course's previous state (from its previous check) and the new one decide the alerts.
  A failed request, or an answer without the course, keeps the previous state, as v3 skipped an
  empty answer. States of codes no longer registered are dropped.
- Any unexpected `Exception` in a step is logged with its traceback and the loop goes on;
  cancellation stays quiet. `cog_unload` sets `closed`, cancels the loop and the posts under way and
  awaits them, so the session closes before the bot's HTTP client; a reload builds a new cog (v3
  added a second subscriber at every reload while enabled, doubling every alert).

### Alerts

- `alerts.Alerts` keeps, per channel and code, the time of the last available alert and whether a
  full alert is owed. A course with seats alerts each registering channel whose last alert is older
  than `alert-interval` (or that never got one); a course that had seats at its previous check and
  is full now alerts the channels that are owed one. A course without seats at its first check, or
  unknown, alerts nobody.
- The texts are the default locale's (`lang.default_locale`, en-US: v3's English) `alert.available`
  and `alert.full`, rendered in one pass with `ncw@second` (the second of the minute of `now`, v3's
  `now.second`), `ncw@mentions` (`<@id>` per member, space-separated), `ncw@course_name` (with `\`,
  `[` and `]` escaped for the link's text) and `ncw@course_id`. An available alert longer than 2000
  UTF-16 code units goes out in several posts, each with as many members as fit (at most 100,
  Discord's limit for allowed users).
- Posts go through `bot.get_partial_messageable(channel_id)` (any channel kind, no cache), each in
  a task kept in `cog.posting` so that a slow or rate-limited channel holds up no step (v3 queued
  them fire-and-forget); `allowed_mentions` lists the post's members only (users, no roles, no
  `@everyone`), and none for the full alert. A 404 forgets the channel's registrations; other
  refusals are logged once per channel, kind and episode.

### Logs

- `xincord.plugins.failures.Failures` for the course query (kinds: the status, the error type, an
  unreadable answer), the registrations document and each channel's posts; lines start with
  `NtustCourseWatch`, in English (v3 printed `請求失敗: ...` to stdout with `println`). Each post is a
  debug line.

### Tests

- `tests/plugins/ntust_course_watch/`: `test_plugin.py`, `test_config.py`, `test_courses.py`,
  `test_web.py` (aiohttp against a local server), `test_store.py`, `test_commands.py`,
  `test_alerts.py`, `test_watch.py` and `test_lifecycle.py` (the loaded plugin with its API, sleep,
  clocks and channels replaced). Nothing reaches the network (the conftest's `offline` guard, as
  NtustAnnouncements') or sleeps in real time.
- Fixtures (`tests/fixtures/plugins/ntust_course_watch/`): `answer.json`, a trimmed copy of NTUST's
  answer for the prefix `CE162A` in semester `1151` (fetched on 2026-10-11; the teachers' names
  replaced by an example), and `golden.yaml` with v3's texts, their translations, the command
  payload and the request body. No CJK text is typed in Python.

## v3 behaved differently

- v3 behaved differently: registrations never loaded after a restart, and the first change after
  one overwrote the stored ones (inventory bug 3); the store keeps them.
- v3 behaved differently: `/course-remove` removed the whole channel's entry for the course,
  unregistering every member there (bug 2); it removes the member only.
- v3 behaved differently: a reload while enabled added a second subscriber, doubling every alert
  (bug 1); a reload replaces the cog and its loop.
- v3 behaved differently: any exception in the poll loop (a registered channel that was not a text
  channel, a missing permission, a concurrent change) stopped it until the next reload (bug 4);
  each step and each post is guarded, posts reach any channel kind, and failures are logged.
- v3 behaved differently: a course with seats was posted at every poll, about every 1.5 seconds,
  beyond Discord's rate limit, so JDA's queue grew without bound (bug 5); a channel hears about a
  course at most once per `alert-interval` (60 seconds), and a full alert only follows an available
  one.
- v3 behaved differently: `/course-list` matched user IDs as substrings and listed duplicates
  (bug 6); it compares them exactly and lists each course once, sorted.
- v3 behaved differently: codes were stored as typed, so a lowercase or padded code never matched
  (bug 7); codes are NFKC, trimmed and upper-cased, and other than 1 to 20 letters and digits get
  `invalid-code`.
- v3 behaved differently: requests had no timeout, so a stalled answer stopped the loop, and errors
  went to stdout (bug 9); requests time out after 30 seconds and failures are logged once per
  episode.
- v3 behaved differently: the semester and the go-live time were hard-coded, and the catalogue was
  polled before the go-live time and with nobody registered (bug 10, decision C1); they are config,
  and nothing is asked before `start` or while nothing is registered.
- v3 behaved differently: it asked for the whole catalogue, which NTUST's server no longer answers
  (no answer in 60 seconds, then a 500 after 120, on 2026-10-11); the plugin asks about one
  registered code per step.
- v3 behaved differently: one malformed course in the answer failed the whole poll; only the
  checked course's entry is read.
- v3 behaved differently: an available alert with mentions over 2000 characters made JDA throw,
  which stopped the loop; it is split into several posts.
- v3 behaved differently: a course name with `]` broke the alert's link; brackets and backslashes
  are escaped.
- v3 behaved differently: a deleted channel's registrations stayed, skipped at every poll; a 404
  forgets them.
- v3 behaved differently: replies and descriptions were English for everyone; zh-TW members get
  translations, and the alerts stay English (the default locale).
- v3 behaved differently: an unknown key or an invalid file failed the bot even while the plugin
  was disabled; only the plugin is disabled, and unknown keys warn (core).

Kept from v3: the commands, their options and v3's English texts; registrations per channel, the
alert going to the channel where members registered; v3's `isFull`; the available alert's format
(the second, the spoilered mentions, the masked course-selection link, the code block); the full
alert pinging nobody; v3's 1.5-second interval; registrations of guilds the bot left stay, as v3
kept them.

## User-visible changes

Copy: the zh-TW translations of the replies and the descriptions (the zh-TW file also translates
the alerts, so that both locales hold the same keys, though the alerts use the default locale), the
new `invalid-code` reply (both locales), the bundled `config.yaml` (comments, new keys), and the
operator's log lines (English).

1. The plugin is `NtustCourseWatch` under `plugins:` and in `plugins/NtustCourseWatch/`;
   `migrate_v3` moves v3's `plugins/NtustCourse/` there, and v3's file (`enabled` only) loads with
   v3's values.
2. `config.yaml` has `semester`, `start`, `interval` and `alert-interval`, with v3's values.
3. Registrations survive restarts; `/course-remove` removes only the member; codes are read
   loosely (case, spaces, full width) and invalid ones get `invalid-code`; `/course-list` is exact
   and sorted.
4. A channel hears about a course with seats at most once a minute, not every 1.5 seconds, and once
   when it fills after an alert; long mention lists come in several posts.
5. Nothing is asked before `start` or while nothing is registered; each registered course is asked
   about in turn, one request per 1.5 seconds.
6. zh-TW members see Chinese command descriptions and replies; the alerts stay English.
7. A deleted channel's registrations are forgotten at its next alert.

## Risks / Trade-offs

- With many registered codes, each is checked less often: 20 codes at 1.5 seconds are 30 seconds
  apart. v3's whole-catalogue request no longer works, and asking about several codes at once
  would multiply NTUST's load.
- A seat that reopens within `alert-interval` of a channel's last alert about the course waits for
  the interval: up to a minute later than v3, which posted at every poll.
- NTUST may change the course query (the body, the URL, the answer); failures are logged once per
  episode, and a course whose entry changed shape is reported, not silently skipped.
- Registrations of guilds that the bot left stay, as in v3, and their alerts are refused (403):
  one warning per channel and episode.
- Members can register many codes, each a request in turn; the load stays one request per
  `interval`, and only the detection slows down.
- The registrations are read at the start of a step; a member who unregisters while the course is
  being asked about may get that step's alert.
- The throttle and the course states live in memory: after a restart or a reload, the first check of
  a course with seats alerts again, as v3's first poll did.

## Checks

- Package: the `xincord-plugins` wheel holds `ntust_course_watch/` with `config.yaml` and
  `lang/en-US/` and `lang/zh-TW/`, `ntust_tls/` with TWCA's certificate, and the
  `NtustCourseWatch` entry point. `xincord --no-online` from a scratch venv with both wheels and
  `plugins: [NtustCourseWatch]` exits 0 with the bundled config (writing `config.yaml` and the lang
  files), 0 with v3's file (a warning names `enabled`) and 1 with an invalid semester (named).
- Image: `docker compose build`, then `docker compose run --rm -T bot --no-online` with the
  seventeen ported plugins enabled (example values for Economy, TicketAwayNotice and
  NtustAnnouncements) exits 0 with every one loaded. In the image (OpenSSL 3.5.7), Python's default
  context refuses `querycourse.ntust.edu.tw` (`Missing Subject Key Identifier`), and the plugin's
  `open_api` read `CE162A001` of semester 1151 (25 of 60) through the shared context. `docker
  compose down -v` and removing `bot/` cleaned up.
- Probe (a scratch script with discord.py's own objects and its HTTP recorded): `/course-add` with
  ` ce162a001 ` from a zh-TW client deferred ephemerally (type 5, flags 64) and edited `@original`
  into the zh-TW reply; `CE-1` from an en-US client got `invalid-code`; `/course-list` listed the
  code; the store held v3's document. After READY, the loop asked about the code with the bundled
  semester, posted the available alert with `allowed_mentions` `{"users": [1], "parse": []}`, then
  the full alert with `{"parse": []}`, each step about 1.5 seconds after the previous one; a 404 on a
  post deleted the channel's registrations.
- Live, on 2026-10-11, before writing the plugin: v3's whole-catalogue request for semester 1151
  got no answer in 60 seconds, then a 500 after 120; a request for the code prefix `CE162A`
  answered in under a second (the fixture's source).

## Inventory audit

Every section of `docs/porting/analysis/inventory/NtustCourse.md` maps to this change:

- Overview (1): the plugin and its name are "The plugin installs as NtustCourseWatch"; the purpose
  is the requirements; `info.yaml` (no intents, no dependencies, the unused `ntustcourse@` prefix)
  is the package section.
- Lifecycle (2): reading the config and `enabled` are the config requirement and the core's
  `plugins` list; the MongoDB load is "Registrations are kept as v3's document"; `start()`,
  `stop()`, unload and reload (the duplicate subscriber, bug 1) are "Registered courses are checked
  in turn from READY"; `guildCommands()` is the commands requirement; the poll loop's semester,
  1.5-second target and 100 ms minimum are the config and loop requirements; its missing guard is
  "Failures are logged without flooding"; the in-memory state is the watcher's (Loop, Alerts).
- Commands (3): names, options, descriptions and attributes are "Commands keep v3's names and answer
  in the member's locale" (zh-TW added, a v3 difference); the ephemeral deferral and `editOriginal`
  are that requirement's replies; the `isFromGuild` and `isMessage` checks are out of scope (dead:
  guild commands only run in guilds, and every channel that hosts a command takes messages); the
  three handlers are the register, unregister and list requirements, their bugs (2, 6, 7) "v3
  behaved differently" entries. A broken registrations document makes a command raise, which
  discord.py logs and which leaves the response thinking, as v3's exceptions did (Economy's choice).
- Components (4): none.
- Events (5): `processUpdates` is the alert requirements (v3's level alert, now throttled, bug 5,
  and the edge full alert) and the course query requirement (`associateBy`'s last entry, v3's
  `isFull` and limit); `processEvent`'s empty map, gate, texts, mentions, cast (bug 4) and
  fire-and-forget sends are the loop, the config and the alert requirements.
- Configuration (6): `enabled` warns (core); the semester, the gate and the cadence are config
  (C1); the API URL, the connect timeout and the course-selection link stay constants (the link in
  `text.yaml`, which operators can edit); the test server URL is dead code.
- Localization (7): none in v3; the lang files hold v3's English and the zh-TW translations.
- Persistence (8): the document, its shape and its write path are "Registrations are kept as v3's
  document"; the broken load (bug 3) is a v3 difference; the migration notes are "Registrations and
  the v3 data import"; code validation is "Members register courses in a channel".
- External dependencies (9): the endpoint, the header, the body (now the site's, for one code), the
  answer's fields and Moshi's leniencies are "Course seats come from NTUST's course query"; the
  missing timeout and `println` (bug 9) are v3 differences; HTTP/2 is not kept (aiohttp speaks
  HTTP/1.1, which NTUST answers).
- Discord requirements (10): no intents; the permissions are in the smoke checklist; guild commands
  in every guild; the API's rate is `interval` with its minimum and one code per request; Discord's
  per-channel limit is the alert throttle.
- Concurrency (11): commands and the loop share the store, whose changes run under the document's
  lock and whose reads are whole documents; the subscribers' race is gone with the single loop;
  cancellation ends a request at once, and `cog_unload` waits for the loop and the posts.
- Bugs and quirks (12): the behaviors to preserve are scenarios (the commands and texts, the
  ephemeral replies, the silent edge full alert, per-channel registrations, `isFull`); bugs 1 to 10
  are "v3 behaved differently" entries (8 out of scope as dead code); bug 11 and the dead code are
  out of scope.
- Testability (13): each pure part is tested alone (`courses`, `store`, `alerts`, `texts` through
  the commands), the HTTP against a local server, the steps with fakes and an injected clock, and
  the loop through the loaded plugin with its sleep, clocks and channels replaced.
- Assessment (14): a cog with three guild commands, the tree's deferral and
  `edit_original_response`, an `asyncio` task with v3's pacing, aiohttp with a total timeout, a
  guard per step, partial messageables with `AllowedMentions` for the members, a throttle per
  channel and course, the store with v3's shape and the config keys are the decisions above; the
  risks (NTUST's load, Discord's limits, restoring registrations, the semester rolling over) are
  under Risks and in the bundled config's comments.

## Manual smoke checklist

On a test guild, with a bot token and `plugins: [NtustCourseWatch]` in `config.yaml`; the bot needs
View Channel and Send Messages in the channels where members register (inventory section 10):

1. Start the bot: NtustCourseWatch loads with the bundled config, and
   `plugins/NtustCourseWatch/` holds `config.yaml` and `lang/en-US/` and `lang/zh-TW/`.
2. Set `semester` to the current one (as the course query site names it) and `start` to a time in
   the past, run `/xincord reload NtustCourseWatch`; `/course-add`, `/course-remove` and
   `/course-list` show v3's descriptions (zh-TW ones in a zh-TW client).
3. `/course-add id: ce162a001 ` with a code that has seats: the reply is ephemeral; within a few
   seconds the channel gets the alert with the second, the spoilered mention (it pings you), the
   masked course-selection link and the code block; a minute later it comes again.
4. `/course-list` lists the code; `/course-add id:CE-1` answers `invalid-code`; `/course-remove`
   with the code stops the alerts, and `/course-list` lists nothing.
5. Register a code whose course is full: nothing is posted. Restart the bot: `/course-list` still
   lists your registrations.
6. Set `start` to a time in the future and reload: nothing is asked or posted until then (the debug
   log shows no request).
7. Delete a channel with registrations while its course has seats: an info line says that its
   registrations were forgotten.
8. Unload the plugin (remove it from `plugins` and reload): no request is made afterwards.
