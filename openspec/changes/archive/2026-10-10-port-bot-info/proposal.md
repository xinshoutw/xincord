## Why

Decision C1 ports BotInfo after AutoRole, and F3 lists it as in use. v3's BotInfo
(`Plugins/BotInfo`, 5 Kotlin files, 134 lines) registers the global `/bot-info` command, which
answers with an ephemeral embed showing how many guilds the bot is in and the sum of their member
counts. Decision C3 makes it the place where xincord meets AGPL section 13: `/bot-info` also shows
a link to the bot's source code, whose URL is configurable. It is the first plugin with a global
command.

## What Changes

- New plugin package `xincord.plugins.bot_info`, registered as `BotInfo`, declaring the members
  intent (v3's core always requested it, and discord.py keeps member counts current only with it),
  with v3's en-US and zh-TW lang files and a bundled `config.yaml`.
- `config.yaml` has a new `source_url` (default `https://github.com/xinshoutw/xincord`), validated
  as an http or https URL when the plugin loads; v3's file, whose only key was `enabled`, still
  loads with a warning.
- The global `/bot-info` command keeps v3's names, descriptions, localizations, contexts (guilds
  and the bot's DMs, guild installs) and missing default permissions; the command tree defers it
  ephemerally.
- The reply edits the deferred response into v3's `bot-info` embed in the user's locale, with
  the guild count, the summed member count and a new "Source Code" field holding `source_url`.
  v3's defects are fixed: the counts are values of one render instead of keys written into the
  process-wide placeholder map, and the reply no longer depends on a core switch.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:10-37`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/Event.kt:13-60`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/command/Register.kt:8-19`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/command/CmdFileSerializer.kt:7-11`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/config.yaml:1`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/info.yaml:1-8`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/en-US/register.yaml:1-3`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/zh-TW/register.yaml:1-3`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/en-US/message/bot-info.yaml:1-17`
- `XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/zh-TW/message/bot-info.yaml:1-17`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:15-18`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:68-72` (the members intent)

Out of scope: counting unique users instead of v3's per-guild sum; other bot statistics (uptime,
latency, version); a license notice beside the source link; the Web Dashboard's reload path
(B13).

## Capabilities

### New Capabilities

- `plugin-bot-info`: the BotInfo plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/bot_info/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/bot_info/` and golden data
in `tests/fixtures/plugins/bot_info/`; `FakeGuild` in `tests/support/discord_fakes.py` gains a
member count. No core changes and no new dependencies. Enabling the plugin makes the bot request
the privileged members intent, which the bot's application must allow in the Discord developer
portal.
