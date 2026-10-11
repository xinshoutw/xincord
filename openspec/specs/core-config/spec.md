# core-config Specification

## Purpose
Loads and validates YAML configuration for the core and for plugins, and defines the core
config schema.

## Requirements

### Requirement: Config files are validated against a typed schema
Loading a config file SHALL validate it against the caller's schema. Any invalid value, YAML
syntax error, or non-mapping document SHALL fail the load with a config error that names the file
and the location of every problem; a YAML syntax error SHALL give its line and column without
quoting the file's text, which can hold secrets. An empty file SHALL load as an empty mapping.

#### Scenario: Valid file loads
- **WHEN** a file matches the schema
- **THEN** the load returns the typed configuration

#### Scenario: Invalid value is reported with its location
- **WHEN** a nested value has the wrong type
- **THEN** the load fails with a config error naming the file and the dotted location

#### Scenario: Broken YAML is reported
- **WHEN** the file is not valid YAML or its top level is not a mapping
- **THEN** the load fails with a config error naming the file

#### Scenario: Empty file uses the defaults
- **WHEN** the file is empty and every field has a default
- **THEN** the load returns the defaults

#### Scenario: YAML errors quote no text
- **WHEN** a line that holds a secret has a YAML syntax error
- **THEN** the config error and the error chained to it give the line and the column, not the
  secret

### Requirement: Missing config files are created from the default
When the config file does not exist, loading SHALL first write the caller's default text to that
path, creating parent directories, and then load it. Existing files SHALL never be overwritten.

#### Scenario: Default is written for a missing file
- **WHEN** the file does not exist
- **THEN** the default text is written to the path and the loaded configuration equals the default

#### Scenario: Existing file is kept
- **WHEN** the file exists
- **THEN** its content is loaded and the file is not modified

### Requirement: Unknown keys warn instead of failing
Keys that the schema does not define SHALL NOT fail the load. Each unknown key SHALL be logged as
a warning with the file and its dotted path, including keys inside lists.

#### Scenario: Unknown nested key is reported
- **WHEN** the file contains a key the schema does not define, at any depth
- **THEN** the load succeeds and a warning names the file and the key's dotted path

### Requirement: Core config schema
The core config SHALL define `token` (default empty), `status.activities` (each with `type`,
`text`, `seconds` greater than zero with default 5, and `url`), and `interaction_log` targets
(each with positive `guild_id` and `channel_id`, `types` drawn from command, button and modal,
and `format`). The default file SHALL validate and contain no real Discord IDs.

#### Scenario: Default core config validates
- **WHEN** the shipped default core config is loaded
- **THEN** it validates, its token is empty, and it has no interaction log targets

#### Scenario: Streaming activity needs a URL
- **WHEN** an activity has type streaming and no url
- **THEN** validation fails at that activity

#### Scenario: Activity duration must be positive
- **WHEN** an activity has seconds of zero or less
- **THEN** validation fails at that activity

#### Scenario: Interaction log types are limited
- **WHEN** an interaction log target lists a type other than command, button or modal
- **THEN** validation fails at that target

### Requirement: The core config lists the enabled plugins
The core config SHALL have `plugins`, the names of the plugins to load in the order given (default
none). The shipped default SHALL enable none.

#### Scenario: Plugins list
- **WHEN** the default core config loads, and a config lists AutoRole and Ticket
- **THEN** the default enables no plugin and the other keeps both names in order
