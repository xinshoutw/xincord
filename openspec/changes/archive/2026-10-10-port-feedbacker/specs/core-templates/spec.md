# Spec Delta

## ADDED Requirements

### Requirement: Embed fields follow JDA
Rendering SHALL remove the leading and trailing characters up to U+0020 from each embed field's name
and value, as Java's `trim` in JDA's fields did, and SHALL give a name or value that is empty
afterwards the text U+200E, as JDA did, because Discord refuses empty fields. Fields that a
`model_key` supplies SHALL get the same treatment.

#### Scenario: Empty value
- **WHEN** a field's value renders empty
- **THEN** the field's value is U+200E

#### Scenario: Padded text
- **WHEN** a field's name renders as ` name ` and its value as `value` followed by two newlines
- **THEN** the field's name is `name` and its value is `value`

### Requirement: Modal submissions are read back
`modal_values(data)` SHALL return the value of each text input in a modal submission's data by its
custom ID, whether the input sits in a label, as rendered modals send it, or in an action row.
Other components SHALL be ignored.

#### Scenario: Label and action row inputs
- **WHEN** a submission holds the input `form` in a label, the input `title` in an action row and a
  text display
- **THEN** the values of `form` and `title` are returned by their IDs
