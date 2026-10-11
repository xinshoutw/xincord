## Why

Decision C1 ports NtustCourse after NtustManager, F3 lists it as in use, and C1 asks for its
hard-coded semester and go-live gate in config; the owner renamed it NtustCourseWatch
(`docs/porting/decisions.md`, Amendment 1). v3's NtustCourse (`Plugins/NtustCourse`, 6 Kotlin files,
407 lines) is a course-seat watcher for NTUST's course selection: members register course codes in
a channel with three slash commands, a coroutine asks NTUST's course query for the whole catalogue
of semester `1142` about every 1.5 seconds, and from a hard-coded time (2025-12-26 09:00) the bot
posts to each registering channel, pinging its members, whenever a registered course has seats, and
once when it becomes full. It is the last port before MusicPlayer.

## What Changes

- New plugin package `xincord.plugins.ntust_course_watch`, registered as `NtustCourseWatch`, without
  intents, with a bundled `config.yaml` and `lang/` (en-US and zh-TW).
- Three guild commands with v3's names, options and English descriptions, for every member:
  `/course-add id`, `/course-remove id` and `/course-list`. Their replies are v3's English texts in
  en-US, with zh-TW translations of the replies and the descriptions; the alerts stay English.
- `config.yaml` holds what v3 hard-coded (C1): `semester` (v3's `1142`), `start` (v3's go-live time,
  2025-12-26 09:00 in Taiwan, with its offset), `interval` (v3's 1.5 seconds between requests, at
  least 1 second, so that the bot cannot hammer NTUST's API) and `alert-interval` (60 seconds
  between two alerts about a course that keeps its seats, at least 10).
- From READY until the plugin unloads, once `start` has passed and while any course is registered,
  the plugin asks NTUST's course query about one registered course every `interval` seconds, the
  courses in turn, and posts v3's alerts: a channel that registered a course with seats hears about
  it, pinging only its members, at most once per `alert-interval`; it hears once when the course
  then becomes full, pinging nobody.
- Registrations are kept in the store as v3's document (namespace `NtustCourseWatch`, key
  `user_record_map`: course code, channel, members), so that the planned v3 data import can copy
  v3's MongoDB document.
- NTUST's TLS context (`page_context` and TWCA's intermediate certificate) moves from
  NtustAnnouncements into the shared package `xincord.plugins.ntust_tls`, used by both plugins,
  since `querycourse.ntust.edu.tw` fails Python's strict X.509 checks too.
- v3's defects are fixed (see `design.md`): registrations survive restarts, `/course-remove`
  removes only the member, codes are normalized and checked, the list matches exactly, a reload
  replaces the loop instead of doubling every alert, no error stops the loop, alerts no longer flood
  the channels, requests time out, nothing is asked before `start` or while nothing is registered,
  and the plugin asks for the registered courses only, since NTUST's server no longer answers v3's
  whole-catalogue query (checked on 2026-10-11).

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-142`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseApi.kt:16-92`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:6-76`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/command/Register.kt:12-28`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/resources/config.yaml:1`
- `XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/resources/info.yaml:1-8`

Out of scope: v3's dead code (per-course subscriptions, `BecameFull.previousCount`,
`Course.teacher`, the commented-out test server URL, the `isFromGuild` check that guild commands
never fail, the `isMessage` check that every channel hosting a command passes); the v3 data import
itself (`xincord migrate`, planned before cutover; `design.md` describes v3's MongoDB document);
the Web Dashboard's reload path (B13).

## Capabilities

### New Capabilities

- `plugin-ntust-course-watch`: the NtustCourseWatch plugin.

### Modified Capabilities

None. Moving NtustAnnouncements' TLS context into a shared package changes no behavior.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/ntust_course_watch/` and its entry point
in `packages/xincord-plugins/pyproject.toml`; the new shared package
`packages/xincord-plugins/src/xincord/plugins/ntust_tls/` with NtustAnnouncements' TLS context and
TWCA's intermediate certificate (no behavior change for NtustAnnouncements); tests under
`tests/plugins/ntust_course_watch/` with a trimmed copy of NTUST's answer and golden data in
`tests/fixtures/plugins/ntust_course_watch/`. No core change and no new dependency. Enabling the
plugin sends the registered course codes and the semester to NTUST's public course query.
