# plugin-example Specification

## Purpose
The template plugin: `/example-command` echoes its two options and a config value in an ephemeral
embed, under a button that counts its presses.

## Requirements

### Requirement: The plugin installs as Example
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Example`, pointing to `xincord.plugins.example`, with no dependencies and no extra
intents. It SHALL bundle a default `config.yaml` and en-US and zh-TW lang files, which its first
load writes to `plugins/Example/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Example` enabled
- **THEN** it returns `Example` from `xincord.plugins.example` with no dependencies and no intents

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/Example/config.yaml` holds the bundled default and the en-US and zh-TW lang
  files exist

### Requirement: The config holds an example key
`config.yaml` SHALL have an optional text `example_key`, `example_value` by default. A v3 config
file SHALL still load, with a warning that names its `enabled` key.

#### Scenario: Missing key uses the default
- **WHEN** `config.yaml` is empty
- **THEN** the plugin loads with `example_key` set to `example_value`

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's, with `enabled: false` and `example_key: from-v3`
- **THEN** the plugin loads with `example_key` set to `from-v3` and logs a warning that names
  `enabled`

### Requirement: The reply echoes the options
The plugin SHALL answer the command by editing the deferred response into the `example` template
in the user's locale, falling back to zh-TW, with `%_Example@option1%`, `%_Example@option2%`
(`none` when omitted), `%_Example@example_key%` and v3's command placeholders, under the `counter`
template's button at 0. Option text SHALL be inserted verbatim, in any channel.

#### Scenario: Both options
- **WHEN** an en-US user runs the command with `first` and `2`
- **THEN** the response is v3's en-US embed showing `first`, `2` and `example_value`, under a button
  that shows 0 and carries `example:1:a=count;b=0`

#### Scenario: Option 2 omitted
- **WHEN** the command runs without `option2`
- **THEN** the second field shows `none`

#### Scenario: Locale and fallback
- **WHEN** a zh-TW user and a Japanese user run the command
- **THEN** both get v3's zh-TW embed and the zh-TW button

#### Scenario: Command placeholders
- **WHEN** the operator's en-US `example` template has the content
  `%user_name% ran %command_string% as %bot_name%` and `alice` runs the command with `first`
- **THEN** the response's content is `alice ran /example-command option1: first as xincord`

#### Scenario: Placeholder text in an option
- **WHEN** `option1` is `%bot_name% %_Example@option1%`
- **THEN** the first field shows that text unchanged

#### Scenario: Command in a thread
- **WHEN** the command runs in a channel without a category, such as a thread
- **THEN** the response is sent

### Requirement: The command is a localized guild command
The plugin SHALL register the guild command `example-command` with a required text option
`option1` of at most 1024 characters and an optional integer option `option2`. Names and
descriptions SHALL default to v3's and be localized in en-US and zh-TW from `register.yaml`. The
command SHALL keep the command tree's ephemeral defer and answer through the reply.

#### Scenario: Command payload
- **WHEN** the plugin is loaded and the commands are translated
- **THEN** the guild payload holds `example-command` with v3's names, descriptions and
  localizations and no default member permissions, `option1` required with a maximum length of
  1024, and `option2` optional

#### Scenario: Command callback
- **WHEN** the registered command's callback runs with `first` and no `option2`
- **THEN** the deferred response is edited into the reply, and the command does not opt out of the
  defer

### Requirement: The counter button counts presses
The `counter` button SHALL carry the ID `example:1:a=count;b=<count>`, which the plugin routes to
itself. A press SHALL edit the message so that the button shows and carries the count plus one,
leaving the embed unchanged. An `example` ID with another action SHALL get no response.

#### Scenario: Press
- **WHEN** the button carrying 4 is pressed
- **THEN** the message's button shows 5 and carries `example:1:a=count;b=5`

#### Scenario: Other action
- **WHEN** the plugin receives the ID `example:1:a=other`
- **THEN** it does not respond
