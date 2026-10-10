# plugin-ticket-away-notice Specification

## Purpose
A new ticket channel gets a notice while the shop's owner is offline.

## Requirements

### Requirement: The plugin installs as TicketAwayNotice
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `TicketAwayNotice`, pointing to `xincord.plugins.ticket_away_notice`, with no dependencies
and the members and presences intents, which the bot then requests. Its first load SHALL write the
bundled `config.yaml` and zh-TW `message/not-online.yaml` to `plugins/TicketAwayNotice/`, even
while the config waits for the operator.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `TicketAwayNotice` enabled
- **THEN** it returns `TicketAwayNotice` from `xincord.plugins.ticket_away_notice` with no
  dependencies and the members and presences intents

#### Scenario: The bot requests the intents
- **WHEN** a bot is created for the enabled `TicketAwayNotice`
- **THEN** its intents include the members and presences intents

#### Scenario: First load writes the files
- **WHEN** the plugin loads in an empty directory with the bundled config
- **THEN** `plugins/TicketAwayNotice/` holds the bundled `config.yaml` and
  `lang/zh-TW/message/not-online.yaml`, and no `register.yaml`

### Requirement: The config names the guild, the owner, the prefixes and the delay
`config.yaml` SHALL keep v3's keys, none with a default: `guild_id` and `user_id`, positive
integers, quoted or not; `prefix`, a non-empty list of texts, numbers read as text as v3 did;
`delay_millis`, 1 to 9223372036854775807 ms. The bundled file SHALL hold v3's prefixes and delay
and 0 for both IDs, so that the plugin loads once the operator sets them. A v3 file SHALL load with
a warning naming `enabled`; an invalid file SHALL disable only this plugin, naming the key.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's: `enabled: true`, both IDs as 18-digit numbers, quoted or not, two
  prefixes and `delay_millis: 2000`
- **THEN** the plugin loads and logs a warning that names `enabled`, and v3's Chinese prefix, which
  the bundled file keeps, matches a channel named after it

#### Scenario: Numbers as prefixes
- **WHEN** `prefix` lists an unquoted `2024`, which YAML reads as a number
- **THEN** the plugin loads with the prefix `2024`, as v3 read it

#### Scenario: Bundled config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it does not load, and the error names `guild_id` and `user_id`

#### Scenario: Invalid values
- **WHEN** `prefix` is empty, `delay_millis` is 0, or `user_id` is not a number
- **THEN** the plugin does not load, and the error names `prefix`, `delay_millis` or `user_id`

