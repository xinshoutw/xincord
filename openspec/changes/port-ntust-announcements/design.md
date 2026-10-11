## Context

v3's NtustManager (`Plugins/NtustManager`, 11 Kotlin files, 1,874 lines), which the owner renamed
NtustAnnouncements, has no commands, components or listeners (`Event.kt:6`, listener flag false).
`Event.load()` reads `config.yaml` (`enabled`, `fetch-interval`, `api-keys`, `prompt`,
`ConfigSerializer.kt:6-26`) and starts `NtustManager`, whose initializer looks up a hard-coded guild
(`NtustManager.kt:21`), loads two MongoDB collections into memory
(`AnnouncementCacheManager.kt:14-20`), checks the Gemini settings
(`GeminiApiService.kt:221-238`) and builds the scheduler. Every `fetch-interval` seconds, starting
at once (`AnnouncementScheduler.kt:120-132`), the scheduler checks 18 hard-coded boards, five at a
time (`137-153`): it parses the board's first page with Ksoup (three layouts,
`AnnouncementParser.kt:108-210`), diffs its URLs against the stored list
(`AnnouncementCacheManager.kt:199-224`), and for each new entry, in board order, fetches the
article, extracts `div#Dyn_2_3.M23` or `div.M23`, minifies it (`HtmlMinifier.kt:18-51`), has
Gemini 2.5 Flash convert it to Markdown with key rotation, a client-side rate limit and retries of
up to hours (`GeminiApiService.kt:35-218`), saves it to a write-only archive and posts it to the
board's hard-coded announcement channel in parts of at most 2000 characters
(`NtustManager.kt:105-237`). Non-NTUST links are posted as their title (`UrlUtils.kt:53-88`). Last,
it replaces the stored list with the page's, unconditionally (`AnnouncementScheduler.kt:201`). The
inventory is `docs/porting/analysis/inventory/NtustManager.md`; its section 12 lists the behavior
to preserve and 15 probable bugs.

## Goals / Non-Goals

**Goals:** v3's behavior (the three page layouts, the article container, the minifier, v3's
prompt, keys, rate limit and retry schedule, the message format and split, title links for other
links, page-order posting, the first pass at once, v3's config keys and stored lists); the
inventory's 15 bugs fixed or settled; the hard-coded guild, channels, boards and model in config;
loops that end with the plugin; logs that do not flood and never show a key.

**Non-Goals:** v3's write-only `announcement_data` archive and the dead code that the inventory
lists; crossposting; later board pages; commands; the v3 data import itself; the Web Dashboard
(B13).

## Decisions

### Package and bundled file

- `packages/xincord-plugins/src/xincord/plugins/ntust_announcements/`: `__init__.py` (metadata and
  `setup`), `config.py` (the models), `markup.py` (an HTML tree over `html.parser`), `pages.py`
  (board entries, links, the article's container and the minifier), `messages.py` (Discord
  messages), `gemini.py` (the prompt, the keys' rate limit and the retries), `web.py` (aiohttp: the
  pages and Gemini's REST API), `store.py` (the posted lists), `watch.py` (one board's passes),
  `cog.py` (the loops, the posts, the ready check) and `config.yaml`. Entry point
  `NtustAnnouncements = "xincord.plugins.ntust_announcements"`; `migrate_v3.RENAMED` already maps
  `NtustManager` to it and moves v3's `plugins/NtustManager/` there.
- `INTENTS = discord.Intents.none()`: the plugin listens to no gateway event beyond `on_ready`, and
  the guilds intent of discord.py's defaults caches the channels that the ready check looks up.
  `DEPENDS` and `SOFT_DEPENDS` are empty, as in v3's `info.yaml`. No lang files: v3 had none, and
  its only text, the posted header and title links, is built in code. No component IDs (v3's
  derived `ntustmanager@` prefix was unused).
