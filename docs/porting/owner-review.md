# Owner review queue

What is left for the owner after the review walk-through (2026-10-12): the cutover's steps, what to
watch once the bot runs in production, and the release settings. The user-visible changes, choices
and manual checks listed here before were answered, verified or skipped, and the rest stands as
implemented (`HANDOFF.md`, section 6); each archived change's `design.md` and
`docs/porting-guide.md` keep them.

When an item is done, record it in `HANDOFF.md` section 6 and delete it here; delete a section once
it is empty.

## Cutover

- Turn on the privileged intents of the enabled plugins for the production application in the
  developer portal (Bot, Privileged Gateway Intents): Server Members, Presence (TicketAwayNotice)
  and Message Content (ChatLogger, and Ticket's archive of other members' messages). v3 requested
  the same ones for ChatLogger and TicketAddons; without them, Discord refuses the connection
  (4014).
- The production host's `.env`: `LAVALINK_PASSWORD` (the same as `lavalink.password` in
  `plugins/MusicPlayer/config.yaml`), `TZ=Asia/Taipei` (Giveaway's typed end times, Ticket's
  archive times and NtustAnnouncements' `{{now}}`; UTC when unset) and Spotify's keys if wanted.
- Run `migrate_v3` on a copy of the stopped v3 directory: it moves the renamed plugins'
  directories, so restoring `config.v3.yaml` alone no longer brings v3 back (its report lists the
  moves), and a running v3 would recreate the old directories. It counts a plugin as enabled only
  with `enabled: true` (v3 3.3.0 and later): check the `plugins` list afterwards.
- After `migrate_v3`, delete `plugins/Feedback/lang/*/register.yaml` (v3's, with the `feedbacker`
  key) so that the bundled files with `/feedback` are exported, and set the guild's permission
  overrides of `/feedbacker` again on `/feedback`, which gets a new command ID.
- The bot's permissions (Administrator covers them): Manage Channels and Manage Roles where tickets
  open and in DynamicVoiceChannel's categories; View Audit Log for VoiceLogger's status changes;
  Send Messages in Threads, Create Public Threads and Manage Webhooks in Ticket's archive channel;
  Read Message History in tickets, in ChatLogger's logged channels and where v3's posts are (the
  core upgrades their IDs); View Channel, Send Messages and Embed Links wherever it posts.
- Then a smoke test in production: press a v3 Ticket panel (the ticket opens and the IDs are
  rewritten); in a v3 ticket and in the new one, lock, unlock, save and delete as staff (deleting
  from a v3 row logs the core's failed upgrade once, since the message is gone); join a
  DynamicVoiceChannel lobby once (the new lobby on top, the room right below it); read the log for
  warnings.

## Plugins at cutover

### Feedback
- Add `form_failure` and `form_submit_failure` to the existing `plugins/Feedback/config.yaml` for
  zh-TW texts, and press one star of a v3 form if any remains.

### Economy
- Keep the existing `plugins/Economy/config.yaml` (it lists the administrators); its `enabled` and
  Google Sheets keys can be deleted to silence the warnings.

### DynamicVoiceChannel
- Delete v3's leftover rooms by hand (only v3's MongoDB knows them).

### Ticket
- Migrate v3's panels (the one-off migration) before anyone uses `/add-ticket` on a v3 panel (until
  then a new button takes index 0, the v3 button's, and both open the new entry) and before staff
  need the control rows of v3's ticket channels (until then lock and unlock answer the not-found
  text).

### TicketAwayNotice
- After `migrate_v3` moved `plugins/TicketAddons/`, check that `guild_id` is the shop's guild: the
  guild filter now applies, so a wrong value stops the notices (the READY check names it).

### NtustAnnouncements
- Migrate v3's stored lists (a one-off script) before enabling the plugin, or its first pass posts
  every board's first page.
- In the migrated `plugins/NtustAnnouncements/config.yaml`: add `boards` with the 18 channel IDs,
  replace `prompt` with the bundled one, add `reject-texts`, `reviewers` and (optionally)
  `review-prompt`, and set a current `model` (the default `gemini-2.5-flash` is v3's); or start
  from the bundled file, as on the test guild.

### NtustCourseWatch
- Optionally restore the registrations of v3's MongoDB document (archived design, "Registrations
  and the v3 data import"); v3 lost them at each restart.
- Before each course selection, set `semester` and `start`; during the first one, check in the log
  that NTUST answers the per-code requests under load.

### MusicPlayer
- The production application needs v3's emojis, by v3's names; a missing one shows as a Unicode
  emoji.

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

- Before the 1.0.0 tag: pending trusted publishers on PyPI for `xincord` and `xincord-plugins`
  (owner `xinshoutw`, repository `xincord`, workflow `release.yml`, environment `pypi`), and
  LICENSE, which the owner adds (the repository is public without it); then Claude checks that
  both distributions carry it.
- Renovate: its first run opens the Dependency Dashboard issue (not seen by 2026-10-12, 02:00
  Asia/Taipei); check that its first patch PR merges itself after CI.
- If a Dependabot uv security PR fails on the lock file (GitHub documents uv 0.11; `uv.lock` comes
  from uv 0.12), turn on Renovate's `vulnerabilityAlerts` instead.
