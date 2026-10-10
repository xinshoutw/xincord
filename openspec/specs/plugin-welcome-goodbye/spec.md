# plugin-welcome-goodbye Specification

## Purpose
Members who join or leave a guild are welcomed or seen off in channels that its administrators
bind.

## Requirements

### Requirement: The plugin installs as WelcomeGoodbye
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `WelcomeGoodbye`, pointing to `xincord.plugins.welcome_goodbye`, with no dependencies
and the members intent. It SHALL bundle v3's en-US and zh-TW lang files, which its first load
writes to `plugins/WelcomeGoodbye/lang/`, and no `config.yaml`: v3's only key was `enabled`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `WelcomeGoodbye` enabled
- **THEN** it returns `WelcomeGoodbye` from `xincord.plugins.welcome_goodbye` with no
  dependencies and the members intent, and the bot requests that intent

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** the en-US and zh-TW `register.yaml` and the 13 message templates of each exist under
  `plugins/WelcomeGoodbye/lang/`, and no `config.yaml` is written

### Requirement: Each guild's channels are stored
The plugin SHALL keep each guild's welcome and bye channel IDs in the store's `WelcomeGoodbye`
namespace under the guild ID, as v3's document `{"welcomeChannelId": ..., "byeChannelId": ...}`
with `0` for an unbound channel, and change it under the guild's lock. A guild without a document,
or a document without a field, SHALL read as unbound, and setting a channel to its current value
SHALL write nothing.

#### Scenario: Unknown guild
- **WHEN** the channels of a guild without a document are read
- **THEN** both are unbound and the namespace stays empty

#### Scenario: v3's document
- **WHEN** channel 5 is set as guild 10's welcome channel
- **THEN** the store holds `{"welcomeChannelId": 5, "byeChannelId": 0}` under `WelcomeGoodbye`
  and `10`

#### Scenario: Missing field
- **WHEN** guild 10's document holds `welcomeChannelId` only
- **THEN** its bye channel reads as unbound

#### Scenario: Unchanged channel
- **WHEN** a guild without a document has its welcome channel set to `0`
- **THEN** the setter reports the previous channel `0` and the namespace stays empty

#### Scenario: Concurrent changes
- **WHEN** the welcome and the bye channel of one guild are set at the same time
- **THEN** both are stored

#### Scenario: Forgetting a guild
- **WHEN** a guild's channels are deleted
- **THEN** its document is gone and other guilds' documents stay

### Requirement: Templates get v3's wbg@ placeholders
The plugin SHALL render command replies with v3's `Placeholder.get(event)` values and the `wbg@`
keys of the guild, the user, the member, the event `command`, the chosen channel, the operator, the
bound channels and the previous channel; and join and leave messages with v3's `Placeholder.get`
values of the member or user and the `wbg@` keys of the guild, the user, the member when known, the
event `join` or `leave` and the bound channels.

#### Scenario: Command values
- **WHEN** an administrator binds `general` (5) as the welcome channel while `rules` (6) is the bye
  channel
- **THEN** `wbg@channel_*` describe `general`, `wbg@operator_name` is the administrator's name,
  `wbg@welcome_channel_is_set` is `true`, `wbg@bye_channel_name` is `rules`, `wbg@event_type` is
  `command` and v3's interaction keys such as `command_name` are present

#### Scenario: Bound channel no longer cached
- **WHEN** the bound welcome channel is not a text channel of the guild any more
- **THEN** `wbg@welcome_channel_id` and `wbg@welcome_channel_mention` still name it and its name
  and type are `-`

#### Scenario: No previous channel
- **WHEN** the reply has no previous channel
- **THEN** `wbg@old_channel_id` is `0` and `wbg@old_channel_mention` is `-`

#### Scenario: Member event values
- **WHEN** a member joins
- **THEN** the values hold the member's `wbg@user_*` and `wbg@member_*` keys, the guild's
  `wbg@guild_*` keys, `wbg@event_type` `join`, the bound channels and v3's unprefixed member keys

