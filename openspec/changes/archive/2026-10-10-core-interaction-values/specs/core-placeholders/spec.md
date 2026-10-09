# Spec Delta

## ADDED Requirements

### Requirement: Command interaction values follow v3
For an application command interaction the placeholders SHALL give `command_name`,
`full_command_name` (with the subcommand group and subcommand), `subcommand_name` when one was
used, and `command_string` as JDA built it: `/`, the full name, then ` name: value` per option,
with channels as `#name` and users and roles as `@name`. Context menu commands SHALL give their
name as `command_string`.

#### Scenario: Subcommand with options
- **WHEN** `/ticket panel create` runs with a channel, a user, a role, a boolean and a text option
- **THEN** `command_string` is
  `/ticket panel create where: #general owner: @alice role: @Mods pinned: true title: Hi`,
  `full_command_name` is `ticket panel create` and `subcommand_name` is `create`

#### Scenario: Context menu command
- **WHEN** the message context command `Report` runs
- **THEN** `command_name` and `command_string` are `Report` and there is no `subcommand_name`

### Requirement: Component interaction values follow v3
For a component interaction the placeholders SHALL give `component_id` and, from the component
with that ID on the message, a button's `component_label`, `component_style` (the JDA style
name), and `component_emoji` and `component_emoji_name` when set, or a select's `component_min`,
`component_max` and `component_placeholder` when set.

#### Scenario: Button and select
- **WHEN** a button with a custom emoji inside a container, and a select with a placeholder, are
  used
- **THEN** the button gives its label, `PRIMARY`, the formatted emoji and its name, and the select
  gives its minimum, maximum and placeholder

#### Scenario: Unknown component
- **WHEN** the message has no component with the interaction's ID, or there is no message
- **THEN** only `component_id` is given for the component

### Requirement: Interaction language and channel follow v3
Every interaction SHALL give `language`, the JDA native name of the user's locale, and, when its
channel has a name, `channel_id` and `channel_name`, plus `channel_category_name` when the channel
is in a category.

#### Scenario: Guild channel and direct message
- **WHEN** a zh-TW user interacts in `general` under the category `Text`, and later in a direct
  message
- **THEN** the first gives the zh-TW native name, the channel's ID and name and `Text`, and the
  second gives only `language`