### Requirement: New channels whose names start with a prefix are watched
In the guild `guild_id` only, a new channel or thread whose name starts with one of `prefix`,
compared case-sensitively as in v3, SHALL start a notice when it takes messages: text,
announcement, voice and stage channels and threads, except the threads that the bot starts itself
(Ticket's archives). Other guilds and names SHALL be left alone, and so SHALL categories and
forums, which take no messages, without an error.

#### Scenario: Text channel with a prefix
- **WHEN** text channel `ticket-alice` is created in guild 10 while the owner is offline
- **THEN** the channel gets the notice

#### Scenario: Threads and voice channels
- **WHEN** a thread or a voice channel named `ticket-alice` is created in guild 10
- **THEN** it gets the notice

#### Scenario: Another guild
- **WHEN** `ticket-alice` is created in a guild other than 10
- **THEN** no notice starts

#### Scenario: Name without a prefix
- **WHEN** Ticket opens a channel named after the username `alice`, or a channel is named
  `my-ticket-alice` or `TICKET-alice`, with the prefix `ticket-`
- **THEN** no notice starts

#### Scenario: Channels that take no messages
- **WHEN** a category or a forum named `ticket-alice` is created in guild 10
- **THEN** no notice starts, and nothing is logged as an error

#### Scenario: The bot's own thread
- **WHEN** the bot starts a thread named `ticket-alice-2026-10-11`, as Ticket's archive does for a
  ticket channel named `ticket-alice`
- **THEN** no notice starts

### Requirement: The notice waits for the delay while the owner is offline
When a notice starts, the plugin SHALL read the member `user_id` from discord.py's cache, else from
Discord, whose member has no presence and counts as offline, as in v3. Only while that member is
offline SHALL it wait `delay_millis` without holding up other events, then check again that the
channel exists and that the member is offline, and post `not-online` rendered in zh-TW with v3's
global placeholders (`bot_id`, `bot_name`).

#### Scenario: Owner offline
- **WHEN** `ticket-alice` is created while the owner is offline
- **THEN** after a wait of 2 seconds the channel gets the bundled notice

#### Scenario: Owner online, idle or busy
- **WHEN** the owner is online, idle or in do not disturb when `ticket-alice` is created
- **THEN** the plugin neither waits nor posts

#### Scenario: Owner back during the wait
- **WHEN** the owner comes online during the wait
- **THEN** no notice is posted

#### Scenario: Channel gone during the wait
- **WHEN** the channel is deleted, or the bot leaves the guild, during the wait
- **THEN** no notice is posted

#### Scenario: Owner not cached
- **WHEN** discord.py has not cached the owner
- **THEN** the plugin asks Discord for the member and, as that member has no presence, posts the
  notice

#### Scenario: Channels created together
- **WHEN** a second channel with a prefix is created while the first one's notice waits
- **THEN** both wait at once, and each gets the notice

#### Scenario: Operator's v3 notice
- **WHEN** `plugins/TicketAwayNotice/lang/zh-TW/message/not-online.yaml` is an operator's v3-style
  file, its text in the embed title and `%bot_name%` in its footer
- **THEN** the notice shows the title as written and the bot's name in the footer

### Requirement: Problems with notices are reported
When Discord answers that the member `user_id` is not in the guild, refuses to look the member up,
or refuses the notice, the plugin SHALL log a warning that names the guild and the member or the
channel, and post nothing for that channel. Any other failure SHALL be logged as an error with its
traceback. A `not-online` template that cannot be posted, such as one with a component ID, SHALL
keep the plugin from loading, with an error that names the file.

#### Scenario: Owner not a member
- **WHEN** Discord answers that user 20 is not a member of guild 10
- **THEN** a warning names user 20 and guild 10, and nothing is posted

#### Scenario: Refused lookup
- **WHEN** Discord refuses the member request for another reason
- **THEN** a warning names user 20, guild 10 and the error, and nothing is posted

#### Scenario: Refused notice
- **WHEN** the channel refuses the notice
- **THEN** a warning names the channel and guild 10

#### Scenario: Unexpected failure
- **WHEN** the notice fails without an answer from Discord, as when the connection drops
- **THEN** an error names the channel, with the traceback

#### Scenario: Template that cannot be posted
- **WHEN** the operator's `not-online.yaml` holds a button with a `uid`
- **THEN** the plugin does not load, and the error names the file

#### Scenario: Template that Discord refuses
- **WHEN** the operator's `not-online.yaml` holds eleven embeds, or renders an empty message
- **THEN** the plugin does not load, and the error names the file

#### Scenario: Template with a file
- **WHEN** the operator's `not-online.yaml` attaches a file that exists
- **THEN** the plugin loads, the notice uploads the file, and no file stays open

### Requirement: Pending notices end with the plugin
Unloading or reloading the plugin SHALL cancel the notices that wait for their delay and start none
afterwards, even for an event that discord.py dispatched before, so that no notice is posted after
it, without logging an error.

#### Scenario: Unload during the wait
- **WHEN** the plugin unloads while a notice waits
- **THEN** the wait ends, nothing is posted, and no error is logged

#### Scenario: Event after the unload
- **WHEN** a channel creation that discord.py dispatched before the unload reaches the unloaded
  plugin's listener
- **THEN** no notice starts

### Requirement: The guild and the owner are checked when the bot is ready
When the bot becomes ready, and when the plugin loads into a ready bot, the plugin SHALL log a
warning if the bot is not in the guild `guild_id` or if the member `user_id` is not in it. Nothing
SHALL be checked before the bot is ready, and a guild that Discord reports unavailable SHALL be
skipped.

#### Scenario: Ready
- **WHEN** the bot becomes ready without guild 10, or with guild 10 but without user 20
- **THEN** a warning names guild 10, or user 20 and guild 10; with both there, nothing is logged

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads while the bot is ready and not in guild 10
- **THEN** the warning is logged during the load

#### Scenario: Unavailable guild
- **WHEN** guild 10 is unavailable, as during a Discord outage
- **THEN** no warning is logged
