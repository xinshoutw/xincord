## Why

Decision C1 ports VoiceLogger after DynamicVoiceChannel, and F3 lists it as in use. v3's
VoiceLogger (`Plugins/VoiceLogger`, 9 Kotlin files, 835 lines) posts an embed to the "listen"
channels an administrator set up whenever a member joins, leaves or switches voice channels, and
whenever a voice channel's status is set, changed or cleared, naming who did it from the audit log.
Each listen channel has its own settings (allow or block mode, lists of voice channels and
categories), changed through an ephemeral menu. It is the first plugin that needs a gateway event
discord.py 2.7.1 does not parse (`VOICE_CHANNEL_STATUS_UPDATE`) and the audit log.

## What Changes

- Core: `Bot.relay_gateway_event(name)` dispatches a gateway event that discord.py does not parse
  as `gateway_<name in lower case>` with Discord's payload, so plugins can listen to it (spec delta
  on `core-plugins`).
- New plugin package `xincord.plugins.voice_logger`, registered as `VoiceLogger`, with no
  dependencies, the voice states intent, v3's en-US and zh-TW lang files (`register.yaml`,
  `placeholder.yaml` and ten message templates per locale) and no `config.yaml` (v3's only key was
  `enabled`).
- v3's guild command `/voice-logger setting` keeps its texts, localizations and the Administrator
  default; it shows the current channel's settings ephemerally with v3's four buttons (toggle the
  mode, add to the allow list, add to the block list, delete) and v3's channel select menus.
- Settings are kept per guild in the shared store as v3's JSON document
  (`{"<listen channel ID>": {"allow_mode", "allow", "block"}}`) under the namespace `VoiceLogger`
  and the guild's ID.
- Voice joins, leaves and switches, and voice channel status changes, are posted with v3's six
  templates in the guild's locale to every listen channel whose settings detect the voice channel.
  The member of a status change comes from the audit log (types 192 and 193).
- The data of a guild is deleted when the bot leaves it, and, when the bot is ready, for guilds it
  left while offline; channels deleted from the allow and block lists are dropped, as v3's startup
  did.
- v3's defects are fixed: corrupt or stale data no longer disables the plugin; a listen channel's
  first selection keeps the allow mode; "Delete" deletes one listen channel's settings instead of
  the guild's file; the switch embed shows the joined channel; a missing category shows `-`; a
  status change is attributed to the matching audit log entry of its own type and channel; one
  missing or refusing listen channel no longer stops the others, and a deleted one is forgotten;
  the menu works in every channel; long lists no longer break the menu; names and statuses are
  shown as written.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:23-110`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:29-439`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/ChannelData.kt:8-77`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:17-117`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/json/JsonData.kt:5-15`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/command/Register.kt:10-32`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/command/CmdFileSerializer.kt:7-23`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/command/PlaceholderSerializer.kt:6-14`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/info.yaml:1-21`
- `XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml`, `placeholder.yaml` and the ten files under `message/`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:44-75`
  (`Placeholder.get(member)` and `Placeholder.get(event)`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40` (the
  per-guild settings files)

Out of scope: moving v3's `plugins/VoiceLogger/setting/*.json` into the store, which the deferred
data migration does (B11); removing single entries from the allow and block lists, which v3 never
offered; logging mutes, deafens, streams and video, which v3 did not log; reading the statuses that
voice channels had before the bot connected (Discord's Request Channel Info); the Web Dashboard's
toggle and reload (B13).

## Capabilities

### New Capabilities

- `plugin-voice-logger`: the VoiceLogger plugin.

### Modified Capabilities

- `core-plugins`: plugins can receive gateway events that discord.py does not parse.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/voice_logger/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; a new public method `Bot.relay_gateway_event` in
`xincord.core.bot`; tests under `tests/plugins/voice_logger/` and `tests/core/`, golden data in
`tests/fixtures/plugins/voice_logger/`; small extensions of `tests/support/discord_fakes.py`
(`FakeRest` answers and query parameters, `FakeGuild.fetch_member`, voice channel URLs) and a
gateway helper in `tests/support/plugin_fakes.py`. Data: one JSON document per guild in the store's
key-value table. No new dependency. Operators who move from v3 keep their `plugins/VoiceLogger/
lang/` files; their listen channels must be set up again with the command until the deferred
migration. Attributing status changes needs the View Audit Log permission, as in v3.
