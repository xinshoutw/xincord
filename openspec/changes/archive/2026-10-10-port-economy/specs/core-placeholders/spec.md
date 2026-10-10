# Spec Delta

## ADDED Requirements

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
