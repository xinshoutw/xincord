## Why

Decision C1 ports SimpleCommand after BotInfo, and F3 lists it as in use. v3's SimpleCommand
(`Plugins/SimpleCommand`, 5 Kotlin files, 209 lines) registers five administrator guild commands,
`cub-none-card`, `tsib-none-card`, `ctcb-none-card`, `ctcb-remit` and `chpytwtp-remit`. Each posts a
fixed embed with a shop's bank payment instructions publicly in the channel, rendered in zh-TW, and
deletes the core's ephemeral deferral. Operators keep the bank details in the editable message
templates.

## What Changes

- New plugin package `xincord.plugins.simple_command`, registered as `SimpleCommand`, with no
  intents and v3's zh-TW lang files: `register.yaml` and the five message templates, whose bank
  account numbers become example values. No `config.yaml`: v3's only key was `enabled`.
- The five guild commands keep v3's names, the description `generate message`, the zh-TW names and
  descriptions, no options and the administrator default permission; the command tree defers them
  ephemerally.
- Each command renders the template named after it in zh-TW, whatever the user's locale, posts the
  whole message (embeds, and any components or files an operator adds) to the command's channel and
  then deletes the deferred response, as v3 did. v3's defects are fixed: the deferred response is
  deleted only after the message is posted, and when the channel takes no messages or refuses this
  one, the administrator sees the message in the deferred response instead of nothing; the reply no
  longer depends on a core switch.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-62`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:8-58`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:9-60`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/CmdFileSerializer.kt:7-23`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/config.yaml:1`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/info.yaml:1-8`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/register.yaml:1-19`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/cub-none-card.yaml:1-16`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/tsib-none-card.yaml:1-16`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/ctcb-none-card.yaml:1-16`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/ctcb-remit.yaml:1-17`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/chpytwtp-remit.yaml:1-17`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:84-95`
  (the default locale and the global placeholders)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:15-18`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30` (the
  ephemeral auto-defer)

Out of scope: a data-driven command set (commands defined in a config file instead of code, the
inventory's B3); en-US or other localizations, which v3 never had; a runtime permission check
besides the default member permissions; the Web Dashboard's reload path (B13).

## Capabilities

### New Capabilities

- `plugin-simple-command`: the SimpleCommand plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/simple_command/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/simple_command/` and golden
data in `tests/fixtures/plugins/simple_command/`. No core changes and no new dependencies.
Operators who move from v3 keep their `plugins/SimpleCommand/lang/` files, which hold the real
account numbers: only missing lang files are exported.
