## Why

Decision C1 ports Ticket after Giveaway, and F3 lists it as in use. v3's Ticket (`Plugins/Ticket`,
8 Kotlin files, 1583 lines) lets administrators build ticket panels (an embed with a button)
through an ephemeral builder, `/create-ticket` for a new panel and `/add-ticket` for a button on an
existing message. A member who presses a panel button gives a reason in a modal, and the bot opens
a private text channel for the member and the panel's staff roles, with a control row that locks
and unlocks the member, saves the conversation into a thread of another channel through a
temporary webhook, and deletes the channel. Panels are kept per guild as JSON. It is the first port
with channels created for members, permission overwrites, webhooks and a channel's whole history.

## What Changes

- New plugin package `xincord.plugins.ticket`, registered as `Ticket`, with no intents beyond
  discord.py's defaults, no `config.yaml` (v3's only key was `enabled`), v3's en-US and zh-TW lang
  files (`register.yaml`, seven message and seven modal templates) and a new `text.yaml` per locale
  holding the texts that v3 wrote in its code (replies, errors, the control row's labels, the
  archive's markers and the builder's defaults), so that Python holds no CJK text.
- The guild commands `/create-ticket` and `/add-ticket message_id` keep v3's names, descriptions,
  localizations, option and default Administrator permission.
- The builder keeps v3's screens, buttons, selects, modals, pre-filled values and preview; the
  panel keeps v3's button and modal; the ticket channel keeps v3's name (the member's username),
  overwrites, opener and control row; delete and save keep v3's checks, and the archive keeps v3's
  thread and webhook names, order, forwarded fields, thread flattening and markers.
- Panels are v3's per-guild documents in the store (namespace `Ticket`, key the guild ID, v3's JSON
  unchanged); every change runs under the guild's lock, and a guild's panels go when the bot leaves
  it, as in v3.
- v3's panels and ticket channels keep working: the routes take v3's IDs (`ticket@a:press;f:0`,
  `ticket@a:lock;d:<hex>;e:<id>;f:<n>`), and the core upgrades a message's IDs after their first
  use.
- v3's defects are fixed (see `design.md`): the preview button opens the reason modal; zh-TW users
  can change the button's text and emoji; the builder answers through each interaction, so it keeps
  working after 15 minutes; colors take `#RRGGBB`, `0xRRGGBB` and `RRGGBB`; a value that Discord
  refuses is reported and leaves the draft; a message ID that is not a number, a message without an
  embed or a full first row is reported; confirming reports failures and keeps the builder; added
  buttons keep the message's other rows and embeds and take the stored index; a missing category or
  panel is reported to the member; long reasons are split instead of losing the controls; the bot
  gets its own overwrite in the ticket channel; the opener pings the staff roles only and the
  archive pings nobody; every archive failure is reported and removes the webhook.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:18-89`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:56-879`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:17-332`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:23-196`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/command/Register.kt:11-43`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/command/CmdFileSerializer.kt:7-27`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/json/serializer/JsonData.kt:3-10`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/info.yaml:1-9`
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml:1-11`, `message/*.yaml`, `modal/*.yaml`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40` (the
  per-guild files)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247` (v3's IDs)

Out of scope: reading v3's `plugins/Ticket/data/*.json` (the v3 data import is a separate change; the
documents keep v3's shape so that it can copy them); a limit of open tickets per member, a cooldown
or a confirmation before deletion (v3 had none); deleting panels whose message was deleted (v3 kept
them); clearing a selected category or role list in the builder (v3's selects need one value);
copying embeds, stickers, reactions, polls, replies or edit history into the archive (v3 copied
text and attachments only); progress reports or a time limit for long archives; the Web Dashboard
(B13).

## Capabilities

### New Capabilities

- `plugin-ticket`: the Ticket plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/ticket/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/ticket/` and golden data in
`tests/fixtures/plugins/ticket/`; additions to `tests/support/discord_fakes.py`. UptimeHeartbeat's
URL redaction moves into a shared package, `xincord.plugins.redaction`, which the archive's error
texts use too (UptimeHeartbeat behaves as before). No core change and no new dependency. Operators
who move from v3 keep their `plugins/Ticket/lang/` files (their `config.yaml` is no longer read);
the new `text.yaml` files are exported next to them. TicketAwayNotice (v3 TicketAddons), ported
next, matches channel names that Ticket creates (see `design.md`, "Channel names").
