# Spec Delta

## Purpose

Voice channels bound as lobbies give each member who joins one alone a room of their own, which is
deleted once it is empty.

## ADDED Requirements

### Requirement: The plugin installs as DynamicVoiceChannel
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `DynamicVoiceChannel`, pointing to `xincord.plugins.dynamic_voice_channel`, with no
dependencies (v3's unused SQLiteAPI is gone) and the voice states intent. It SHALL bundle v3's
en-US and zh-TW lang files, which its first load writes to `plugins/DynamicVoiceChannel/lang/`, and
no `config.yaml`: v3's only key was `enabled`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `DynamicVoiceChannel` enabled
- **THEN** it returns `DynamicVoiceChannel` from `xincord.plugins.dynamic_voice_channel` with no
  dependencies and the voice states intent, and the bot requests that intent

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** the en-US and zh-TW `register.yaml` and the four message templates of each exist under
  `plugins/DynamicVoiceChannel/lang/`, and no `config.yaml` is written

### Requirement: Bindings are kept per guild in v3's documents
The plugin SHALL keep a guild's bindings in the store under `DynamicVoiceChannel` and the guild's
ID as v3's list of `{"categoryId", "defaultName", "formatName1", "formatName2"}`. A missing format
SHALL read as empty and reading SHALL never write. A binding SHALL replace those of the same
category and lobby name; removing the last one SHALL delete the document. Concurrent changes
SHALL never lose one another. An entry that is not v3's shape SHALL raise an error and never be
overwritten.

#### Scenario: First binding
- **WHEN** guild 10 binds the lobby `Lobby` of category 20 with the formats `A` and `B`
- **THEN** the store holds `[{"categoryId": 20, "defaultName": "Lobby", "formatName1": "A",
  "formatName2": "B"}]` under `DynamicVoiceChannel` and `10`

#### Scenario: Guild without bindings
- **WHEN** the bindings of a guild without a document are read
- **THEN** there are none and the namespace stays empty

#### Scenario: Missing formats
- **WHEN** a stored entry has no `formatName1` and no `formatName2`
- **THEN** both read as empty texts

#### Scenario: Binding again
- **WHEN** the document holds two entries for category 20 and `Lobby`, as v3's `bind` appended
  them, and that lobby is bound again with the format `C`
- **THEN** reading before finds the first of the two, and afterwards the document holds one entry
  for them, with `C`, after the guild's other entries

#### Scenario: Unbinding
- **WHEN** the only binding of guild 10 is removed, and then removed again
- **THEN** the first removal reports a binding and deletes the document, and the second reports
  none and writes nothing

#### Scenario: Concurrent binds
- **WHEN** 20 lobbies of one guild are bound at the same time
- **THEN** all 20 are stored

#### Scenario: Unreadable entry
- **WHEN** an entry has no `categoryId`, a text `categoryId` or a null format
- **THEN** reading and changing the guild's bindings raise an error and the document stays

### Requirement: Rooms are tracked per guild
The plugin SHALL keep the rooms it created in the store under `DynamicVoiceChannel.rooms` and the
guild's ID, as `{"<room ID>": <owner ID>}`. Forgetting the last room SHALL delete the document. A
document that is not of that shape SHALL raise an error and never be overwritten.

#### Scenario: Tracked room
- **WHEN** room 30 of guild 10 is tracked for member 1, then room 31 for member 2
- **THEN** the store holds `{"30": 1, "31": 2}` under `DynamicVoiceChannel.rooms` and `10`

#### Scenario: Forgotten rooms
- **WHEN** room 30 and then room 31 are forgotten, and then room 32, which was never tracked
- **THEN** the document holds room 31 only, then is deleted, and the last call writes nothing

#### Scenario: Unreadable rooms
- **WHEN** the document is a list, or maps a room to a text
- **THEN** reading and changing the guild's rooms raise an error and the document stays

### Requirement: Room names follow format 1
A room's name SHALL be the binding's format 1 rendered in one pass with v3's member values (the
user, member and bot keys of `Placeholder.get(member)`) and `%dvc@custom_name%`, the member's
display name up to its first ` - `, and then trimmed. A blank name, or one longer than 100
characters, SHALL not be used.

