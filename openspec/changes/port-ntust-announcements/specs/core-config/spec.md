# Spec Delta

## MODIFIED Requirements

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
