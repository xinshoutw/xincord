## Why

Decision C1 ports TicketAddons after Ticket, and F3 lists it as in use; the owner renamed it
TicketAwayNotice (`docs/porting/decisions.md`, Amendment 1). v3's TicketAddons
(`Plugins/TicketAddons`, 3 Kotlin files, 95 lines) has no commands, components or data: when a
channel whose name starts with a configured prefix is created, it checks whether one configured
member (the shop's owner) is offline and, if so, posts a fixed "the owner is not online, please
wait" embed into the new channel after a delay. It is the first port with the privileged presences
intent and with delayed work started by an event.

## What Changes

- New plugin package `xincord.plugins.ticket_away_notice`, registered as `TicketAwayNotice`,
  declaring the members and presences intents, with a bundled `config.yaml` and v3's zh-TW
  `message/not-online.yaml` (no `register.yaml`, as v3).
- `config.yaml` keeps v3's keys (`guild_id`, `user_id`, `prefix`, `delay_millis`) so that v3's file,
  which `migrate_v3` moves from `plugins/TicketAddons/`, loads unchanged; v3's `enabled` key only
  warns. The bundled file holds example values: 0 for both IDs, so that the plugin waits for the
  operator, and v3's prefixes (`客服單-`, `ticket-`) and delay (2000 ms).
- A new channel or thread whose name starts with a prefix, in the configured guild, gets the notice
  when the configured member is offline: the plugin waits `delay_millis` without holding up other
  events, checks again that the channel exists and the member is still offline, then posts
  `not-online` in zh-TW with v3's global placeholders. Pending notices end when the plugin unloads.
- v3's defects are fixed (see `design.md`): the guild filter applies; threads, announcement, voice
  and stage channels get the notice and categories and forums are skipped, where v3 threw; the
  member's presence comes from discord.py's member cache, kept by the members and presences
  intents, where v3 read an uncached member as offline almost always; nothing is posted in a channel
  deleted during the wait or once the member came online; the bundled files hold example values
  instead of the shop's IDs and name.
- When the bot is ready, and when the plugin loads into a ready bot, warnings name a configured
  guild that the bot is not in and a configured member who is not in that guild.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39`
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:7-30`
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/config/ConfigSerializer.kt:6-26`
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/config.yaml:1-7`
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/info.yaml:1-13`
- `XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/lang/zh-TW/message/not-online.yaml:1-7`

Out of scope: matching Ticket's channels, which Ticket names after the member's username (the
owner's question about a `ticket-` prefix is in the review queue's Ticket section; this change
keeps v3's prefix matching and leaves Ticket alone); other locales for the notice (v3 rendered
zh-TW for everyone); several owners or guilds (v3 had one of each); notices for channels created
while the bot was offline; the Web Dashboard's reload path (B13).

## Capabilities

### New Capabilities

- `plugin-ticket-away-notice`: the TicketAwayNotice plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/ticket_away_notice/` and its entry point
in `packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/ticket_away_notice/` and
golden data in `tests/fixtures/plugins/ticket_away_notice/`; presence and member builders in
`tests/support/payloads.py`. No core change and no new dependency. Enabling the plugin makes the
bot request the privileged presences and members intents: the developer portal must allow both,
or Discord refuses the bot's connection.
