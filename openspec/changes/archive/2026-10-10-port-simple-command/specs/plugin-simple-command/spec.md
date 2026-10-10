# Spec Delta

## Purpose

Five administrator commands post a shop's bank payment instructions publicly in the channel.

## ADDED Requirements

### Requirement: The plugin installs as SimpleCommand
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `SimpleCommand`, pointing to `xincord.plugins.simple_command`, with no dependencies or
intents. It SHALL bundle v3's zh-TW lang files, with example values in place of v3's bank account
numbers, which its first load writes to `plugins/SimpleCommand/lang/`, and no `config.yaml`: v3's
only key was `enabled`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `SimpleCommand` enabled
- **THEN** it returns `SimpleCommand` from `xincord.plugins.simple_command` with no dependencies or
  intents

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** the zh-TW `register.yaml` and the five message templates exist under
  `plugins/SimpleCommand/lang/`, and no `config.yaml` is written

### Requirement: A command posts its message in the channel
On each of its commands, the plugin SHALL render the message template named after the command in
the default locale zh-TW, whatever the user's locale, with v3's global placeholders `%bot_id%` and
`%bot_name%`, send the whole message to the command's channel and then delete the deferred
response. If the channel takes no messages or Discord refuses the message, the plugin SHALL log a
warning and edit the deferred response into the message instead.

#### Scenario: Message
- **WHEN** an administrator runs `cub-none-card`
- **THEN** the channel receives v3's embed for it, with its title, thumbnail, fields and the colour
  `#9BD9D5`, and the deferred response is deleted

#### Scenario: Every command
- **WHEN** each of the five commands runs
- **THEN** the channel receives v3's embed of the template with the command's name, with an example
  account number

#### Scenario: Default locale
- **WHEN** an en-US user and a Japanese user run `ctcb-remit`, also after the operator added an
  en-US `ctcb-remit` template
- **THEN** the channel receives the zh-TW embed

#### Scenario: Bot placeholders
- **WHEN** the operator's zh-TW `cub-none-card` template has the content `%bot_name% (%bot_id%)`
  and the bot is `xincord` with the ID 99
- **THEN** the posted message's content is `xincord (99)`

#### Scenario: Components and files
- **WHEN** the operator's template has a link button, or a Components V2 layout with a local file
- **THEN** the posted message carries the button, or the layout and the file

#### Scenario: Channel refuses the message
- **WHEN** Discord refuses the message, for example because the bot lacks a permission there
- **THEN** a warning is logged and the deferred response is edited into the message, with its
  files rendered again

#### Scenario: Channel without messages
- **WHEN** the command's channel takes no messages, such as a forum or a category
- **THEN** the deferred response is edited into the message

### Requirement: The commands are localized administrator guild commands
The plugin SHALL register v3's five guild commands `cub-none-card`, `tsib-none-card`,
`ctcb-none-card`, `ctcb-remit` and `chpytwtp-remit`, without options, with the description
`generate message`, the zh-TW names and descriptions of `register.yaml` and the default member
permission for administrators only. Each command SHALL keep the command tree's ephemeral defer and
post its message.

#### Scenario: Command payload
- **WHEN** the plugin is loaded and the commands are translated
- **THEN** the guild payload holds the five commands with v3's names, description and zh-TW
  localizations, no options and the administrator default permission, and the global payload
  holds none of them

#### Scenario: Command callback
- **WHEN** a registered command's callback runs after the command tree's check
- **THEN** the response was deferred ephemerally, the channel received the message named after the
  command and the deferred response was then deleted
