## Why

Decision C1 ports Giveaway after ChatLogger, and F3 lists it as in use. v3's Giveaway
(`Plugins/Giveaway`, 8 Kotlin files, 1426 lines) is an administrator's step-by-step giveaway
builder: `/create-giveaway` opens an ephemeral preview with ten buttons and six modals (title,
description, end time, prizes, winner policy, sponsor, thumbnail); confirming posts a public
giveaway with **Join / Leave**, **Draw Winners** and **Reroll** buttons; a background job draws the
giveaways whose end time has passed and announces the winners. Giveaways are kept per guild as
JSON. It is the first port with a draft held between interactions, a scheduled job that must
survive restarts, and winners drawn at random.

## What Changes

- New plugin package `xincord.plugins.giveaway`, registered as `Giveaway`, with no intents beyond
  discord.py's defaults, v3's en-US and zh-TW lang files (`register.yaml`, seven message and six
  modal templates) and a new `text.yaml` per locale that holds the texts v3 wrote in its code
  (embed fields, statuses, replies and errors), so that Python holds no CJK text.
- `config.yaml` keeps v3's `defaultLocale` and `autoDrawIntervalSeconds` (clamped to 5 to 3600
  seconds) and adds `timeZone`, the zone of the end times, which defaults to the host's as in v3.
  v3's files load unchanged, their `enabled` key only warning; an unknown locale or zone stops
  only this plugin, with the key named.
- The guild command `/create-giveaway` keeps v3's name, description, localizations and default
  Administrator permission. The builder keeps v3's buttons, modals, validations, preview and
  Administrator check at confirmation; the post keeps v3's embed, buttons, permissions (draw: the
  creator or an administrator; reroll: administrators), toggle to join and leave, and ephemeral
  draw results; the automatic draw keeps v3's first pass five seconds after READY and its public
  announcement; winners follow v3's algorithm per prize and policy, drawn with `SystemRandom`.
- Giveaways are v3's per-guild documents in the store (namespace `Giveaway`, key the guild ID,
  v3's JSON unchanged); every change of a guild's giveaways runs under the guild's lock.
- v3's posts keep working: the routes take v3's IDs (`giveaway@a:participate;c:<id>`), and the core
  upgrades the post's IDs after their first use.
- v3's defects are fixed (see `design.md`): a double confirmation no longer creates two giveaways;
  the builder answers through each interaction, so it keeps working after 15 minutes and long
  descriptions or prize lists no longer freeze it; a builder message other than the latest one
  answers that the session expired; a post that cannot be made is reported and keeps the builder;
  posts in threads and every other channel kind are refreshed and announced; draws are saved
  before they are posted, and a draw and the automatic draw can no longer both draw; a giveaway's
  data stays when the bot leaves the guild; an uppercase `HTTPS://` thumbnail is shown; texts in
  one message use one language; typed `%...%` stays as written.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Event.kt:19-118`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:44-633`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-380`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:16-148`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/data/GiveawayData.kt:7-102`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/command/Register.kt:9-24`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/command/CmdFileSerializer.kt:7-11`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/config/ConfigSerializer.kt:5-10`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/config.yaml:1-7`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/info.yaml:1-9`
- `XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml:1-3`, `message/*.yaml`, `modal/*.yaml`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40` (the
  per-guild files)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247` (v3's IDs)

Out of scope: reading v3's `plugins/Giveaway/data/*.json` (the data migration is deferred, B11; the
documents keep v3's shape so that it can copy them); commands to cancel, edit, end early or delete a
giveaway (v3 had none); checking that winners are still members (v3 did not); a time limit on
drafts; coalescing the post refreshes of a burst of joins; years after 9999 in end times (v3 took
`+12026-...`); the Web Dashboard (B13).

## Capabilities

### New Capabilities

- `plugin-giveaway`: the Giveaway plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/giveaway/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/giveaway/` and golden data in
`tests/fixtures/plugins/giveaway/`; small additions to `tests/support/discord_fakes.py` (the
message a channel's `send` and an original response's edit return, and partial messages). No core
change and no new dependency. Operators who move from v3 keep their `plugins/Giveaway/config.yaml`
and `lang/` files; the new `text.yaml` files are exported next to them.
