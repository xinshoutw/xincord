# core-i18n Specification

## Purpose
Loads each plugin's localized YAML files, validates them, and serves texts, template paths and
command localizations per Discord locale.

## Requirements

### Requirement: Bundled lang files are exported
Exporting SHALL copy every bundled lang file into the plugin's `lang` directory, creating
directories as needed. Existing files SHALL be kept unless renewal is forced, in which case every
bundled file is overwritten. Files that exist only in the target SHALL never be deleted.

#### Scenario: First export writes every file
- **WHEN** the target directory is empty
- **THEN** every bundled file is written with its bundled content

#### Scenario: Operator edits are kept
- **WHEN** a target file already exists and renewal is not forced
- **THEN** its content is unchanged

#### Scenario: Forced renewal overwrites bundled files only
- **WHEN** renewal is forced
- **THEN** every bundled file is overwritten and files only in the target remain

### Requirement: Locales come from Discord locale directories
Each directory under `lang` named after a Discord locale SHALL be loaded as that locale. Other
directories SHALL be skipped with a warning. A missing default locale directory SHALL fail the
load.

#### Scenario: Unknown directory is skipped
- **WHEN** `lang` contains `en-US`, `zh-TW` and `backup`
- **THEN** the locales are en-US and zh-TW and a warning names `backup`

#### Scenario: Default locale is required
- **WHEN** the default locale has no directory
- **THEN** the load fails naming the plugin and the locale

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
  and refuses the others, such as `Calc`, `my calc`, 33 letters, a line break, and a combining
  mark outside the Devanagari and Thai scripts, which Discord refuses

### Requirement: Key sets are compared with the default locale
After loading, keys and template names that a locale lacks, or has only for itself, compared with
the default locale SHALL be logged as warnings naming the plugin, locale and keys.

#### Scenario: Missing and extra keys warn
- **WHEN** zh-TW lacks one key of the default locale and has one key the default lacks
- **THEN** two warnings name zh-TW and those keys

### Requirement: Texts and templates fall back to the default locale
Looking up a text key or a template SHALL use the requested locale when it has the key or file,
and the default locale otherwise. A key or template missing from the default locale SHALL raise a
lookup error.

#### Scenario: Per-key fallback
- **WHEN** zh-TW has text key a but not key b, and both are requested in zh-TW
- **THEN** a comes from zh-TW and b from the default locale

#### Scenario: Template fallback
- **WHEN** a template exists only in the default locale and is requested in another locale
- **THEN** the default locale's file is returned

#### Scenario: Unknown key raises
- **WHEN** a key exists in no locale
- **THEN** the lookup raises an error naming the plugin and the key

### Requirement: Commands are localized from register.yaml without fallback
Command strings created by a plugin's lang SHALL carry the plugin's lang and the register key, and
the translator SHALL return that key's value in the requested locale, or nothing when that locale
lacks it so that Discord shows the default name.

#### Scenario: Translated name
- **WHEN** a command name created for key `calc.name` is translated to zh-TW and zh-TW defines it
- **THEN** the zh-TW value is returned

#### Scenario: No fallback for commands
- **WHEN** the requested locale does not define the key, or the string carries no lang
- **THEN** the translator returns nothing

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
