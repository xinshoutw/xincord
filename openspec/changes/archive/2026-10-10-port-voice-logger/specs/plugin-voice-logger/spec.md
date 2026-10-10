# Spec Delta

## Purpose

Voice joins, leaves, switches and voice channel status changes are posted to the listen channels
whose settings detect the voice channel; administrators set each listen channel up through an
ephemeral menu.

## ADDED Requirements

### Requirement: The plugin installs as VoiceLogger
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `VoiceLogger`, pointing to `xincord.plugins.voice_logger`, with no dependencies and the
voice states intent. It SHALL bundle v3's en-US and zh-TW lang files, which its first load writes
to `plugins/VoiceLogger/lang/`, and no `config.yaml`: v3's only key was `enabled`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `VoiceLogger` enabled
- **THEN** it returns `VoiceLogger` from `xincord.plugins.voice_logger` with no dependencies and the
  voice states intent, and the bot requests that intent

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** the en-US and zh-TW `register.yaml`, `placeholder.yaml` and the ten message templates of
  each exist under `plugins/VoiceLogger/lang/`, and no `config.yaml` is written

### Requirement: Settings are kept per guild in v3's documents
The plugin SHALL keep a guild's settings under `VoiceLogger` and the guild's ID as v3's object of
listen channel IDs to `{"allow_mode", "allow", "block"}`. A missing entry SHALL read as the allow
mode with empty lists, without a write; new entries SHALL start in the allow mode. A change that
changes nothing SHALL write nothing, the last removal SHALL delete the document, and concurrent
changes SHALL never lose one another. A document not of v3's shape SHALL raise and stay.

#### Scenario: First selection
- **WHEN** the channels 30 and 40 are added to the allow list of listen channel 5 in guild 10
- **THEN** the store holds `{"5": {"allow_mode": true, "allow": [30, 40], "block": []}}` under
  `VoiceLogger` and `10`

#### Scenario: Listen channel without settings
- **WHEN** the settings of a listen channel without an entry are read
- **THEN** they are the allow mode with empty lists, and the namespace stays empty

#### Scenario: Toggling and adding
- **WHEN** listen channel 5 is toggled twice, then 40 and 50 are added to its allow list
  `[30, 40]` and 60 to its block list
- **THEN** its mode is block and then allow again, its allow list is `[30, 40, 50]` and its block
  list `[60]`

#### Scenario: Nothing to change
- **WHEN** channels that are already in a list are added again, and a listen channel without an
  entry is removed
- **THEN** nothing is written

#### Scenario: Removing
- **WHEN** listen channel 5 of guild 10 is removed while channel 6 has settings too, and then 6
- **THEN** the first removal keeps 6's entry and the second deletes the document

#### Scenario: Concurrent changes
- **WHEN** 20 listen channels of one guild get settings at the same time
- **THEN** all 20 are stored

#### Scenario: Unreadable settings
- **WHEN** the document is a list, or an entry lacks `block`, holds a text in `allow` or has a key
  that is not a channel ID
- **THEN** reading and changing the guild's settings raise an error and the document stays

### Requirement: Listen channels detect voice channels
A listen channel's settings SHALL detect a voice channel, in the allow mode, when the channel or its
category is in the allow list, and, in the block mode, unless the channel or its category is in the
block list. An event SHALL go to every listen channel of the guild that detects one of its voice
channels: either side of a switch.

#### Scenario: Allow mode
- **WHEN** the allow list holds channel 30 and category 20
- **THEN** channel 30 and channel 31 of category 20 are detected, and channel 32 of category 21
  and channel 33 without a category are not

#### Scenario: Block mode
- **WHEN** the block list holds channel 30 and category 20
- **THEN** channel 30 and channel 31 of category 20 are not detected, and channels 32 and 33 are

#### Scenario: Either side of a switch
- **WHEN** listen channel 5 detects channel 30 only, 6 detects channel 32 only and 7 detects
  neither, and a member switches from 30 to 32
- **THEN** the event goes to listen channels 5 and 6

### Requirement: The settings menu shows the channel's settings
`/voice-logger setting` SHALL edit the deferred response into v3's `voice-logger@setting` template
for the current channel, in the user's locale, with v3's values of the interaction, `vl_channel_mode`
(`ALLOW` or `BLOCK`) and each list in the locale's line format, or `empty` when it has none. A list
longer than 1024 characters SHALL end with `...` after the lines that fit. Nothing SHALL be written.

#### Scenario: Menu
- **WHEN** an administrator with an en-US or a zh-TW client runs the command in channel 5, whose
  settings are the block mode, the allow list `[30]` and an empty block list
- **THEN** the response is v3's settings embed in that locale with `<BLOCK>`, the line of channel 30
  and the `empty` text, and v3's four buttons

#### Scenario: Channel without settings
- **WHEN** the command runs in a channel without settings
- **THEN** the menu shows `<ALLOW>` and `empty` for both lists, and nothing is written

