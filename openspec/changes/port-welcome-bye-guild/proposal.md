## Why

Decision C1 ports WelcomeByeGuild after SimpleCommand, and F3 lists it as in use. v3's
WelcomeByeGuild (`Plugins/WelcomeByeGuild`, 7 Kotlin files, 633 lines) posts a welcome embed when a
member joins a guild and a bye embed when one leaves, in channels that administrators bind per
guild with four guild commands. The bindings live in one JSON file per guild.

## What Changes

- New plugin package `xincord.plugins.welcome_bye_guild`, registered as `WelcomeByeGuild`, with the
  members intent and v3's en-US and zh-TW lang files (`register.yaml` and 13 message templates
  each), two zh-TW typos corrected. No `config.yaml`: v3's only key was `enabled`.
- Four administrator guild commands keep v3's names, descriptions, localizations and the optional
  `channel` option that offers text channels only: `welcome-channel-bind`,
  `welcome-channel-unbind`, `bye-channel-bind` and `bye-channel-unbind`. They bind the option's
  channel or the command's text channel, or unbind, and answer ephemerally in the guild's locale
  with v3's templates and `wbg@` placeholders, after v3's runtime Administrator check.
- Each guild's channel IDs are kept in the core store (namespace `WelcomeByeGuild`, key = the guild
  ID) as v3's document `{"welcomeChannelId": ..., "byeChannelId": ...}`, changed under the guild's
  lock; read-only paths write nothing.
- Joins post `welcome`, and departures (leave, kick, ban, through `on_raw_member_remove`) post
  `bye`, in the bound text channel, in the guild's locale, with v3's member placeholders. A message
  that Discord refuses is logged.
- A guild's bindings are deleted when the bot leaves it and, when the bot is ready, for every guild
  it left while it was offline or while the plugin was off.
- Core: v3's `Placeholder.get(event)` moves from _Example into `xincord.core.placeholders` as
  `placeholder_values(interaction)`, which _Example now imports. `interaction_values` no longer
  fails in a thread whose parent channel is not cached (discord.py's `Thread.category` raises
  there), which would have left such a command unanswered.
- v3's defects are fixed: the commands answer in threads, voice channel chats and announcement
  channels (v3 gave no reply there, and saved a binding chosen with the option silently), so
  `invalid-channel` reaches the administrator; names are no longer expanded as placeholders;
  read-only paths no longer create data; bindings of guilds the bot left no longer linger.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:18-80`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:25-303`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuildSubstitutorFactory.kt:12-113`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuildMessageKeys.kt:3-20`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/CmdFileSerializer.kt:7-32`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/Register.kt:12-75`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/config.yaml:1`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/info.yaml:1-9`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/lang/en-US/register.yaml:1-23`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/lang/zh-TW/register.yaml:1-23`
- `XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/lang/en-US/message/` (13
  templates) and `lang/zh-TW/message/` (13 templates)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:30-82`
  (`Placeholder.get` for users, members and slash commands) and `:145-276` (`putGuild`, `putUser`,
  `putMember`, `putEvent`, `putTextChannel`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-41`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30` (the
  ephemeral auto-defer)

Out of scope: importing v3's `plugins/WelcomeByeGuild/data/<guildId>.json` files (Resolution 3 and
B11 defer data migration; the stored document keeps v3's shape so that a migration can copy it); a
check of the bot's permissions in a channel when it is bound; per-guild templates; the Web
Dashboard's toggle and reload (B13).

## Capabilities

### New Capabilities

- `plugin-welcome-bye-guild`: the WelcomeByeGuild plugin.

### Modified Capabilities

- `core-placeholders`: adds v3's `Placeholder.get(event)`, the acting user's and the interaction's
  values in one call; a thread whose parent channel is not cached gives no category instead of
  failing the interaction values.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/welcome_bye_guild/` and its entry point
in `packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/welcome_bye_guild/` and
golden data in `tests/fixtures/plugins/welcome_bye_guild/`; new fields on the shared fakes in
`tests/support/discord_fakes.py`. Core: `placeholder_values` and its Protocols in
`xincord.core.placeholders`; `xincord.plugins.example` uses it. No new dependencies. Operators who
move from v3 keep their `plugins/WelcomeByeGuild/lang/` files, and bind the channels again until a
data migration exists.
