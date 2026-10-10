# core-placeholders Specification

## Purpose
Substitutes `%key%` placeholders in template text in one pass and provides the v3 placeholder keys
for users, members, guilds, channels and events.

## Requirements

### Requirement: Placeholders are replaced in a single pass
Rendering SHALL replace each `%key%` whose key has a value, scanning left to right once. Keys
without a value SHALL stay as written, and a `%` that does not close a known key MAY open the next
placeholder. `$%` SHALL produce a literal `%`. Substituted values SHALL never be scanned again.

#### Scenario: Known and unknown keys
- **WHEN** `Hi %user_name%, %missing%!` is rendered with a value for `user_name` only
- **THEN** the result is `Hi Alice, %missing%!`

#### Scenario: Values are not expanded again
- **WHEN** the value of `user_name` is `%bot_name%` and `bot_name` also has a value
- **THEN** the result contains `%bot_name%` literally

#### Scenario: Percent signs and escapes
- **WHEN** `100% of %user_name%` and `$%user_name%` are rendered
- **THEN** the results are `100% of Alice` and `%user_name%`

### Requirement: Every render uses only its own values
Rendering SHALL depend only on the text and the values passed to that call, and SHALL NOT modify
the values. No placeholder state SHALL be kept between renders.

#### Scenario: Values do not leak between renders
- **WHEN** a text is rendered with a value for `extra` and then rendered again without it
- **THEN** the second result keeps `%extra%` as written

### Requirement: Acting-user values follow v3
The acting-user family SHALL provide `bot_id`, `bot_name`, `user_id`, `user_mention`,
`user_name` and `user_avatar_url`, and for guild members also `member_display_name`,
`member_avatar_url` and `member_fixed_name` (`nickname (name)` with a nickname, else the name).

#### Scenario: Member with a nickname
- **WHEN** the acting user is a member named `alice` with nickname `Al`
- **THEN** `member_fixed_name` is `Al (alice)` and `user_name` is `alice`

#### Scenario: Plain user
- **WHEN** the acting user is not a member
- **THEN** no `member_` keys are present

### Requirement: User and member values follow v3
The user family SHALL provide the twelve v3 `user_` keys and the member family the ten v3
`member_` keys, each with an optional prefix. Missing text SHALL become the none value (default
`-`), missing numbers `0`. Member roles exclude the default role, highest first.

#### Scenario: User keys
- **WHEN** user values are built with prefix `wbg@`
- **THEN** every key starts with `wbg@` and `user_global_name` is `-` when the user has none

#### Scenario: Member roles
- **WHEN** a member has the default role and two others
- **THEN** `member_roles_count` is 2 and the mentions list the higher role first

### Requirement: Guild values follow v3
The guild family SHALL provide the twenty v3 `guild_` keys with an optional prefix, including the
JDA locale enum name as `guild_locale` and `guild_booster_count` as an alias of
`guild_boost_count`. Missing text SHALL become the none value, missing ids and counts `0`.

#### Scenario: Guild without icon or system channel
- **WHEN** a guild has no icon and no system channel
- **THEN** `guild_icon_url` is `-` and `guild_system_channel_id` is `0`

#### Scenario: Guild locale name
- **WHEN** the guild's preferred locale is zh-TW
- **THEN** `guild_locale` is `CHINESE_TAIWAN`

### Requirement: Channel and event values follow v3
The channel family SHALL provide `<base>_id`, `<base>_name`, `<base>_mention` and `<base>_type`
(the JDA channel type name) with base `channel` by default, using `0` and the none value when there
is no channel. The event family SHALL provide `event_type` and the event time as unix seconds,
milliseconds and ISO-8601 in UTC.

#### Scenario: Missing channel
- **WHEN** channel values are built for no channel
- **THEN** the id is `0` and the name, mention and type are `-`

#### Scenario: Event time
- **WHEN** event values are built for 2026-01-02 03:04:05.678 UTC
- **THEN** the unix, millisecond and ISO values are 1767323045, 1767323045678 and
  `2026-01-02T03:04:05.678Z`