#### Scenario: Long list
- **WHEN** the allow list holds 40 channels with 19-digit IDs
- **THEN** the field holds at most 1024 characters, made of whole lines and `...`

### Requirement: The settings components change the settings
The menu's buttons and select menus SHALL reach the plugin, in v3's `voice-logger@` format too:
`toggle_btn` flips the mode; `modify_allow_btn` and `modify_block_btn` replace the message with the
list's select menu, whose choice adds the channels to the list; these show the updated menu, and
`delete_btn` deletes the channel's settings and shows `delete`. Other actions and component types
SHALL get no response.

#### Scenario: Toggle
- **WHEN** an administrator presses the toggle button of channel 5's menu
- **THEN** the stored mode flips and the message becomes the menu with `<BLOCK>`

#### Scenario: Modify a list
- **WHEN** an administrator with an en-US or a zh-TW client presses the allow list button, then
  chooses channel 30 and category 20 in the select menu
- **THEN** the message becomes v3's select menu alone, for voice channels and categories, 1 to 25
  of them, and then the menu listing 30 and 20, which are stored

#### Scenario: Delete
- **WHEN** an administrator presses the delete button of channel 5's menu while channel 6 has
  settings too
- **THEN** channel 5's settings are deleted, channel 6's stay, and the message becomes v3's `delete`
  embed without components

#### Scenario: v3 IDs
- **WHEN** a button with v3's ID `voice-logger@a:toggle_btn` is pressed
- **THEN** it toggles the mode as the new ID `voice_logger:1:a=toggle_btn` does

#### Scenario: Other actions
- **WHEN** a button has an unknown action, or a button carries a select menu's action
- **THEN** there is no response and nothing is written

### Requirement: The command is a localized administrator guild command
The plugin SHALL register v3's guild command `voice-logger` with the subcommand `setting`, without
options, with v3's names, descriptions and en-US and zh-TW localizations, visible to administrators
by default. The tree SHALL defer it ephemerally.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** the command has v3's texts, localizations and subcommand, and the default member
  permissions are Administrator

#### Scenario: Command callback
- **WHEN** the `setting` subcommand is looked up
- **THEN** its callback is the cog's menu handler, bound to the cog

### Requirement: Voice channel changes are logged
When a member joins, leaves or switches voice channels, the plugin SHALL post `on-channel-join`,
`on-channel-left` or `on-channel-switch` to the detecting listen channels with v3's member values
and the `vl_channel_*` and `vl_category_*` values of each channel: the category's mention, or `-`
without one. Updates that keep the channel, such as mutes, deafens and streams, SHALL post nothing.

#### Scenario: Join
- **WHEN** a member or a bot joins voice channel 30 of category 20, which listen channel 5 detects,
  in an en-US or a zh-TW guild
- **THEN** listen channel 5 gets v3's join embed in that locale with the member and the channel

#### Scenario: Leave without a category
- **WHEN** a member leaves voice channel 33, which has no category
- **THEN** the leave embed shows `-` as the category

#### Scenario: Switch
- **WHEN** a member switches from channel 30 to channel 32
- **THEN** the switch embed shows both channels and both categories, the joined channel's mention
  included

#### Scenario: Same channel
- **WHEN** a member mutes, deafens or streams in a detected channel
- **THEN** nothing is posted

#### Scenario: Not detected
- **WHEN** a member joins a channel that no listen channel detects
- **THEN** nothing is posted

### Requirement: Logs reach every listen channel
Each log SHALL be rendered in the guild's locale, falling back to zh-TW, and sent to each detecting
listen channel on its own. A listen channel that Discord no longer has SHALL be forgotten with a log
line, and one that refuses the message SHALL get a warning naming the guild and the channel, while
the other listen channels still get theirs.

#### Scenario: Locale without templates
- **WHEN** the guild's locale is French
- **THEN** the log uses the zh-TW templates

#### Scenario: Deleted listen channel
- **WHEN** Discord answers that listen channel 5 does not exist, while 6 also detects the channel
- **THEN** channel 5's settings are deleted with a log line and channel 6 gets the log

#### Scenario: Refused listen channel
- **WHEN** listen channel 5 refuses the message
- **THEN** a warning names the guild and the channel, 5's settings stay, and channel 6 gets the log

### Requirement: Voice channel status changes are logged
The plugin SHALL relay `VOICE_CHANNEL_STATUS_UPDATE` and track each voice channel's status from it,
an unknown one being empty. A change SHALL post `on-status-delete` when the new status is empty,
`on-status-new` when the old one is, else `on-status-update`, with `vl_channel_mention`,
`vl_channel_url`, `vl_category_mention`, `vl_status_before` and `vl_status_after`. An unchanged
status, or a channel that is not a cached voice channel, SHALL post nothing.

#### Scenario: New status
- **WHEN** voice channel 30, whose status is unknown, gets the status `Gaming` in an en-US or a
  zh-TW guild
