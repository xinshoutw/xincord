# Owner review queue

What is left for the owner after the cutover of 2026-10-12: the plugins not enabled in production,
the follow-ups there, what to watch, and the release settings. The user-visible changes, choices,
manual checks and cutover steps listed here before were answered, verified, skipped or done, and the
rest stands as implemented (`HANDOFF.md`, section 6); each archived change's `design.md` and
`docs/porting-guide.md` keep them.

When an item is done, record it in `HANDOFF.md` section 6 and delete it here; delete a section once
it is empty.

## Not enabled in production

Production runs AutoRole, Calculator, BotInfo, ChatLogger, DynamicVoiceChannel, Economy,
UptimeHeartbeat, MusicPlayer, NtustAnnouncements, Ticket and VoiceLogger; the shop's second bot
runs Economy, UptimeHeartbeat and TicketAwayNotice. Before enabling another plugin there:

- Feedback: delete `plugins/Feedback/lang/*/register.yaml` (v3's, with the `feedbacker` key) so
  that the bundled `/feedback` files are exported, and add `form_failure` and `form_submit_failure`
  to its `config.yaml` for zh-TW texts.
- TicketAwayNotice on the main bot: check that `guild_id` is the shop's guild.
- NtustCourseWatch: set `semester` and `start`; v3's registrations are in the cutover's Mongo export
  (`NtustCourse.generated_cache.json`) if they are wanted.

## Production follow-ups

- MusicPlayer: some official music videos ask for a login; `youtube-oauth` is released, and the
  node needs the spare account's device login on the production host (`.env.example`); check the
  panel's emojis on the production application (v3's names).
- NtustAnnouncements: v3's first Gemini key is invalid; delete it from `api-keys`.
- After a few days: delete the migration's copies on the production host (`CUTOVER.md`,
  "Afterwards") and the rehearsal volumes `xincord-rehearsal-data` and
  `xincord-shirotsuki-rehearsal`.

## After cutover

- VoiceLogger: a voice channel status change names its member. Discord's
  `VOICE_CHANNEL_STATUS_UPDATE` and the audit log entries 192 and 193 were not observed on a real
  guild; if a status set by a member shows `-`, read the bot's log.
- ChatLogger: whether pins and link previews log edits (members' never do; a bot's rich preview
  would), and how long a large purge takes to post.
- DynamicVoiceChannel: two members who join an empty lobby at the same instant may both stay in the
  lobby without a room.
- Ticket: a long archive near Discord's rate limits, and authors whose names Discord refuses for
  webhooks (the archive renames them).
- Backups copy `data/ChatLogger/` as well as `data/xincord.db`, best with the bot stopped.
- NtustAnnouncements: TWCA's intermediate certificate in the package expires on 2030-10-16; if
  NTUST changes its certificates, check the log for TLS failures on the boards.

## Releases and dependencies

- Before the 1.0.0 tag: pending trusted publishers on PyPI for `xincord` (environment `pypi`,
  registered on 2026-10-12) and `xincord-plugins` (environment `pypi-plugins`), both with owner
  `xinshoutw`, repository `xincord` and workflow `release.yml`; and LICENSE, which the owner adds
  (the repository is public without it), then Claude checks that both distributions carry it.
- Renovate: its first run opens the Dependency Dashboard issue (not seen by 2026-10-12, 02:00
  Asia/Taipei); check that its first patch PR merges itself after CI.
- If a Dependabot uv security PR fails on the lock file (GitHub documents uv 0.11; `uv.lock` comes
  from uv 0.12), turn on Renovate's `vulnerabilityAlerts` instead.