### Requirement: Locale names follow JDA
Each Discord locale SHALL map to JDA 6.4.1's enum name and native name; unknown locales SHALL map
to `UNKNOWN` and `Unknown`.

#### Scenario: Known and unknown locale
- **WHEN** the names of `en-US` and of an unknown locale are requested
- **THEN** they are `ENGLISH_US` with `English, US`, and `UNKNOWN` with `Unknown`

### Requirement: Command interaction values follow v3
For an application command interaction the placeholders SHALL give `command_name`,
`full_command_name` (with the subcommand group and subcommand), `subcommand_name` when one was
used, and `command_string` as JDA built it: `/`, the full name, then ` name: value` per option,
with channels as `#name` and users and roles as `@name`. Context menu commands SHALL give their
name as `command_string`.

#### Scenario: Subcommand with options
- **WHEN** `/ticket panel create` runs with a channel, a user, a role, a boolean and a text option
- **THEN** `command_string` is
  `/ticket panel create where: #general owner: @alice role: @Mods pinned: true title: Hi`,
  `full_command_name` is `ticket panel create` and `subcommand_name` is `create`

#### Scenario: Context menu command
- **WHEN** the message context command `Report` runs
- **THEN** `command_name` and `command_string` are `Report` and there is no `subcommand_name`

### Requirement: Component interaction values follow v3
For a component interaction the placeholders SHALL give `component_id` and, from the component
with that ID on the message, a button's `component_label`, `component_style` (the JDA style
name), and `component_emoji` and `component_emoji_name` when set, or a select's `component_min`,
`component_max` and `component_placeholder` when set.

#### Scenario: Button and select
- **WHEN** a button with a custom emoji inside a container, and a select with a placeholder, are
  used
- **THEN** the button gives its label, `PRIMARY`, the formatted emoji and its name, and the select
  gives its minimum, maximum and placeholder

#### Scenario: Unknown component
- **WHEN** the message has no component with the interaction's ID, or there is no message
- **THEN** only `component_id` is given for the component

### Requirement: Interaction language and channel follow v3
Every interaction SHALL give `language`, the JDA native name of the user's locale, and, when its
channel has a name, `channel_id` and `channel_name`, plus `channel_category_name` when the channel
is in a known category. A thread whose parent channel is not cached SHALL give no category instead
of failing.

#### Scenario: Guild channel and direct message
- **WHEN** a zh-TW user interacts in `general` under the category `Text`, and later in a direct
  message
- **THEN** the first gives the zh-TW native name, the channel's ID and name and `Text`, and the
  second gives only `language`

#### Scenario: Thread with an uncached parent
- **WHEN** a command runs in a thread whose parent channel discord.py has not cached
- **THEN** the values give the thread's ID and name and no `channel_category_name`

### Requirement: Event values follow v3's Placeholder.get(event)
The event family SHALL give, for an interaction, the acting-user values of its user with the bot's
keys, merged with the interaction values, as v3's `Placeholder.get(event)`. Before the bot has
logged in, when the client has no user, it SHALL give the interaction values only.

#### Scenario: Member runs a command
- **WHEN** the member `alice` with the nickname `Al` runs `/bind` in `general` and the bot is
  `xincord`
- **THEN** the values hold `bot_name` `xincord`, `user_name` `alice`, `member_fixed_name`
  `Al (alice)`, `command_string` `/bind` and `channel_name` `general`

#### Scenario: Bot not logged in
- **WHEN** the client has no user yet
- **THEN** the values hold the interaction's keys and no `bot_`, `user_` or `member_` keys

### Requirement: Global values follow v3
`global_values(client)` SHALL give v3's global placeholders, `bot_id` and `bot_name` of the
client's user, which v3 used for templates rendered without a user. Before the bot has logged in,
when the client has no user, it SHALL give no values.

#### Scenario: Bot logged in
- **WHEN** the client's user is `xincord` with the ID 99
- **THEN** the values are exactly `bot_id` `99` and `bot_name` `xincord`

#### Scenario: Bot not logged in
- **WHEN** the client has no user yet
- **THEN** there are no values
