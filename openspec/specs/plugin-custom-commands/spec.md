# plugin-custom-commands Specification

## Purpose
The commands that the plugin's `config.yaml` lists answer with message templates, in the channel or
as a public or ephemeral reply; the bundled ones are five administrator commands, which post a
shop's bank payment instructions publicly in the channel.

## Requirements

### Requirement: The plugin installs as CustomCommands
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `CustomCommands`, pointing to `xincord.plugins.custom_commands`, with no dependencies or
intents. It SHALL bundle a `config.yaml` that defines five commands, and five zh-TW message templates with
example bank account numbers, which its first load writes to `plugins/CustomCommands/`, and no `register.yaml`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `CustomCommands` enabled
- **THEN** it returns `CustomCommands` from `xincord.plugins.custom_commands` with no dependencies
  or intents

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/CustomCommands/config.yaml` holds the bundled commands, the five zh-TW message
  templates exist under `plugins/CustomCommands/lang/`, and no `register.yaml` is written

### Requirement: A command posts its message in the channel
On a command whose `reply` is `channel`, the default, the plugin SHALL render the message template
that the entry's `template` names (the command's name by default) in the default locale zh-TW, with
the placeholders of the user, the bot and the interaction, send the whole message to the command's
channel and then delete the deferred response. If the channel takes no messages or Discord refuses
the message, the plugin SHALL log a warning and edit the deferred response into the message.

#### Scenario: Message
- **WHEN** an administrator runs `cub-none-card`
- **THEN** the channel receives its embed, with its title, thumbnail, fields and the colour
  `#9BD9D5`, and the deferred response is deleted

#### Scenario: Every command
- **WHEN** each of the five commands runs
- **THEN** the channel receives the embed of the template with the command's name, with an example
  account number

#### Scenario: Default locale
- **WHEN** an en-US user and a Japanese user run `ctcb-remit`, also after the operator added an
  en-US `ctcb-remit` template
- **THEN** the channel receives the zh-TW embed

#### Scenario: Bot placeholders
- **WHEN** the operator's zh-TW `cub-none-card` template has the content `%bot_name% (%bot_id%)`
  and the bot is `xincord` with the ID 99
- **THEN** the posted message's content is `xincord (99)`

#### Scenario: User placeholders
- **WHEN** the template has the content `%user_name% in %channel_name%` and alice runs the command
  in #general
- **THEN** the posted message's content is `alice in general`

#### Scenario: Template key
- **WHEN** an entry named `pay` sets `template: ctcb-remit`
- **THEN** `/pay` posts the `ctcb-remit` embed

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

### Requirement: Commands come from the config
The plugin SHALL register a guild command for each entry of `commands` in its `config.yaml`, with
the entry's `name`, `description` and `localizations` (a name and a description per Discord
locale), the default member permissions that `permissions` lists by discord.py's names
(Administrator when omitted, none when empty) and, when `guilds` lists guild IDs, in those guilds
only. The bundled entries SHALL be the five shop commands.

#### Scenario: Command payload
- **WHEN** the plugin is loaded with the bundled config and the commands are translated
- **THEN** the guild payload holds the five commands with their names, description and zh-TW
  localizations, no options and the administrator default permission, and the global payload
  holds none of them

#### Scenario: Operator's command
- **WHEN** the operator's config has only a `rules` entry with en-US and ja localizations and
  `permissions: [manage_guild, manage_messages]`
- **THEN** the guild payload holds `rules` alone, with those localizations and the default member
  permissions 8224

#### Scenario: Every member
- **WHEN** an entry sets `permissions: []`
- **THEN** its command has no default member permissions

#### Scenario: Some guilds
- **WHEN** one entry lists guild 1 and another lists no guild
- **THEN** guild 1's payload holds both commands and guild 2's only the second

#### Scenario: Command callback
- **WHEN** a registered command's callback runs after the command tree's check
- **THEN** the response was deferred ephemerally, the channel received the message named after the
  command and the deferred response was then deleted

