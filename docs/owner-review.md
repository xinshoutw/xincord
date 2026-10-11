# Owner review queue

What is left for the owner: the plugins not enabled in production, the follow-ups there, what to
watch, and the release settings. When an item is done, delete it here (its commit or change
records it); delete a section once it is empty.

## Production

Both bots run on the host `xs-mac` with docker compose, each from the `compose.yaml` of its
release tag and the image that `XINCORD_VERSION` in its `.env` names:

- The main bot in `~/selfhost/Discord/xincord` runs AutoRole, Calculator, BotInfo, ChatLogger,
  DynamicVoiceChannel, Economy, UptimeHeartbeat, MusicPlayer, NtustAnnouncements, Ticket and
  VoiceLogger; its `.env` sets `COMPOSE_PROFILES=music` for the Lavalink node.
- The shop's bot in `~/selfhost/Discord/xincord-shirotsuki` runs Economy, UptimeHeartbeat and
  TicketAwayNotice, without a node.
- Each token is `XINCORD_TOKEN` in the bot's `.env`; `config.yaml` keeps `token: ""`.
- The launchd job `tw.xinshou.xincord-backup` runs `~/selfhost/Discord/xincord-backup.sh` daily at
  04:30: `python -m xincord.core.backup` for both bots, the newest 7 kept in each `backups/`
  (log: `~/Library/Logs/xincord-backup.log`).

## Not enabled in production

Before enabling another plugin there:

- Feedback: delete `plugins/Feedback/lang/*/register.yaml` (older files with the `feedbacker` key)
  so that the bundled `/feedback` files are exported, and add `form_failure` and
  `form_submit_failure` to its `config.yaml` for zh-TW texts.
- TicketAwayNotice on the main bot: check that `guild_id` is the shop's guild.
- NtustCourseWatch: set `semester` and `start`.

## Production follow-ups

- Backups: copy `backups/` off the host (#7: Google Drive).
- MusicPlayer: check the panel's emojis on the production application (`emojis` in its
  `config.yaml`). The node uses a youtube-source snapshot (`youtube-remote-cipher`): move back to a
  release once one holds the TV client's fix (#3); it depends on the public yt-cipher unless
  `YOUTUBE_CIPHER_URL` names a server of your own.
- After 2026-10-15: delete the migration's copies on the production host (#8).

## To watch

- VoiceLogger: a voice channel status change names its member. Discord's
  `VOICE_CHANNEL_STATUS_UPDATE` and the audit log entries 192 and 193 were not observed on a real
  guild; if a status set by a member shows `-`, read the bot's log.
- ChatLogger: whether pins and link previews log edits (members' never do; a bot's rich preview
  would), and how long a large purge takes to post.
- DynamicVoiceChannel: two members who join an empty lobby at the same instant may both stay in the
  lobby without a room.
- Ticket: a long archive near Discord's rate limits, and authors whose names Discord refuses for
  webhooks (the archive renames them).
- NtustAnnouncements: TWCA's intermediate certificate in the package expires on 2030-10-16; if
  NTUST changes its certificates, check the log for TLS failures on the boards.

## Releases and dependencies

- PyPI's first release is 1.0.0: the trusted publishers (environments `pypi` and `pypi-plugins`)
  and LICENSE (in both distributions since `license-files`) are in place; the owner picks the time.
- Renovate runs since 2026-10-12 (Dependency Dashboard #6). Its first PRs wait for the owner: #4
  (uv's image 0.13.0, minor) and #5 (the runners to Ubuntu 26.04, major); they predate CI's image
  job, so rebase them first (the checkbox in each PR). Check that the first patch PR merges itself
  after CI.
- If a Dependabot uv security PR fails on the lock file (GitHub documents uv 0.11; `uv.lock` comes
  from uv 0.12), turn on Renovate's `vulnerabilityAlerts` instead.