- The bundled `config.yaml` keeps v3's `fetch-interval`, v3's two example keys and v3's prompt
  (copied from v3's file by a script), and adds `model` and v3's 18 boards: their names (v3's enum
  names, the keys of v3's stored lists), URLs, layouts and the student main office's title prefix
  `【處本部】`, each with `channel-id: 0` (v3's channel IDs and guild were the owner's, never
  committed). The plugin therefore does not load until the operator sets the keys and the
  channels; the error names each of them.

### Config

- `Config(Model)` with v3's kebab-case keys as aliases: `fetch_interval` (`fetch-interval`, 60 to
  Java's `Long.MAX_VALUE` seconds, 3600 by default; v3 checked the minimum only when enabled),
  `api_keys` (`api-keys`, required, at least one, none blank, none equal to v3's example key
  `sk-thisisatestkey1234567890abcdef1234567890`), `prompt` (required, holding the four tokens that
  v3's `validateConfiguration` required; `{{page_title}}` optional), and the new `boards`
  (required, at least one, unique names) and `model` (`gemini-2.5-flash`, letters, digits, `.`,
  `-` and `_`, since it goes into the URL's path). New keys are kebab-case like v3's.
- `Board(Model)`: `name` (non-blank: the key of the board's posted list and the name in the logs),
  `url` (http or https with a host and no spaces), `layout` (`student-affairs`,
  `academic-affairs` or `language-center`, v3's three parsers), `channel_id` (`channel-id`, a
  positive integer) and `title_prefix` (`title-prefix`, empty by default: every title).
- `boards` is required although v3's file has no such key: its values cannot have defaults
  (channel IDs, and `【處本部】`, which Python files may not hold), and v3 hard-coded them in
  Kotlin, so a migrated v3 file must get them anyway. `migrate_v3` does not add them: it cannot
  know the channels.
- Every model sets `hide_input_in_errors=True` and the validators give fixed messages, so that no
  key appears in the core's `ConfigError` or in the chained `ValidationError` that the core logs.
- v3's `enabled` key only warns (core-config); kaml's strict mode is gone.

### Pages and the HTML parser

- `markup.py` builds a tree with the standard library's `html.parser` (no dependency): void
  elements, raw-text elements (`script`, `style`), duplicate attributes (the first wins), an end tag
  that closes the nearest open element of its name, the end tags that HTML lets pages omit in
  tables and lists (`td`, `th`, `tr`, `tbody`, `thead`, `tfoot`, `li`, `dt`, `dd`, and `p` before a
  block), and the implied `tbody` (and `tr`) that HTML5 parsers such as jsoup insert. NTUST's pages
  are well formed (checked against the live pages on 2026-10-11), so these rules cover omissions,
  not HTML5's whole tree construction.
- `Element.select` reads the selectors that v3 used: compound selectors (a tag, `#id`, `.class`,
  classes compared without case as jsoup's `hasClass`) joined by descendant combinators, matched
  against the element itself and its descendants in document order, the element counting as an
  ancestor, as jsoup's `select`. `Element.text()` follows jsoup's `text()`: runs of space, tab, line
  feed, form feed, carriage return and no-break space become one space, U+200B and U+00AD are
  dropped, `br` and block elements separate words, and the result is trimmed; v3 trimmed it again
  with Kotlin's `trim()`, which also removes Unicode spaces such as U+3000.
- The tree's walks (selection, text, serialization) keep their own stacks, so no nesting depth
  exhausts Python's recursion limit; a non-void start tag with a slash stays open and classes
  split at Java's whitespace (no-break spaces left out), as in jsoup. Pages are parsed in a worker
  thread (`asyncio.to_thread`), about 0.3 s per MB, so that no page holds up the event loop.
- `pages.board_links(html, board, page_url)` ports `parseAnnouncementList`: `student-affairs` and
  `academic-affairs` take the first `table.listTB.table` (none: no entries, with v3's warning),
  its `tbody tr` rows, each row's `td` cells (fewer than two: skipped), cell 0 or cell 1, and its
  first `a`; `language-center` takes each `div.row.listBS` and its first `div.d-item.d-title.
  col-sm-12 div.mbox div.d-txt div.mtitle a`. The `title-prefix` applies to every layout (v3
  hard-coded it for STUDENT_MAIN_OFFICE, a Student Affairs board).
- Links (`complete_url`): an `https://` link stays as written and a `/` path takes the page's scheme
  and host, which give v3's exact strings, the identity of a posted announcement; `//host/x` takes
  the page's scheme and other relative links resolve against the page with `urljoin` (v3 mangled
  both, bug 12); other schemes stay as written, as in v3. The page's URL is the one after
  redirects.
- Pages are fetched with certificates and host names verified but without Python's
  `VERIFY_X509_STRICT` (`web.page_context`): Python 3.13 made it a default, and the certificate
  chains of NTUST's three hosts lack a Subject Key Identifier, which it refuses (checked on
  2026-10-11 with Python 3.14.8 and OpenSSL 3.5.9: every page failed, the relaxed context read
  them); Java's `HttpClient` accepted them. `www.academic.ntust.edu.tw` also sends its own
  certificate twice and the root but not TWCA's intermediate, so OpenSSL cannot build its chain:
  the package ships that public certificate (`twca-secure-ssl-ca.pem`, TWCA Secure SSL
  Certification Authority, valid until 2030-10-16, SHA-256 checked by a test) and the context
  trusts it. Gemini's requests keep Python's default context.
- The live pages (2026-10-11) confirmed v3's layouts: the Student Affairs and Academic Affairs
  boards are `table.listTB.table` with `thead` and `tbody`, the Language Center's are
  `div.row.listBS`, the student resource room's `412-1053-8272.php` page has the same table (bug 15
  settled: it works), and the boards link external sites (Google Docs, government sites), which
  v3 posts as title links. The test fixtures are trimmed copies of these pages.

### Articles and minification

- `pages.is_article(url)` is v3's `validateUrlType`, a full match of
  `^https://[^/?#]*\.ntust\.edu\.tw/p/[0-9\-,r]+\.php.*$`: v3's `.*` before the host's
  `.ntust.edu.tw` took any host (found in the cross-review); v3's `RELATIVE_PATH` was unreachable
  and both other types meant "not an article".
- `pages.article_html(html)` takes the first `div#Dyn_2_3.M23`, else the first `div.M23`, and
  minifies its outer HTML. The outer HTML is the tree serialized (attributes in their order, `"`
  quotes, text escaped, raw text as it is, comments dropped); v3 sent jsoup's pretty-printed
  serialization. Neither is byte for byte the page, and Gemini reads both alike.
- `pages.minify(html)` is v3's regex sequence with `re.ASCII`, because Java's `\s` is ASCII:
  comments, whitespace between tags, leading and trailing whitespace of lines, runs of two or more
  whitespace characters, empty lines, then a trim. Line breaks are normalized to `\n` first, as an
  HTML parser would have, so that Python's `^` and `$` see the lines that Java's saw. The trailing
  step is `(?<!\s)\s+$`, which removes what v3's `\s+$` removed (checked on 200,000 random texts)
  without backtracking through each run of whitespace (v3's took 5 s for 40,000 spaces).

### Gemini

- No SDK: `web.Web.generate(key, model, prompt)` POSTs `{"contents": [{"parts": [{"text":
  prompt}]}], "generationConfig": {"temperature": 0.1}}` to
  `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent` with the key in
  the `x-goog-api-key` header (Google's documented REST call, checked on 2026-10-11), over the
  plugin's aiohttp session, without following redirects, within 300 seconds. The answer's text is
  v3's: the first candidate's parts' texts joined and trimmed; none or blank is a failed attempt,
  as is an answer that is not 200 (`GeminiError` with the status and Google's `error.message`). The
  google-genai Java SDK built a new client per attempt and never closed it (bug 10); one session
  serves the plugin until it unloads.
- `gemini.fill_prompt` replaces the five tokens in one pass (`re.sub` over the template), so that a
  title holding `{{html}}` stays as written; v3's chained `String.replace` calls expanded tokens in
  earlier values. `{{base_url}}` is `https://` and the first `https://([^/]+)` match of the URL,
  else `ntust.edu.tw`; `{{now}}` is the host's local time (v3's `LocalDateTime.now()`).
- `gemini.KeyRing` is v3's limiter on an injected monotonic clock: each key's attempts in the last
  60 seconds, at most 10; `take` scans from the key after the last used and records the attempt in
  the same step (v3's check and record were two steps, so concurrent boards could overshoot); when
  every key is at its limit, `wait` is the time until the oldest attempt among them is 60 seconds
  old. A use leaves the window at 60 seconds (v3 kept it until it was older, then slept an extra
  second). Keys are counted by their text, so a key listed twice has one budget, as in v3.
- `gemini.Gemini.convert(html, link)` is `processHtmlContentWithRetry`: at most 10 attempts; a wait
  for the rate limit uses no attempt; after a failed attempt it sleeps 60, 300, 900, then 1800
  seconds (`backoff`); after the tenth it logs an error and gives None. Any `Exception` in an
  attempt fails the attempt, as in v3; cancellation is no `Exception` and ends the conversion.

### Messages

- `messages.content_messages(content)` is `createDiscordMessages`: the content trimmed as Kotlin's
  `trim()`; up to 1975 UTF-16 code units, one message `HEADER + "\n" + content`; else
  `split(content, 1980)`, v3's `splitContentIntoSegments` in UTF-16 code units (Kotlin's
  `String.length`), the header and a line break before the first part only. The header is 15 U+FF3F
  (built with `chr` in Python). A cut without a line break never splits a character outside the
  BMP, which Kotlin's `substring` could, and parts of only whitespace (a cut between line breaks
  or spaces) are left out, since Discord refuses them.
- `messages.link_message(title, url)`: `HEADER + "\n# [" + title + "](" + url + ")"`, as v3, with
  `\`, `[` and `]` escaped in the title, parentheses, angle brackets, backslashes and whitespace
  percent-encoded in the URL (they end a Markdown link), and the title cut with an ellipsis so that
  the message fits in 2000 units; the URL is never cut unless no title fits at all (a URL of about
  1980 units, which no board has), where the message is the header and the URL cut to the limit.
  v3 neither escaped nor checked the length (bug 13).
- Posts go through `bot.get_partial_messageable(channel_id)`, which needs no cache and takes every
  channel kind, with `allowed_mentions=AllowedMentions.none()`; v3 used JDA's default mentions, so
  `@everyone` in Gemini's output would have pinged. v3's announcement channels are announcement
  channels; posts are not published to following servers, as in v3.

### Passes

- `watch.Watcher` runs one board: `check()` is one pass and `run()` loops `check()` then
  `sleep(fetch-interval)`. Its effects are passed in (the page fetch, the conversion, the post,
  the store), so that tests drive it without HTTP or Discord.
- A pass (v3's `checkAnnouncementUpdates`): fetch the board's page (a failure or a page without
  entries logs and changes nothing, as v3's empty list did); keep the entries with a non-blank
  title and link (v3's `filterValidAnnouncements`; the skipped count is a debug line, where v3 warned
  at every cycle about "empty content"); load the board's posted links (a broken document logs
  and ends the pass); then post, in page order, each link not posted yet, once per link (v3 posted
  a link listed twice twice, bug 3).
- An announcement (v3's `contentParser` and `handleNewAnnouncement`): a link that is not an NTUST
  article is posted as its title link without a fetch. An article's page is fetched (a failure or
  a status other than 200 leaves the announcement for the next pass, bug 1); without a container,
  or when Gemini fails all 10 attempts, it is posted as its title link with a warning (v3 skipped it
  for good, bug 1); else its Markdown is posted. The messages go out in order; when the first is
  refused nothing was posted and the announcement waits for the next pass (bug 2); when a later one
  is refused, the announcement counts as posted, with an error, since posting it again would
  repeat its start. Refused messages wait on the board (`Watcher.ready`) until they are posted or
  leave the page, so that a refusing channel costs one conversion per article, not one per pass
  (found in the cross-review). Links posted while the store refused to save them stay in memory
  (`Watcher.delivered`) until a save takes them, so that none is posted twice. Each announcement is
  guarded: an exception is logged with its traceback once per kind and episode, and the board's
  later entries are still posted.
- Fetches of NTUST pages (boards and articles) share one `asyncio.Semaphore(5)`, v3's
  `maxConcurrentRequests`; it is held for the fetch only, not while Gemini works or waits (bug 9).

### Storage and the v3 data import

- `store.py`: namespace `NtustAnnouncements`, key = the board's name, value = v3's
  `TypedListWrapper`, `{"items": [{"type": <board name>, "url": ..., "title": ...}, ...]}` in
  Moshi's field order; v3's `itemTypeName` is read and ignored (Moshi omitted it when null, and the
  port writes none). A document that is not this shape (not an object, `items` not a list, an item
  without string `type`, `url` and `title`) raises `DataError`: the board logs an error once per
  episode, posts nothing and never overwrites it; v3 dropped such items one by one, after which
  their links counted as new.
- Each board has one writer, its own loop (a reload's new loop starts after the old one ended), so
  the document is read once per pass and written with `Store.put`, without a lock.
- The document is written after each posted announcement (`remember`): the page's links that are
  posted (stored before or posted in this pass), in page order, then the stored links no longer on
  the page, at most 100 of them, most recent first. v3 replaced the list with the page's at the
  end of every cycle, so an announcement that left the first page and came back (a transient
  partial page, an article moved back to the top) was posted again (bug 3). A pass that posted
  nothing writes the document only when it changed (the page's order or titles, links that left).
- v3 behaved the same way on a first pass: with no stored list, every entry of the first page is
  posted (the inventory's "first-ever run"). The planned v3 data import (`xincord migrate`) must
  therefore run before the plugin is enabled at cutover.
- **v3 data to import:** v3's embedded MongoDB (`<v3 directory>/mongodb-data`, MongoDB 8.2, WiredTiger
  files, read through a `mongod` of that version or `mongodump`), database `NtustManager`,
  collection `current_announcement_lists`: one document per board, `{"_id": "<board name>",
  "value": {"items": [...], "itemTypeName": "tw.xinshou.discord.plugin.ntustmanager.announcement.AnnouncementLink"},
  "timestamp": <epoch ms>}`. The import puts each document's `value` under namespace
  `NtustAnnouncements` and key `_id` unchanged (its `itemTypeName` is ignored); `timestamp` is
  dropped. An `_id` that names no configured board is imported anyway: the board can be added
  later with that name. The collection `announcement_data` (the write-only archive) is not
  imported. The local copy `XsDiscordBotKt/Server/mongodb-data` runs v3 3.2.5, whose
  `AnnouncementCacheManager` stored the same collections; the import's tests use it, per B11.

### Loops

- `cog_load` creates one task, `_run`, which awaits `bot.wait_until_ready()` (nothing runs before
  READY or under `--no-online`), opens the session (`open_web`, an attribute that tests replace),
  builds one `Gemini` for every board, and runs one `Watcher.run()` per board in a `TaskGroup`.
  Each board passes at once, then `fetch-interval` seconds after its own pass (a fixed delay, the
  project's mapping of `scheduleAtFixedRate`): a board whose announcement waits hours between
  Gemini attempts holds up neither the others' passes nor their fetches (bug 9).
- `cog_unload` cancels the task and awaits it, so that the session closes before the bot's HTTP
  client; a reload builds a new cog with the new config (bugs 4 to 7: no second scheduler, no
  rejected executor, new keys, prompt and interval apply). The cog's `sleep`, `clock` and `now`
  are attributes that tests replace.
- `Watcher.check()` logs any unexpected `Exception` with its traceback and the loop goes on;
  cancellation stays quiet.

### Logs

- `Failures` (UptimeHeartbeat's failure episodes) moves into the shared package
  `xincord.plugins.failures`, unchanged. Each board has one for its page, one for its articles,
  one for its posts and one for its stored document; the plugin has one for Gemini. A kind of failure (a status code, an error
  type, `no entries`) is logged at its level when it is new in the episode, the rest at debug
  level, and the step logs one info line once it has worked three times in a row.
- Lines start with `NtustAnnouncements board <name>`; a key is named by its position in
  `api-keys` (`key 2`), never by its text (v3 logged its last four characters), and the texts of
  Gemini's errors and of unexpected tracebacks have every key replaced with `...` before they are
  logged. NTUST's URLs carry no secret and are logged whole; Gemini's URL holds no key.
- Info lines: a pass that finds new announcements (`3 new announcements`) and each posted
  announcement (its URL); v3's per-step info lines are debug lines.

### Core change

- `xincord.core.config.load_config` drops the faulty line that PyYAML quotes in a YAML syntax
  error (the marks' buffers), in the `ConfigError` and in the chained error; the line and the
  column stay (a `core-config` delta). A key on a line with a syntax error reached the log
  otherwise (found in the cross-review); UptimeHeartbeat's push tokens had the same gap, an open
  question in the review queue.

### Ready check

- `check()` runs from `on_ready` and from `cog_load` in a ready bot: for each board, a warning when
  `bot.get_channel(channel_id)` is None (the bot is not in its guild, cannot see it, or the ID is
  wrong) or the channel takes no messages (a category or a forum: no `send`). v3 looked the guild up
  with `!!` and stopped the bot without it (bug 8), and looked each channel up only when posting.

### Tests

- `tests/plugins/ntust_announcements/`: `test_plugin.py`, `test_config.py`, `test_markup.py`,
  `test_pages.py`, `test_messages.py`, `test_gemini.py`, `test_web.py`, `test_store.py`,
  `test_watch.py`, `test_lifecycle.py`, `test_ready.py`.
- Fixtures (`tests/fixtures/plugins/ntust_announcements/`): trimmed copies of NTUST's live pages
  (the dormitory, student main office, course and Language Center recruitment boards; a student and
  an academic article), fetched once on 2026-10-11, and `golden.yaml` with the entries that v3's
  parsers give for them and v3's bundled boards. No CJK text is typed in Python.
- Nothing touches the network or sleeps in real time: `test_web.py` runs aiohttp against a local
  server; the other tests pass fakes for the pages, Gemini and the channels, a recording `sleep`
  and a fake clock. An autouse fixture (`offline`) makes aiohttp refuse every host but this
  machine's, after a test that loaded the plugin into a ready bot once reached NTUST: a dotted
  `monkeypatch` target had resolved a stale module object, so tests patch the module that
  `sys.modules` holds.
- The loops' scene (`tests/plugins/ntust_announcements/conftest.py`) loads the plugin offline and
  replaces the cog's `open_web` (`FakeWeb`: the trimmed pages, a student article for every
  article, a fake Gemini that can hold a prompt forever, page fetches that can wait together),
  `sleep` (`Clock`: each wait lasts until the test wakes the waits so far) and
  `bot.get_partial_messageable` (a `FakeChannel` per channel).

## v3 behaved differently

- v3 behaved differently: a failed item was never retried, since the board's list was replaced
  with the page's whatever happened (bug 1); an article whose page could not be fetched, or whose
  post Discord refused, is posted at a later pass, and content that cannot be converted (no
  container, ten failed Gemini attempts) is posted as its title link.
- v3 behaved differently: an item was saved before it was posted, so a refused post lost it
  (bug 2); a board remembers an announcement once it is posted.
- v3 behaved differently: an announcement that left the first page and came back, or that a
  transient partial page left out, was posted again, and a link listed twice was posted twice
  (bug 3); a board keeps up to 100 links that left its page, and posts a link once.
- v3 behaved differently: a reload added a second scheduler (duplicate posts), failed after a
  disable, ignored new keys, prompt and interval, and initialized everything to shut it down
  (bugs 4 to 7); a reload replaces the cog and its loops.
- v3 behaved differently: the guild and 18 channels were hard-coded with `!!`, so the bot did not
  start outside the owner's guild, and a channel that was not an announcement channel lost its
  posts (bug 8); the channels are config, any channel that takes messages works, a missing one is a
  warning at READY and when posting, and the bundled file holds no real ID.
- v3 behaved differently: a Gemini backoff of up to hours held one of five slots and the whole
  cycle, and the next cycles ran back to back (bug 9); boards run on their own and the fetch limit
  is held only while fetching.
- v3 behaved differently: a new Gemini client was built for every attempt and never closed
  (bug 10); one HTTP session serves the plugin until it unloads.
- v3 behaved differently: redirects were not followed, so a moved board was empty at every cycle
  (bug 11); they are followed (at most 10), and links resolve against the final page.
- v3 behaved differently: `//host/x` became `https://<board host>//host/x` and `x.php` stayed
  relative (bug 12); both resolve.
- v3 behaved differently: a title link's title was not escaped and its length not checked, so `]`
  broke the link and a long title failed the post (bug 13); the title is escaped and cut to fit,
  the URL kept whole.
- v3 behaved differently: entries without a title or a link logged an "empty content" warning at
  every cycle (bug 14); a debug line counts them.
- v3 behaved differently: prompt tokens in a title or a URL were replaced by later tokens' values
  (chained `replace`); the prompt is filled in one pass.
- v3 behaved differently: Gemini's output could ping `@everyone` and roles (JDA's default
  mentions); posts ping nobody.
- v3 behaved differently: log lines showed each key's last four characters; keys are named by
  their position and removed from error texts.
- v3 behaved differently: a key at its limit stayed blocked until its oldest use was more than 60
  seconds old, then one more second; it frees at 60 seconds, and finding the key and counting its
  use is one step.
- v3 behaved differently: the config was validated only when `enabled` was true, a missing `api-keys`
  or `prompt` failed even while disabled, and any invalid value stopped the bot; the file is read
  only when `plugins` lists the plugin, an invalid one disables only it, and unknown keys warn.
- v3 behaved differently: v3's write-only `announcement_data` archive (with a fetch date that was
  never shown) is not kept.
- v3 behaved differently: a link whose path, query or fragment named `.ntust.edu.tw/p/<n>.php`
  counted as an NTUST article, whatever its host, and was fetched and sent to Gemini; only NTUST's
  hosts count now.
- v3 behaved differently: a cut between line breaks or spaces gave a message part of only
  whitespace, which cannot be sent; such parts are left out.
- v3 behaved differently: an exception in one announcement was caught per announcement (v3) but its
  item was then marked seen; it is tried again at the next pass, and the board's later entries are
  posted meanwhile.

Kept on purpose: the first pass at once, page-order posting (newest first on NTUST's boards), the
first page only, v3's three layouts and container selectors, the minifier, the prompt, the model,
temperature, rate limit and retry schedule, the header and the split, title links for other links
and PDFs, the URL as an announcement's identity, every first-page entry posted when nothing is
stored, and no crossposting.

## User-visible changes

Copy: the bundled `config.yaml` (comments, `model`, `boards`), the title links' escaping and
ellipsis, and the operator's log lines (English).

1. The plugin is `NtustAnnouncements` under `plugins:` and in `plugins/NtustAnnouncements/`;
   `migrate_v3` moves v3's `plugins/NtustManager/` there. A v3 file needs `boards` added (copy
   them from the bundled file with the channel IDs); the bundled file waits for the keys and the
   channels.
2. Announcements that failed are posted later (v3 lost them); articles that Gemini cannot convert
   appear as their title link; an announcement that left a board and came back is not posted
   again; duplicate links are posted once.
3. Boards are read on their own schedules: a board stuck in Gemini retries no longer delays the
   others.
4. Title links escape `\`, `[` and `]` and are cut with an ellipsis to fit; posts never ping.
5. Log lines name the board and a key's position; each kind of failure is logged once per episode;
   a warning at READY names a board whose channel the bot cannot see.

## Risks / Trade-offs

- Every first-page entry is posted when a board has no stored list, as in v3: without the v3 data
  import at cutover, the first pass posts every board's first page (about 250 announcements, each
  a Gemini attempt at 10 per minute per key). A new board added to the config posts its first page
  too.
- An article whose page keeps failing is fetched at every pass until it leaves the first page; the
  log says so once per episode.
- NTUST may change its markup or its URLs: a changed layout gives no entries (a warning per
  episode), and a changed URL shape (a new query parameter) makes every entry new, as in v3.
- Gemini's output is not bounded beyond the prompt's instruction (under 10,000 characters): a
  runaway answer becomes many messages, as in v3. Its Markdown is posted as Gemini wrote it.
- `{{now}}` is the host's local time: UTC in the container unless `TZ` is set in `compose.yaml`
  (Giveaway's note), so the prompt's time is UTC there.
- An unload during a post can repeat that announcement at the next start, since it is stored after
  it is posted; storing first would lose it instead.
- The articles are sent to Google with the operator's keys; the free tier's daily quota can run out
  during a backlog, after which conversions fail until it resets and their articles are posted as
  title links.
- `gemini-2.5-flash` may be retired by Google (its previews were shut down in 2026); `model`
  switches it without a code change.

## Cross-review (a subagent, 2026-10-11)

A review of the pushed work (other paths into a pass, repeated or concurrent passes, state left
behind), with scratch probes through the loaded plugin, a local board server, discord.py's own
objects and jsoup 1.23.1 on 46 malformed pages, found no lifecycle bug (reloads, failed reloads,
`--no-online` and a second READY never ran two loops for one board) and these problems, fixed in
this change (tasks 9.3 to 9.19):

1. (medium) A channel that refuses posts made Gemini convert every new article again at every
   pass, which a wrong channel ID or a missing permission turns into a spent daily quota and
   articles posted for good as title links. A board now keeps an article's messages until they
   are posted.
2. (medium, rare) A part of only whitespace (`"a" * 1980 + "\n\n\n" + ...`) is a message that
   Discord refuses, and a refused later part counted as posted, so the rest was lost. Such parts
   are dropped.
3. (low) An exception in one announcement (a page nested about 1,000 levels deep overflowed the
   recursive serializer) stopped the board's later entries at every pass, with a traceback each
   time. Each announcement is guarded and logged once per kind and episode, and the tree's text
   and serialization walk without recursion.
4. (low) A store write that failed after a post made the next pass post the announcement again.
   A board keeps the links it posted in memory too.
5. (low) A YAML syntax error on a key's line logged the line (PyYAML's snippet, in the core's
   `ConfigError` and its chained error), so a key could reach the log. The core's YAML errors now
   give the line and the column without the file's text (a `core-config` delta; UptimeHeartbeat's
   open question about the same snippets, in the review queue, is settled the same way).
6. (low) The tree differed from jsoup where pages are malformed: `<a href=... />Title` closed the
   link (jsoup keeps the title in it) and classes split at no-break spaces. Both follow jsoup now;
   the remaining differences (a `form` between a table and its rows, links misnested across
   blocks, links inside `option`) are accepted, since NTUST's pages are well formed.
7. (low) Parsing and minifying ran on the event loop (about 0.3 s per MB, more for deep nesting),
   and the minifier's trailing-whitespace step was quadratic in a run of whitespace (40,000 spaces:
   5 s). Pages are parsed in a worker thread, and the step uses an equivalent pattern that cannot
   backtrack inside a run.
8. (low, as v3) The article pattern's `.*` took any host (`https://example.com/x.ntust.edu.tw/p/1.php`
   was fetched and sent to Gemini). The host must end in `.ntust.edu.tw` now.
9. Tests added for what the scenarios say and no test checked: a pass over v3's document with
   `itemTypeName`, a redirected page whose relative links resolve against it, empty pages logged
   once per episode, and a reload that replaces the loops.

The review also found sound: reloads during a post (one send in flight at most, sent again after,
the documented risk), failed reloads, `--no-online`, a second READY, `cog_unload` racing the
start, the store's worker thread ordering writes across a reload, `remember` with duplicates,
renamed titles, links that come back and v3 documents with other boards' items, Discord's limits,
keys in headers only, bounded failure kinds, entity decoding in attributes, odd markup without
exceptions, and the largest `fetch-interval`.

## Checks

- Package: the `xincord-plugins` wheel holds `ntust_announcements/config.yaml`, its modules,
  `xincord/plugins/failures/` and the `NtustAnnouncements` entry point; `xincord --no-online` from
  a scratch venv with both wheels and `plugins: [NtustAnnouncements]` exits 1 with the bundled
  config (both `api-keys` and the 18 `boards.<n>.channel-id` named, nothing else, no key text) and
  0 once the bundled file's keys and channels are replaced with example values.
- Image: `docker compose build`, then `docker compose run --rm -T bot --no-online` with the sixteen
  ported plugins enabled (example values for Economy, TicketAwayNotice and NtustAnnouncements)
  exits 0 with every one loaded. In the image (OpenSSL 3.5.7), Python's default TLS context refuses
  `lc.ntust.edu.tw` and the plugin's page context reads it. `docker compose down -v` and removing
  `bot/` cleaned up.
- Probe (a scratch script with discord.py's own objects and its HTTP recorded): after READY, the
  two boards' ten announcements went out as `POST /channels/{id}/messages` with the header,
  Gemini's Markdown and `allowed_mentions` `{"parse": []}` although it held `@everyone` and a role
  mention; each board then waited 3600 seconds; the store held v3's document with the dormitory's
  six items; the ready check warned about a board whose channel was a category; `bot.close()`
  ended the loops.
- Live, once each, sequentially: the plugin's web and parser read all 18 bundled boards (229
  entries: 10 to 20 per board, the student resource room's `412` page included) and found a
  Language Center article's container, on the host (Python 3.14.8, OpenSSL 3.5.9). The first try
  stopped at the Academic Affairs boards: their host leaves out TWCA's intermediate.
- Found while checking and fixed in this change: NTUST's certificates and Python's strict X.509
  checks, the academic host's missing intermediate (`page_context`), and pydantic's `min_length`,
  which counted only the valid items and so also called the bundled config's 18 boards an empty
  list.

## Inventory audit

Every section of `docs/porting/analysis/inventory/NtustManager.md` maps to this change:

- Overview (1): the plugin and its name are "The plugin installs as NtustAnnouncements"; the 18
  boards, channels and guild are the config requirement and the bundled file (golden data).
- Lifecycle (2): reading the config and `enabled` are the config requirement and the core's
  `plugins` list; the guild lookup is the ready check; the MongoDB load is the store requirement;
  `validateConfiguration` is config validation; the first cycle at once, the scheduler, unload and
  reload are "Boards are checked from READY until the plugin unloads" (bugs 4 to 7 are "v3 behaved
  differently" entries); the cycle algorithm (`checkAllAnnouncements`, `checkAnnouncementUpdates`
  steps 1 to 6, the first run, `boardParser`, `parseAnnouncementList`, `contentParser`) is
  "Board pages list their announcements", "Article pages give their content as minified HTML",
  "New announcements are posted in board order" and "Each board remembers what it posted".
- Commands (3) and components (4): none; the helpers without callers (`triggerManualCheck`,
  `clearCache`, `getAllCurrentAnnouncementLists`) are out of scope as dead code.
- Events (5): none; `on_ready` runs the ready check only.
- Configuration (6): the keys and their checks are the config requirement; the prompt's tokens
  are "The prompt is filled in one pass"; the default prompt is in the bundled file; of the
  hard-coded values, the guild and channels (the guild by its channels), the board URLs, the
  filter and the model became config, and the temperature, the rate limit, the retries, the
  concurrency, the timeouts and the split sizes stay v3's constants (review queue).
- Localization and templates (7): the header, the split in UTF-16 code units and the title links
  are "Announcements become messages within Discord's limits"; the unescaped title is bug 13.
- Persistence (8): the collections and the document envelope are "Storage and the v3 data import"
  and the store requirement (v3's document read with or without `itemTypeName`); the legacy
  converter is `parse_posted`; `announcement_data` is not kept; the migration concerns (import or
  first-pass posting, the URL as identity) are under Risks and in the data import's description.
- External dependencies (9): Ksoup is `markup.py`; the google-genai SDK is Gemini's REST call; the
  endpoints are the bundled boards; the URL helpers are `complete_url`, `is_article` and
  `fill_prompt`'s base URL (`extractParagraphId` served the dropped archive and log lines only);
  the Gemini service is the two Gemini requirements.
- Discord requirements (10): no intents beyond the defaults; the permissions are in the smoke
  checklist; announcement channels became any channel that takes messages, with the ready check;
  no crossposting, as in v3; mentions are off; the backlog's posts are under Risks.
- Concurrency (11): the executor and coroutines are one task with a task group; the semaphore is
  the fetch limit, held while fetching only (bug 9); each board's list has one writer; the
  limiter's check and record are one step; store writes are awaited; unloading cancels and waits.
- Bugs and quirks (12): the behaviors to preserve are scenarios (1 "Start at READY", 2 "Posted
  links", 3 "First pass", 4 "Title prefix", 5 "First pass" and "Content that cannot be
  converted", 6 the message scenarios); 7, the fetch date, served the dropped archive; bugs 1 to
  14 are "v3 behaved differently" entries and bug 15 is settled (the 412 page has the table); the
  dead code is out of scope; the time zone stays the host's (Risks, review queue).
- Testability (13): each pure part is tested alone (`markup`, `pages`, `messages`, `gemini`,
  `store`), the HTTP layer against a local server, the passes with fakes and the loops through
  the loaded plugin, with the clock and the sleeps injected.
- Assessment (14): a cog without commands, `asyncio` tasks instead of `tasks.loop`, the semaphore,
  aiohttp instead of httpx, the standard library's parser instead of selectolax or BeautifulSoup,
  Gemini's REST API instead of an SDK, the store instead of MongoDB, partial messageables and
  `AllowedMentions.none()` are the decisions above.
- Appendix: every scenario seed is a scenario: first run, failed or empty boards, a new NTUST
  article, an external link, the split at 1981 units, entries that leave the page (kept now,
  bug 3), Gemini's retries and rate limit, and the config errors.

## Manual smoke checklist

On a test guild, with a bot token, a Gemini API key and `plugins: [NtustAnnouncements]` in
`config.yaml`; the bot needs View Channel and Send Messages in each board's channel (inventory
section 10):

1. Start the bot with the bundled config: NtustAnnouncements does not load, the error names
   `api-keys` and each `boards.<n>.channel-id` and shows no key, and
   `plugins/NtustAnnouncements/config.yaml` is the bundled file.
2. Set `api-keys` to the Gemini key and keep two boards (one Student Affairs and one Language
   Center), each with a test channel; run `/xincord reload NtustAnnouncements`: it loads, and a
   warning names any board whose channel the bot cannot see.
3. Within a minute, each board's first page is posted in page order: articles as Markdown under the
   15-character header, split into parts under 2000 characters, other links (Google Docs) as
   `# [title](url)`; no post pings anyone.
4. Reload again: nothing is posted again. Remove the bot's Send Messages permission in one channel
   and delete that board's document (or add a new board): a warning names the board and the
   channel at each pass, once per episode; give the permission back: the announcements are posted
   at the next pass and an info line says posting works again.
5. Set an invalid key: each conversion logs a Gemini failure once per episode, naming `key 1` and
   no key text; the article is posted as its title link after ten attempts (or shorten the check
   by watching the first failure only).
6. `docker compose logs bot | grep <key>` finds nothing.
7. Unload the plugin (remove it from `plugins` and reload): its loops stop, and no request is made
   afterwards.
