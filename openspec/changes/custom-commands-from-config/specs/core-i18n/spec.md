## MODIFIED Requirements

### Requirement: Lang files are validated at load
Every lang YAML file SHALL be a mapping whose leaves are strings; otherwise the load SHALL fail
naming the file and key. In `register.yaml`, every `name` SHALL follow Discord's command name
rules and every `description` SHALL have 1 to 100 characters. The name check SHALL be public as
`is_command_name(name)`, for names that plugins read from elsewhere.

#### Scenario: Non-string leaf fails
- **WHEN** a lang file has a list or number as a value
- **THEN** the load fails naming the file and the key

#### Scenario: Invalid command name fails
- **WHEN** a register name has an uppercase letter, a space, or more than 32 characters
- **THEN** the load fails naming the file and the key

#### Scenario: Description length is checked
- **WHEN** a register description is empty or longer than 100 characters
- **THEN** the load fails naming the file and the key

#### Scenario: Public name check
- **WHEN** a plugin checks names with `is_command_name`
- **THEN** it accepts the names that `register.yaml` accepts, such as `my-calc_2` and `o'clock`,
  and refuses the others, such as `Calc`, `my calc` and 33 letters

## ADDED Requirements

### Requirement: Commands can be localized from a table
A command string created with `localized(default, translations)`, where `translations` maps
Discord locales to texts, SHALL be translated to the text of the requested locale, or to nothing
when the table lacks that locale, so that Discord shows the default.

#### Scenario: Translated from the table
- **WHEN** a command name created with `localized("rules", {"zh-TW": "gui-ze"})` is translated to
  zh-TW
- **THEN** `gui-ze` is returned, and the string's message is `rules`

#### Scenario: Locale missing from the table
- **WHEN** that name is translated to Japanese
- **THEN** the translator returns nothing
