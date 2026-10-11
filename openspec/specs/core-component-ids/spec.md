# core-component-ids Specification

## Purpose
Encodes plugin state in Discord component and modal IDs in a versioned format, keeps decoding the
legacy IDs on existing messages, and upgrades those IDs when they are used.

## Requirements

### Requirement: Component IDs use a versioned format
A plugin's codec SHALL build IDs as `{namespace}:1:` followed by `key=value` pairs joined by `;`,
where each key is the letter of the field's position in the plugin's field list (`a` to `z`) and
each value is percent-encoded text. Parsing SHALL return the same field values as text. Building
SHALL fail for unknown fields and for IDs longer than 100 characters.

#### Scenario: Build and parse
- **WHEN** a `giveaway` codec with fields `action`, `sub_action` and `giveaway_id` builds
  `{action: join, giveaway_id: 7}`
- **THEN** the ID is `giveaway:1:a=join;c=7` and parsing it returns `{action: join, giveaway_id: 7}`
  as a current ID

#### Scenario: Values are escaped
- **WHEN** values contain `;`, `=`, `:`, `%`, spaces or non-ASCII text
- **THEN** parsing the built ID returns the same values

#### Scenario: Limits
- **WHEN** a field is unknown or the ID would be longer than 100 characters
- **THEN** building fails

#### Scenario: Codec as the template ID builder
- **WHEN** a message template's button has `uid: {action: join}` and the codec builds its IDs
- **THEN** the button's ID is `giveaway:1:a=join`

### Requirement: Legacy IDs decode permanently
A codec with a legacy prefix SHALL parse legacy IDs (`{prefix}{letter}:{value}` joined by `;`,
letters by the plugin's field order) into the same field map as new IDs, turning hex fields into
decimal text, and SHALL report them as legacy. IDs of other plugins, malformed segments and unknown
letters SHALL fail. A codec SHALL tell whether an ID is its own in either format.

#### Scenario: Legacy ticket ID
- **WHEN** a `ticket` codec with legacy prefix `ticket@` and hex field `user_id` parses
  `ticket@a:submit;d:1b;f:2`
- **THEN** it returns `{action: submit, user_id: 27, btn_index: 2}` as a legacy ID

#### Scenario: Foreign and malformed IDs
- **WHEN** the codec parses another plugin's ID, `ticket@a`, `ticket@z:x`, or a hex field that is
  not hex
- **THEN** parsing fails, and only its own IDs are recognized as its own

### Requirement: Legacy IDs are upgraded lazily
A codec SHALL convert one of its legacy IDs into the equivalent new-format ID. Given a view rebuilt
from a message, the core SHALL replace each legacy ID that one of the given codecs owns with its
new-format ID, leave every other item unchanged, and report whether anything changed.

#### Scenario: Upgrade a view
- **WHEN** a view holds a legacy ticket button, a legacy ticket select, a new-format button and a
  link button
- **THEN** both legacy IDs become new-format IDs, the others stay, and a change is reported

#### Scenario: Nothing to upgrade
- **WHEN** a view holds no legacy IDs
- **THEN** nothing changes and no change is reported