#### Scenario: Departed user
- **WHEN** a user whom discord.py had not cached leaves
- **THEN** the values hold the user's keys, `wbg@event_type` `leave` and no member keys

### Requirement: Administrators bind a channel
On `welcome-channel-bind` or `bye-channel-bind`, the plugin SHALL take the `channel` option, or the
command's channel when the option is omitted, if it is a text channel, and reply `invalid-channel`
without writing otherwise. It SHALL store that channel as the guild's welcome or bye channel and
reply `welcome-bind-success` or `bye-bind-success`, or reply `welcome-bind-already` or
`bye-bind-already` without writing when that channel is already bound.

#### Scenario: Option's channel
- **WHEN** an administrator runs `welcome-channel-bind` with the text channel `general`
- **THEN** `general` is stored as the welcome channel and the reply is `welcome-bind-success`
  naming it

#### Scenario: Command's channel
- **WHEN** `bye-channel-bind` runs without the option in the text channel `general`
- **THEN** `general` is stored as the bye channel and the reply is `bye-bind-success`

#### Scenario: Already bound
- **WHEN** `welcome-channel-bind` names the bound welcome channel
- **THEN** the reply is `welcome-bind-already` and nothing is written

#### Scenario: No text channel
- **WHEN** `welcome-channel-bind` runs without the option in a thread, a voice channel's chat or
  an announcement channel
- **THEN** the reply is `invalid-channel` and nothing is written

#### Scenario: One channel for both
- **WHEN** `general` is bound as the welcome channel and then as the bye channel
- **THEN** both channels are `general`

### Requirement: Administrators unbind a channel
On `welcome-channel-unbind` or `bye-channel-unbind`, the plugin SHALL reply `welcome-unbind-empty`
or `bye-unbind-empty` without writing when no channel is bound, and otherwise store `0` for that
channel and reply `welcome-unbind-success` or `bye-unbind-success`, whose
`%wbg@old_channel_mention%` mentions the previous channel even when it was deleted.

#### Scenario: Nothing bound
- **WHEN** `bye-channel-unbind` runs while no bye channel is bound
- **THEN** the reply is `bye-unbind-empty` and nothing is written

#### Scenario: Unbind
- **WHEN** `welcome-channel-unbind` runs while channel 5 is the welcome channel and 6 the bye
  channel
- **THEN** the welcome channel is `0`, the bye channel stays 6 and the reply is
  `welcome-unbind-success` mentioning `<#5>`

#### Scenario: Deleted channel
- **WHEN** the bound welcome channel was deleted and `welcome-channel-unbind` runs
- **THEN** the reply still mentions it

### Requirement: Only administrators change the channels
Each command SHALL reply `guild-only` when it runs outside a guild and `no-permission` when the
user lacks the Administrator permission, rendered with v3's `Placeholder.get(event)` values, and
then neither read nor change the channels.

#### Scenario: Member without Administrator
- **WHEN** a member without the Administrator permission runs `welcome-channel-bind`
- **THEN** the reply is `no-permission` and nothing is written

#### Scenario: Outside a guild
- **WHEN** a command runs without a guild
- **THEN** the reply is `guild-only`

### Requirement: Replies use the guild's locale
Each command SHALL answer by editing the deferred ephemeral response into its message template,
rendered in the guild's preferred locale, or the user's outside a guild, with a per-file fallback
to zh-TW.

#### Scenario: Guild locale
- **WHEN** a zh-TW user runs `welcome-channel-unbind` in a guild whose preferred locale is en-US
- **THEN** the reply is the en-US `welcome-unbind-empty`

#### Scenario: Other locales
- **WHEN** the guild's preferred locale is Japanese
- **THEN** the reply is the zh-TW one

