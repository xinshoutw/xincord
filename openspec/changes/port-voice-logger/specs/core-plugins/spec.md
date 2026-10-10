# Spec Delta

## ADDED Requirements

### Requirement: Plugins receive gateway events that discord.py does not parse
`Bot.relay_gateway_event(name)` SHALL make the bot dispatch every gateway event `name` it receives
as `gateway_<name in lower case>`, with Discord's payload as the only argument, after discord.py's
own handling of that event when it has one. Relaying the same event again SHALL change nothing,
and the relay SHALL last as long as the bot.

#### Scenario: An event discord.py does not parse
- **WHEN** a plugin relays `VOICE_CHANNEL_STATUS_UPDATE` twice and the gateway delivers one
- **THEN** the listeners of `gateway_voice_channel_status_update` receive its payload once

#### Scenario: An event discord.py parses
- **WHEN** an event that discord.py already parses is relayed and delivered
- **THEN** discord.py's handling runs first, and the listeners receive the same payload
