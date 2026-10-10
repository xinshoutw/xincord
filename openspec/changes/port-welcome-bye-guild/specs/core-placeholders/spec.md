# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
