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