### Requirement: Members who join are welcomed
When a member joins a guild whose welcome channel is bound and is a text channel the bot knows, the
plugin SHALL send the `welcome` template there, for bots too, rendered in the guild's preferred
locale. It SHALL do nothing when no welcome channel is bound or the channel is gone or not a text
channel, and log a warning when Discord refuses the message.

#### Scenario: Welcome
- **WHEN** a member joins a guild whose preferred locale is en-US, and then one whose locale is
  zh-TW
- **THEN** each guild's welcome channel receives v3's welcome embed in its locale, with the guild's
  name and icon, the member's name and avatar, the member count, the rules channel and the colour
  `#57F287`

#### Scenario: Nothing bound
- **WHEN** a member joins a guild without a welcome channel
- **THEN** nothing is sent

#### Scenario: Channel gone or not a text channel
- **WHEN** the bound welcome channel was deleted or became an announcement channel
- **THEN** nothing is sent

#### Scenario: Message refused
- **WHEN** Discord refuses the welcome message, for example because the bot lacks a permission
- **THEN** a warning that names the guild and the channel is logged

### Requirement: Members who leave are seen off
When a member leaves, is kicked or is banned from a guild whose bye channel is bound and is a text
channel the bot knows, the plugin SHALL send the `bye` template there in the guild's preferred
locale, also when discord.py had not cached the member, and log a warning when Discord refuses it.
It SHALL ignore the bot's own removal, guilds it does not know and guilds without such a channel.

#### Scenario: Bye
- **WHEN** a cached member leaves a guild whose preferred locale is en-US, and then one whose
  locale is zh-TW
- **THEN** each guild's bye channel receives v3's bye embed in its locale, with the colour
  `#ED4245`

#### Scenario: Uncached user
- **WHEN** a user whom discord.py had not cached leaves
- **THEN** the bye channel receives the bye embed with the user's name

#### Scenario: Bot removed
- **WHEN** the removal is the bot's own
- **THEN** nothing is sent

#### Scenario: Nothing to send
- **WHEN** a member leaves a guild without a bye channel, or a guild the bot does not know
- **THEN** nothing is sent

#### Scenario: Bye refused
- **WHEN** Discord refuses the bye message
- **THEN** a warning that names the guild and the channel is logged

### Requirement: Channels are forgotten with the guild
When the bot leaves a guild or is removed from it, the plugin SHALL delete that guild's channels.
When the bot is ready, and when the plugin loads into a ready bot, it SHALL delete the channels of
every guild the bot is no longer in, and keep those of the guilds it is in, unavailable ones
included.

#### Scenario: Bot leaves
- **WHEN** the bot leaves a guild with bound channels
- **THEN** that guild's channels are deleted

#### Scenario: Left while offline
- **WHEN** the bot becomes ready while channels are stored for a guild it is in, an unavailable
  guild and a guild it left
- **THEN** only the left guild's channels are deleted

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads into a ready bot that is not in a guild with stored channels
- **THEN** that guild's channels are deleted

### Requirement: The commands are localized administrator guild commands
The plugin SHALL register v3's guild commands `welcome-channel-bind`, `welcome-channel-unbind`,
`bye-channel-bind` and `bye-channel-unbind` with v3's descriptions, the en-US and zh-TW
localizations of `register.yaml` and the Administrator default permission; the bind commands take
an optional `channel` option that offers text channels only. Each SHALL keep the command tree's
ephemeral defer.

#### Scenario: Command payload
- **WHEN** the plugin is loaded and the commands are translated
- **THEN** the guild payload holds the four commands with v3's names, descriptions, localizations,
  options and the Administrator default permission, and the global payload holds none of them

#### Scenario: Command callback
- **WHEN** a registered command's callback runs after the command tree's check
- **THEN** the response was deferred ephemerally and then edited into the command's reply

#### Scenario: Text channels only
- **WHEN** Discord resolves the `channel` option
- **THEN** the option passes the resolved channel to the callback unchanged
