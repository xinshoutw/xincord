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
