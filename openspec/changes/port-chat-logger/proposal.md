## Why

Decision C1 ports ChatLogger after VoiceLogger, and F3 lists it as in use. v3's ChatLogger
(`Plugins/ChatLogger`, 11 Kotlin files, 995 lines) stores the text of every guild message in SQLite
and, when a stored message is edited or deleted, posts an embed with the text before and after to
the "listen" channels an administrator set up. Each listen channel has its own settings (allow or
block mode, lists of channels and categories), changed through an ephemeral menu: v3 copied that
code from VoiceLogger, which xincord already ported. It is the first plugin that stores message
content, which needs Discord's privileged message content intent, and the first whose data grows
with the guilds' traffic: decision B8 left open where that log lives.

## What Changes

- The listen channel code that VoiceLogger and ChatLogger share (the settings, their store, the
  settings menu and its components, the posts to listen channels and the checks at READY) moves out
  of `xincord.plugins.voice_logger` into `xincord.plugins.listen_channels`, a package that both
  plugins import and that is no plugin itself. VoiceLogger keeps its behavior and its tests.
- New plugin package `xincord.plugins.chat_logger`, registered as `ChatLogger`, with no
  dependencies, the guild messages and message content intents, v3's en-US and zh-TW lang files
  (`register.yaml`, `placeholder.yaml` and six message templates per locale) and a `config.yaml`
  with v3's `log_all` and a new `retention_days`.
- v3's guild command `/chat-logger setting` keeps its texts, localizations and the Administrator
  default; it shows the current channel's settings ephemerally with v3's four buttons and channel
  select menus. Settings are kept per guild in the shared store as v3's JSON document under the
  namespace `ChatLogger`.
- Guild messages that the bot did not send are stored in the plugin's table of the shared SQLite
  store (`ChatLogger_messages`, one row per message): from every channel with `log_all: true`, from
  the detected channels only with `log_all: false`. A stored message's edit and its deletion,
  bulk deletions included, are posted with v3's two templates in the guild's locale to every listen
  channel whose settings detect the message's channel.
- Stored messages are kept for `retention_days` days (default 30): when the bot is ready and every
  hour after, older ones are deleted. A deleted message's text is removed once its deletion is
  handled.
- The data of a guild is deleted when the bot leaves it (the stored messages when `log_all` is
  false, as v3 intended), and, when the bot is ready, for guilds it left while offline; channels
  deleted from the allow and block lists are dropped, as v3's startup did.
- v3's defects are fixed: corrupt or stale settings no longer disable the plugin; a listen
  channel's first selection keeps the allow mode; "Delete" deletes one listen channel's settings;
  `log_all: false` stores the detected channels instead of a frozen set; deletions by authors who
  left are logged; long texts and lists no longer break the logs and the menu; threads are logged;
  one missing listen channel no longer stops the others; typed `%...%` is shown as written; a
  missing category shows `-`; the text keeps the content of messages with embeds and no `null`;
  the menu works in every channel; bulk deletions are logged; updates that keep the text, such as a
  pin or a link preview, are not logged as edits.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:23-131`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:31-382`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChannelData.kt:8-78`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/JsonManager.kt:17-118`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/json/JsonData.kt:5-15`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/command/Register.kt:11-33`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/config/ConfigSerializer.kt:6-11`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Exceptions.kt:3`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/info.yaml:1-17` and `config.yaml:1-2`
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml`, `placeholder.yaml` and the six files under `message/`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:44-75`
  (`Placeholder.get(member)` and `Placeholder.get(event)`)

Out of scope: moving v3's `plugins/ChatLogger/data/<guildId>.db` and `setting/<guildId>.json` into
the store, which the deferred data migration does (B11); removing single entries from the allow and
block lists, which v3 never offered; storing attachments, stickers and reactions, which v3 did not
store; a command to purge stored messages; the Web Dashboard's toggle and reload (B13).

## Capabilities

### New Capabilities

- `plugin-chat-logger`: the ChatLogger plugin.

### Modified Capabilities

None: VoiceLogger's requirements stay as they are while its listen channel code moves.

## Impact

New packages `packages/xincord-plugins/src/xincord/plugins/listen_channels/` and
`packages/xincord-plugins/src/xincord/plugins/chat_logger/`, and the `ChatLogger` entry point in
`packages/xincord-plugins/pyproject.toml`; VoiceLogger's `settings.py` and `store.py` move into the
shared package, and its cog keeps only the voice and status code. Tests under
`tests/plugins/chat_logger/` (VoiceLogger's tests follow the moved code), golden data in
`tests/fixtures/plugins/chat_logger/`. Data: one JSON document per guild in the key-value table and
one table, `ChatLogger_messages`, in the shared `data/xincord.db`. No core change and no new
dependency. Operators must allow the Message Content intent in the developer portal before they
enable the plugin, or Discord refuses the bot's connection. Operators who move from v3 keep their
`plugins/ChatLogger/lang/` files; their listen channels must be set up again until the deferred
migration, and messages stored by v3 are not read.