- **THEN** the detecting listen channels get v3's new status embed in that locale with `Gaming`

#### Scenario: Changed status
- **WHEN** the status of channel 30 changes from `Gaming` to `Chill`
- **THEN** the update embed shows `Gaming` before and `Chill` after

#### Scenario: Cleared status
- **WHEN** the status of channel 30 is cleared after `Chill`
- **THEN** the delete embed shows `Chill`

#### Scenario: Nothing to log
- **WHEN** the same status arrives again, or a status arrives for a stage channel, an uncached
  channel or an uncached guild
- **THEN** nothing is posted and the audit log is not read

### Requirement: Status changes name their member from the audit log
For a detected change, the plugin SHALL read the guild's audit log of type 192 for a set status, or
193 for a cleared one, and take the newest entry for the channel made within 30 seconds of the
event, one with the new status first; a type-192 entry with another status SHALL not count. Without
one it SHALL read once more after 2 seconds. The member values SHALL be the entry's user's, or `-`
without an entry, an audit log or the member.

#### Scenario: Matching entry
- **WHEN** the audit log holds a newer entry for another channel and an entry for channel 30
- **THEN** the log names the user of channel 30's entry, as the guild's member

#### Scenario: Cleared status
- **WHEN** a status is cleared
- **THEN** the audit log is read for type 193

#### Scenario: Late entry
- **WHEN** the first read has no matching entry and the second, 2 seconds later, has one
- **THEN** the log names its user

#### Scenario: Earlier change's entry
- **WHEN** the first read holds only the channel's entry of an earlier status, and the second read
  the entry of the new status
- **THEN** the log names the second entry's user

#### Scenario: No entry
- **WHEN** neither read has a matching entry, or the only entry for the channel is 10 minutes old
- **THEN** the log is posted with `-` as the member and without a thumbnail

#### Scenario: Audit log refused
- **WHEN** Discord refuses to show the audit log
- **THEN** a warning names the guild and the log is posted with `-` as the member

#### Scenario: Member gone
- **WHEN** the entry's user is no longer a member of the guild
- **THEN** the log is posted with `-` as the member

#### Scenario: Not detected
- **WHEN** no listen channel detects the channel
- **THEN** the audit log is not read

### Requirement: Status changes are posted in order from the current session
The plugin SHALL post a voice channel's status changes in the order they arrive, also when one
waits for its audit log entry. It SHALL forget the tracked statuses when a new gateway session
starts, and a guild's when the bot leaves the guild or the guild becomes unavailable, as JDA rebuilt
its cache then.

#### Scenario: A change waits for its entry
- **WHEN** a cleared status waits for its audit log entry and the channel gets a new status meanwhile
- **THEN** the delete embed is posted before the new status embed

#### Scenario: A new session or an outage
- **WHEN** the status `Gaming` was logged, and then the bot becomes ready again or the guild becomes
  unavailable
- **THEN** `Gaming` set again is logged as a new status

#### Scenario: The bot leaves
- **WHEN** the bot leaves a guild whose statuses it tracked
- **THEN** it forgets them

### Requirement: Settings are forgotten with the guild
When the bot leaves a guild, the plugin SHALL delete the guild's settings. When the bot is ready,
and when the plugin loads into a ready bot, it SHALL delete the settings of every guild the bot is
no longer in.

#### Scenario: The bot leaves
- **WHEN** the bot leaves guild 10 while guilds 20 and 30 have settings too
- **THEN** guild 10's settings are deleted and the others stay

#### Scenario: Left while offline
- **WHEN** the bot becomes ready, or the plugin loads into a ready bot, and guild 20 is not among
  the bot's guilds
- **THEN** guild 20's settings are deleted with a log line and the other guilds' stay

### Requirement: Settings are checked when the bot is ready
When the bot is ready, and when the plugin loads into a ready bot, the plugin SHALL remove from the
allow and block lists of each available guild the channels that the guild no longer has, as v3's
startup did, and write nothing when none is gone. Unavailable guilds SHALL be skipped, and a guild
whose settings cannot be read SHALL be skipped with an error, and a stored key that is not a guild
ID with a warning.

#### Scenario: Deleted channels
- **WHEN** the allow list holds channel 30 and the deleted channel 31, and the block list the
  deleted category 21
- **THEN** the lists become `[30]` and `[]`, with a log line

#### Scenario: Nothing deleted
- **WHEN** every listed channel exists
- **THEN** nothing is written

#### Scenario: Unavailable or unreadable
- **WHEN** one guild is unavailable and another's settings cannot be read
- **THEN** the first keeps its lists, the second is skipped with an error, and the other guilds
  are still checked

#### Scenario: A key that is not a guild ID
- **WHEN** the namespace holds settings under the key `general`, and the bot becomes ready or the
  plugin loads into a ready bot
- **THEN** a warning names the key, the plugin loads, and the other guilds are still checked
