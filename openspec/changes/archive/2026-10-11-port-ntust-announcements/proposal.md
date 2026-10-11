## Why

Decision C1 ports NtustManager after TicketAddons, and F3 lists it as in use; the owner renamed it
NtustAnnouncements (`docs/porting/decisions.md`, Amendment 1). v3's NtustManager
(`Plugins/NtustManager`, 11 Kotlin files, 1,874 lines) has no commands, components or listeners:
a background job polls 18 hard-coded NTUST announcement boards every `fetch-interval` seconds,
diffs each board's first page against the list it stored, has Google Gemini turn each new NTUST
article into Discord Markdown, and posts the result to a hard-coded channel per board in a
hard-coded guild. It is the first port that scrapes HTML and calls an LLM API.

## What Changes

- New plugin package `xincord.plugins.ntust_announcements`, registered as `NtustAnnouncements`,
  without intents, lang files or commands, with a bundled `config.yaml`.
- `config.yaml` keeps v3's keys (`fetch-interval`, `api-keys`, `prompt`, so that v3's file loads
  once `boards` is added) and moves v3's hard-coded values into new keys: `boards` (each board's
  name, first-page URL, layout, channel and title prefix; the bundled file lists v3's 18 boards
  with 0 for every channel) and `model` (v3's `gemini-2.5-flash`). The bundled file keeps v3's
  example API key and prompt, so the plugin waits for the operator's keys and channels.
- From READY until the plugin unloads, each board is read at once and then `fetch-interval`
  seconds after each pass: the first page's entries (v3's three layouts, parsed with the standard
  library's HTML parser) that the board has not posted yet are posted in board order. An NTUST
  article's content container goes to Gemini with v3's prompt, keys, rate limit and retries, and
  its Markdown is posted in messages of at most 2000 characters, as v3 split it; other links are
  posted as their title. Posts never ping.
- Each board's posted list is kept in the store in v3's document shape (namespace
  `NtustAnnouncements`, key = the board's name), so that the planned v3 data import can copy v3's
  MongoDB documents.
- v3's defects are fixed (see `design.md`): failed announcements are retried instead of skipped
  for good, a board remembers an announcement only once it is posted and keeps the ones that left
  its first page, a long Gemini backoff no longer holds up the other boards, reloads replace the
  loops instead of adding a second scheduler, titles are escaped and cut to fit, prompts are
  filled in one pass, redirects are followed, relative links resolve, and the guild and channels
  come from the config.
- Failures are logged once per kind and episode (UptimeHeartbeat's `Failures`, moved into the
  shared `xincord.plugins.failures`), the API keys never appear in logs or config errors, and
  boards whose channel the bot cannot see are named when the bot is ready.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:15-286`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:10-328`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementModels.kt:3-19`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:19-335`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:14-294`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementTypes.kt:3-50`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/config/ConfigSerializer.kt:6-26`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:29-271`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/HtmlMinifier.kt:8-51`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/UrlUtils.kt:10-88`
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/resources/config.yaml:1-105`

Out of scope: v3's write-only `announcement_data` archive and the dead code that the inventory
lists (helpers without callers, the aggressive minifier, the commented-out channel purge);
publishing posts to following servers (v3 did not crosspost); boards' later pages (v3 read page 1
only); commands to trigger a check or clear the lists (v3's had no callers); the v3 data import
itself (`xincord migrate`, planned before cutover; `design.md` describes v3's MongoDB documents to
import); the Web Dashboard's reload path (B13).

## Capabilities

### New Capabilities

- `plugin-ntust-announcements`: the NtustAnnouncements plugin.

### Modified Capabilities

- `core-config`: a YAML syntax error gives its line and column without quoting the file's text,
  which can hold a plugin's API key or token (found in the cross-review).

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/ntust_announcements/` and its entry point
in `packages/xincord-plugins/pyproject.toml`; `Failures` moves from UptimeHeartbeat's `logs.py` into
the new shared package `xincord.plugins.failures` (no behavior change); tests under
`tests/plugins/ntust_announcements/` with trimmed copies of NTUST's pages and golden data in
`tests/fixtures/plugins/ntust_announcements/`. One core change, in `xincord.core.config`'s YAML
errors (above), and no new dependency: HTML is
parsed with the standard library and Gemini is called over its REST API with aiohttp. Enabling the
plugin sends the boards' articles to Google's Gemini API with the operator's keys.