#### Scenario: Custom name
- **WHEN** format 1 is `| %dvc@custom_name%` and the member's display name is `Bob - Gaming`
- **THEN** the room's name is `| Bob`

#### Scenario: Member values
- **WHEN** format 1 is `%member_display_name% %user_name% %bot_name%` for a member with the
  nickname `Bob`
- **THEN** the name holds the nickname, the username and the bot's name

#### Scenario: Typed text stays
- **WHEN** the display name is `%user_id%`
- **THEN** `%dvc@custom_name%` gives `%user_id%` as typed

#### Scenario: Unusable name
- **WHEN** format 1 renders to spaces only, or to 101 characters
- **THEN** there is no name

### Requirement: Administrators bind lobbies
`bind` SHALL store a binding of the `channel` option's category, its name and both formats,
replacing one of the same category and name, and edit the deferred response into `bind-success`.
A channel outside a category SHALL get `must-under-category`, and nothing SHALL be written.
Replies SHALL be rendered in the user's locale with v3's values of the interaction.

#### Scenario: Bind
- **WHEN** an administrator with an en-US or a zh-TW client binds the voice channel `Lobby` of
  category 20 with the formats `A` and `B`
- **THEN** the binding is stored and the response is v3's `bind-success` embed in that locale

#### Scenario: Bind outside a category
- **WHEN** the voice channel has no category
- **THEN** the response is v3's `must-under-category` embed and nothing is written

### Requirement: Administrators unbind lobbies
`unbind` SHALL remove the bindings of the `channel` option's category and current name and edit
the deferred response into `unbind-success`, or into `unbind-fail` when there was none. A channel
outside a category SHALL get `must-under-category`.

#### Scenario: Unbind
- **WHEN** an administrator with an en-US or a zh-TW client unbinds a bound lobby, and then unbinds
  it again
- **THEN** the binding is removed and the responses are v3's `unbind-success` and `unbind-fail`
  embeds in that locale

#### Scenario: Unbind outside a category
- **WHEN** the voice channel has no category
- **THEN** the response is v3's `must-under-category` embed

### Requirement: The command is a localized administrator guild command
The plugin SHALL register v3's guild command `dynamic-voice-channel` with the subcommands `bind`
(`channel`, `format-name-1` and `format-name-2`, all required) and `unbind` (`channel`), with v3's
names, descriptions and en-US and zh-TW localizations, visible to administrators by default. The
`channel` options SHALL offer voice channels only. The tree SHALL defer both ephemerally.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** the command has v3's texts, localizations and subcommands, the default member
  permissions 8, and channel options limited to voice channels (type 2)

#### Scenario: Command callbacks
- **WHEN** each subcommand runs
- **THEN** its callback, bound to the plugin's cog, answers in the response that the tree deferred
  ephemerally

#### Scenario: Outside a guild
- **WHEN** a subcommand's callback runs without a guild, which Discord never sends for guild
  commands
- **THEN** nothing is answered

### Requirement: Joining an empty lobby creates a room
When a member joins or moves into a voice channel that then holds only them, is not a tracked room
and whose category and exact name match a binding of its guild, the plugin SHALL copy the channel
as the new lobby, track the joined channel as the member's room, move the copy to position 0, rename
the room from format 1 and move it to position 1, and allow the member Manage Channels and Manage
Permissions there.

#### Scenario: First join
- **WHEN** member Bob joins the empty lobby `Lobby` of a binding with format 1 `| %dvc@custom_name%`
- **THEN** the lobby is copied, the copy moves to position 0, the joined channel becomes Bob's
  tracked room `| Bob` at position 1, and Bob is allowed Manage Channels and Manage Permissions
  there, in that order

#### Scenario: Not alone
- **WHEN** a member joins a lobby where someone already is
- **THEN** nothing is created

#### Scenario: Not a lobby
- **WHEN** a member joins, alone, a voice channel with another name, in another category or in no
  category, a stage channel with the lobby's name, or a tracked room with the lobby's name