### Requirement: A command can answer with a public or an ephemeral reply
An entry's `reply` SHALL be `channel`, `public` or `ephemeral`. The command tree SHALL not defer a
`public` command, which defers publicly and edits that response into its message in the default
locale. An `ephemeral` command SHALL edit the tree's ephemeral deferral into its message in the
user's locale, else the default one. When Discord refuses an edited response, the plugin SHALL log
a warning and delete it.

#### Scenario: Public reply
- **WHEN** a command with `reply: public` runs
- **THEN** the command tree did not defer it, the response is deferred publicly and edited into
  the zh-TW message, and nothing is posted in the channel

#### Scenario: Ephemeral reply
- **WHEN** a command with `reply: ephemeral` runs for an en-US user and its template exists in en-US
- **THEN** the ephemeral deferred response is edited into the en-US message, and nothing is posted
  in the channel

#### Scenario: Ephemeral fallback
- **WHEN** a Japanese user runs that command and the template has no ja file
- **THEN** the response is the zh-TW message

#### Scenario: Refused response
- **WHEN** Discord refuses the edit of a public reply's response, or of a post's fallback
- **THEN** a warning names the command, and the response is deleted

#### Scenario: Unknown answer
- **WHEN** an entry sets `reply: dm`
- **THEN** the plugin does not load and the log names `commands.0.reply`

### Requirement: The config is validated at load
The plugin SHALL not load, and its error SHALL name the file and the key, when `commands` is
missing, a name or localized name breaks Discord's name rules, a description is empty or over 100
characters, a locale is not Discord's, a permission is unknown, a guild ID is not positive, two
commands share a name in a locale, the commands exceed the room left of Discord's 100, or a
command's template is missing from the default locale or fails to render.

#### Scenario: Invalid names and descriptions
- **WHEN** an entry's name is `Pay Now` or ends with a line break, its zh-TW name holds a space,
  or its description is empty or 101 characters long
- **THEN** the plugin does not load and the log names `commands.0.name`,
  `commands.0.localizations.zh-TW.name` or `commands.0.description`

#### Scenario: Unknown locale, permission or guild
- **WHEN** a localization is under `zh`, a permission is `admin`, or a guild ID is 0
- **THEN** the plugin does not load and the log names the key

#### Scenario: Duplicate names
- **WHEN** two entries are named `pay`, or two entries have the same zh-TW name, or one entry's
  zh-TW name is another entry's name, which zh-TW clients see for it
- **THEN** the plugin does not load and the log names the second entry's key

#### Scenario: Too many commands
- **WHEN** 100 entries are listed, while the core's `/xincord` takes one of the 100 places
- **THEN** the plugin does not load and the log names `commands`

#### Scenario: Missing template
- **WHEN** an entry's template has no file in `lang/zh-TW/message/`, only one in `lang/en-US/`
- **THEN** the plugin does not load and the log names `commands.0.template`

#### Scenario: Template that cannot be posted
- **WHEN** a command's template, in any locale, has a button with a `uid`, a `model_key`, a file
  that does not exist, or six rows of buttons
- **THEN** the plugin does not load and the log names the template's file and the problem

#### Scenario: Link button with a uid
- **WHEN** a command's template has a link button that also has a `uid`, which is not used
- **THEN** the plugin loads

#### Scenario: Missing commands
- **WHEN** `config.yaml` holds only `enabled: true`
- **THEN** the plugin does not load and the log names `commands`

### Requirement: Config changes apply on reload
Reloading the plugin SHALL read `config.yaml` again and replace the plugin's commands with the
edited ones, which the core then uploads. When the edited config is invalid, the reload SHALL fail
with the key named and the plugin SHALL keep the commands it had.

#### Scenario: Edited config
- **WHEN** the operator renames a command, adds one and removes one, then reloads the plugin in a
  ready bot
- **THEN** the guild payload holds the edited commands and the core uploads the commands

#### Scenario: Broken edit
- **WHEN** the edited config has an entry without a description and the plugin reloads
- **THEN** the reload fails naming the key and the previous commands stay
