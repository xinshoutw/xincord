## MODIFIED Requirements

### Requirement: Bindings are kept per guild in v3's documents
The plugin SHALL keep a guild's bindings in the store under `DynamicVoiceChannel` and the guild's
ID as v3's list of `{"categoryId", "defaultName", "formatName1"}`. A missing format SHALL read as
empty and reading SHALL never write. A binding SHALL replace those of the same category and lobby
name; removing the last one SHALL delete the document. Concurrent changes SHALL never lose one
another. An entry that is not v3's shape SHALL raise an error and never be overwritten.

#### Scenario: First binding
- **WHEN** guild 10 binds the lobby `Lobby` of category 20 with the format `A`
- **THEN** the store holds `[{"categoryId": 20, "defaultName": "Lobby", "formatName1": "A"}]` under
  `DynamicVoiceChannel` and `10`

#### Scenario: Guild without bindings
- **WHEN** the bindings of a guild without a document are read
- **THEN** there are none and the namespace stays empty

#### Scenario: Missing formats
- **WHEN** a stored entry has no `formatName1`
- **THEN** its format reads as an empty text

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
- **WHEN** an entry has no `categoryId`, a text `categoryId` or a null `formatName1`
- **THEN** reading and changing the guild's bindings raise an error and the document stays

### Requirement: Administrators bind lobbies
`bind` SHALL store a binding of the `channel` option's category, its name and the format, replacing
one of the same category and name, and edit the deferred response into `bind-success`. A channel
outside a category SHALL get `must-under-category`, and nothing SHALL be written. Replies SHALL be
rendered in the user's locale with v3's values of the interaction.

#### Scenario: Bind
- **WHEN** an administrator with an en-US or a zh-TW client binds the voice channel `Lobby` of
  category 20 with the format `A`
- **THEN** the binding is stored and the response is v3's `bind-success` embed in that locale

#### Scenario: Bind outside a category
- **WHEN** the voice channel has no category
- **THEN** the response is v3's `must-under-category` embed and nothing is written

### Requirement: The command is a localized administrator guild command
The plugin SHALL register v3's guild command `dynamic-voice-channel` with the subcommands `bind`
(`channel` and `format-name-1`, both required) and `unbind` (`channel`), with v3's names,
descriptions and en-US and zh-TW localizations, visible to administrators by default. The
`channel` options SHALL offer voice channels only. The tree SHALL defer both ephemerally.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** the command has v3's texts, localizations and subcommands without `format-name-2`, the
  default member permissions 8, and channel options limited to voice channels (type 2)

#### Scenario: Command callbacks
- **WHEN** each subcommand runs
- **THEN** its callback, bound to the plugin's cog, answers in the response that the tree deferred
  ephemerally

#### Scenario: Outside a guild
- **WHEN** a subcommand's callback runs without a guild, which Discord never sends for guild
  commands
- **THEN** nothing is answered

## ADDED Requirements

### Requirement: v3's second format is ignored
A binding SHALL have one name format. v3's `formatName2`, which v3 required, stored and never used,
SHALL be ignored when an entry is read, whatever its value, and left out when the guild's bindings
are written. An operator's `register.yaml` that still holds `format-name-2` SHALL load, its keys
unused.

#### Scenario: v3's entry
- **WHEN** a stored entry holds `"formatName2": "B"`, another `"formatName2": 2`, and then another
  lobby of the guild is bound
- **THEN** both entries read with their `formatName1`, and the written document holds no
  `formatName2`

#### Scenario: v3's lang files
- **WHEN** the plugin loads with en-US and zh-TW `register.yaml` files that hold `format-name-2`
- **THEN** it loads, and `bind` has the options `channel` and `format-name-1` only