- **THEN** nothing is created

#### Scenario: Same channel
- **WHEN** a member in a lobby mutes or deafens
- **THEN** nothing is created

#### Scenario: Gone before the plugin saw it
- **WHEN** the member has already left the lobby when the plugin handles the join
- **THEN** nothing is created

#### Scenario: Unusable name
- **WHEN** format 1 renders to a blank name
- **THEN** the room keeps its name and still moves to position 1 and gives the member the
  permissions, and a warning names the guild and the room

### Requirement: Failures leave a lobby
When the copy of a lobby fails, the plugin SHALL track nothing, change nothing and log a warning
that names the guild and the channel. When a later step fails, it SHALL log such a warning, still
run the remaining steps and keep the room tracked.

#### Scenario: Copy refused
- **WHEN** Discord refuses the copy of the lobby
- **THEN** nothing is tracked, no other request is sent, and a warning names the guild and the
  lobby

#### Scenario: Later step refused
- **WHEN** Discord refuses moving the copy, renaming the room, or the member's permissions
- **THEN** a warning names the guild and the channel, the other steps are still sent, and the room
  stays tracked

### Requirement: Empty rooms are deleted
When a member leaves or moves out of a tracked room that is then empty, the plugin SHALL delete the
channel and forget it. A channel that is already gone SHALL be forgotten; one whose deletion fails
SHALL stay tracked, with a warning. Untracked channels SHALL never be deleted. A guild's voice
changes SHALL be handled one after another.

#### Scenario: Last member leaves
- **WHEN** the last member leaves a tracked room, or moves from it into a lobby
- **THEN** the room is deleted and forgotten, and the move also creates the member's new room

#### Scenario: Someone stays
- **WHEN** a member leaves a tracked room where someone else still is
- **THEN** nothing is deleted

#### Scenario: Untracked channel
- **WHEN** the last member leaves a channel that is not a tracked room
- **THEN** nothing is deleted

#### Scenario: Already deleted
- **WHEN** Discord answers that the empty room no longer exists
- **THEN** the room is forgotten

#### Scenario: Deletion refused
- **WHEN** Discord refuses to delete the empty room
- **THEN** the room stays tracked and a warning names the guild and the room

#### Scenario: Leaving during the creation
- **WHEN** the member leaves the lobby while its room is being created
- **THEN** the room is created and then deleted, and the copy stays as the lobby

### Requirement: Data is forgotten with the guild
The plugin SHALL delete a guild's bindings and rooms when the bot leaves the guild or is removed
from it, and, when the bot is ready or the plugin loads into a ready bot, those of every guild the
bot is no longer in. Unavailable guilds SHALL keep their data.

#### Scenario: The bot leaves
- **WHEN** the bot leaves guild 10
- **THEN** guild 10's bindings and rooms are deleted and other guilds' stay

#### Scenario: Left while offline
- **WHEN** the bot becomes ready with data of an available guild, an unavailable guild and a guild
  it left
- **THEN** only the data of the guild it left is deleted, with a log line that names it

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads into a bot that is ready
- **THEN** the data of the guilds the bot left is deleted at once

### Requirement: Bindings and rooms are checked when the bot is ready
When the bot is ready, and when the plugin loads into a ready bot, the plugin SHALL, in each
available guild, drop bindings whose category is gone or holds no voice channel with the lobby's
name, with a warning each, delete tracked rooms that are empty, and forget tracked rooms that no
longer exist.

#### Scenario: Stale bindings
- **WHEN** a guild has a binding whose category is gone, one whose category has no voice channel
  with the lobby's name, and a valid one
- **THEN** only the valid binding stays, and a warning names each dropped one

#### Scenario: Rooms after a restart
- **WHEN** the bot becomes ready with an empty tracked room, an occupied one and one that no longer
  exists
- **THEN** the empty room is deleted, and only the occupied room stays tracked

#### Scenario: Unavailable guild
- **WHEN** a guild with bindings and rooms is unavailable when the bot becomes ready
- **THEN** its bindings and rooms are left as they are
