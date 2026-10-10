## Why

Decision C1 ports DynamicVoiceChannel after Economy, and F3 lists it as in use. v3's
DynamicVoiceChannel (`Plugins/DynamicVoiceChannel`, 7 Kotlin files, 539 lines) turns voice
channels into "lobbies": when a member joins an empty lobby, that channel becomes the member's room
(renamed from a format, moved below the lobby, with the member allowed to manage it) and a copy of
the lobby takes its place; rooms are deleted once they are empty. It is the first port that creates
and deletes Discord channels and must find them again after a restart.

## What Changes

- New plugin package `xincord.plugins.dynamic_voice_channel`, registered as `DynamicVoiceChannel`,
  with no dependencies (v3's unused SQLiteAPI dependency is gone), the voice states intent, v3's
  en-US and zh-TW lang files (`register.yaml` and four messages per locale) and no `config.yaml`
  (v3's only key was `enabled`).
- v3's guild command `/dynamic-voice-channel` keeps its two subcommands, `bind channel
  format-name-1 format-name-2` and `unbind channel`, with v3's texts, localizations and the
  Administrator default; the `channel` options offer voice channels only. The replies edit the
  ephemeral deferred response with v3's four templates in the user's locale.
- Bindings are kept per guild in the shared store as v3's JSON document
  (`[{"categoryId", "defaultName", "formatName1", "formatName2"}]`) under the namespace
  `DynamicVoiceChannel` and the guild's ID; the rooms the plugin created are kept per guild under
  `DynamicVoiceChannel.rooms` (v3 kept them in the embedded MongoDB).
- A member who joins an empty lobby gets the lobby as a room: the lobby is copied (the copy is the
  new lobby, at position 0), and the joined channel is renamed from format 1 (`%dvc@custom_name%`
  and v3's member keys), moved to position 1 and gives the member Manage Channels and Manage
  Permissions. Rooms are deleted when they are empty.
- When the bot is ready, and when the plugin loads into a ready bot, the plugin deletes the data of
  guilds it left, drops bindings whose category or lobby is gone (as v3's startup did), deletes
  tracked rooms that emptied while it was away and forgets those that no longer exist.
- v3's defects are fixed: the subcommands answer again (v3's command filter never let them run);
  the `channel` option no longer offers channels that left the response "thinking"; a bind
  replaces a binding instead of adding a duplicate; a room is tracked only once the copy exists, so
  a failed copy no longer gets the lobby itself deleted; a guild's voice changes are handled one
  after another, so a quick leave no longer leaves an orphan room; empty rooms left while the bot
  was away are deleted; a failed step no longer skips the others, and an unusable room name no
  longer costs the member their permissions; data of left guilds is deleted completely, and an
  unavailable guild no longer loses its bindings; stage channels named like a lobby are ignored.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/Event.kt:21-78`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:19-135`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/JsonManager.kt:30-142`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/json/JsonData.kt:3-29`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/command/Register.kt:13-89`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/command/CmdFileSerializer.kt:7-54`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/resources/info.yaml:1-21`
- `XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/resources/lang/en-US/` and
  `lang/zh-TW/` (`register.yaml:1-24` and the four files under `message/`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:44-58`
  (`Placeholder.get(member)`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/mongodb/MemoryCacheDb.kt:21-94` and
  `Core/src/main/kotlin/core/mongodb/CacheCollectionManager.kt:31-97` (the room tracker)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40` (the
  per-guild binding files)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/GlobalUtil.kt:49-50` (the command filter)

Out of scope: moving v3's `plugins/DynamicVoiceChannel/data/*.json` and MongoDB's
`DynamicVoiceChannel.generated_cache` into the store, which the deferred data migration does (B11);
a meaning for `format-name-2`, which v3 stored and never used; the Web Dashboard's toggle and
reload (B13); moving members, limits, or any room command that v3 did not have.

## Capabilities

### New Capabilities

- `plugin-dynamic-voice-channel`: the DynamicVoiceChannel plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/dynamic_voice_channel/` and its entry
point in `packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/dynamic_voice_channel/`
and golden data in `tests/fixtures/plugins/dynamic_voice_channel/`; a voice channel fake in
`tests/support/discord_fakes.py`. Data: two JSON documents per guild in the store's key-value
table. No core change and no new dependency. Operators who move from v3 keep their
`plugins/DynamicVoiceChannel/lang/` files; their bindings must be made again with the command until
the deferred migration, and rooms that v3 created are not deleted by xincord.
