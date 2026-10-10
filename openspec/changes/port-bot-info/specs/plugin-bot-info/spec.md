# Spec Delta

## Purpose

`/bot-info` shows how many guilds the bot is in, the sum of their member counts and a link to the
bot's source code.

## ADDED Requirements

### Requirement: The plugin installs as BotInfo
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `BotInfo`, pointing to `xincord.plugins.bot_info`, with no dependencies and the members
intent, which the bot then requests. It SHALL bundle a default `config.yaml` and en-US and zh-TW
lang files, which its first load writes to `plugins/BotInfo/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `BotInfo` enabled
- **THEN** it returns `BotInfo` from `xincord.plugins.bot_info` with no dependencies and the
  members intent

#### Scenario: The bot requests the members intent
- **WHEN** a bot is created for the enabled `BotInfo`
- **THEN** its intents include the members intent

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/BotInfo/config.yaml` holds the bundled default and the en-US and zh-TW lang
  files exist

### Requirement: The config sets the source link
`config.yaml` SHALL have an optional `source_url`, `https://github.com/xinshoutw/xincord` by
default, which SHALL be an `http` or `https` URL without spaces and of at most 512 characters. A
v3 config file SHALL load unchanged, with a warning that names its `enabled` key. An invalid value
SHALL disable only this plugin, with an error that names `source_url`.

#### Scenario: Default config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** its source link is `https://github.com/xinshoutw/xincord`

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's, with `enabled: true` only
- **THEN** the plugin loads with the default source link and logs a warning that names `enabled`

#### Scenario: Operator URL
- **WHEN** `source_url` is `https://git.example/bot`
- **THEN** the plugin loads with that source link

#### Scenario: Invalid URL
- **WHEN** `source_url` is empty, has no scheme, uses `ftp`, contains a space or is longer than
  512 characters
- **THEN** the plugin does not load, and the error names `source_url`

### Requirement: The counts sum the bot's guilds
The plugin SHALL count the guilds the bot is in and sum their member counts, as v3 did: a user in
several guilds counts once per guild, and bots count. A guild whose member count is unknown SHALL
add nothing to the sum.

#### Scenario: Guilds and members
- **WHEN** the bot is in two guilds of 3 and 4 members
- **THEN** the counts are 2 guilds and 7 members

#### Scenario: Unknown member count
- **WHEN** the bot is in a guild of 5 members and a guild whose member count is unknown
- **THEN** the counts are 2 guilds and 5 members

#### Scenario: No guilds
- **WHEN** the bot is in no guild
- **THEN** the counts are 0 guilds and 0 members

### Requirement: The reply shows the counts and the source link
The plugin SHALL answer the command by editing the deferred response into the `bot-info` template
in the user's locale, falling back to zh-TW, with `%guild_counts%`, `%member_counts%`,
`%source_url%`, `%bot_id%` and `%bot_name%`. The counts SHALL be taken at each use.

#### Scenario: Reply
- **WHEN** an en-US user runs the command while the bot is in guilds of 3 and 4 members
- **THEN** the response is v3's en-US embed showing 2 servers and 7 members, with a "Source Code"
  field showing `https://github.com/xinshoutw/xincord`

#### Scenario: Locale and fallback
- **WHEN** a zh-TW user, a Japanese user and a British English user run the command
- **THEN** each gets v3's zh-TW embed with the zh-TW source field

#### Scenario: Operator URL in the reply
- **WHEN** `source_url` is `https://git.example/bot`
- **THEN** the source field shows `https://git.example/bot`

#### Scenario: Bot placeholders
- **WHEN** the operator's en-US `bot-info` template has the content `%bot_name% (%bot_id%)` and
  the bot is `xincord` with the ID 99
- **THEN** the response's content is `xincord (99)`

#### Scenario: Counts at each use
- **WHEN** the bot joins a third guild of 5 members between two uses of the command
- **THEN** the second reply shows 3 servers and 12 members

### Requirement: The command is a localized global command
The plugin SHALL register the global command `bot-info`, without options or default member
permissions, usable in guilds and in the bot's DMs and installed with guilds, as JDA's defaults
made v3's. Its name and description SHALL default to v3's and be localized in en-US and zh-TW from
`register.yaml`. The command SHALL keep the command tree's ephemeral defer and answer through the
reply.

#### Scenario: Command payload
- **WHEN** the plugin is loaded and the commands are translated
- **THEN** the global payload holds `bot-info` with v3's name, description and localizations, no
  options, no default member permissions, the guild and bot DM contexts and the guild install
  type, and the guild payload does not hold it

#### Scenario: Command callback
- **WHEN** the registered command's callback runs after the command tree's check
- **THEN** the response was deferred ephemerally and is then edited into the reply
