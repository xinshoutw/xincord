## ADDED Requirements

### Requirement: Plugins get a data directory
Each plugin's context SHALL name `<data>/<Name>/` as the plugin's data directory, for the files
that the plugin keeps itself, where `<data>` is the data directory that the bot was given; the
program SHALL give `data/`, which also holds the store's database. The core SHALL NOT create the
plugin's directory.

#### Scenario: Data directory
- **WHEN** a plugin loads in a bot whose data directory is `data`
- **THEN** its context's data directory is `data/<Name>`, which does not exist until the plugin
  creates it

#### Scenario: Data directory at startup
- **WHEN** the program starts with a listed plugin
- **THEN** the plugin's data directory is `data/<Name>` in the working directory
