## Context

`Placeholder.get(event)` (`Placeholder.kt:59-142`) starts from the member or user keys and adds,
for slash commands, `command_name`, `full_command_name`, `language`, `command_string`, the
channel and its category (guild only) and `subcommand_name`; for buttons, the clicked button's
label, style name, URL and emoji; for selects, the minimum, maximum and placeholder. JDA's
`getCommandString` writes `/name group sub` followed by ` option: value`, with `#` for channels,
`@` for users, roles and mentionables, the raw ID when an entity is not resolved (autocomplete),
and the bare name for context menu commands.

## Goals / Non-Goals

**Goals:** the same keys and the same `command_string` text for discord.py interactions.

**Non-Goals:** user and member keys (callers merge `user_values` / `member_values`), modal keys
(v3 had none).

## Decisions

- **Command keys come from `interaction.data`**: the name, nested subcommand group and subcommand
  options (types 2 and 1), leaf options in order, and `resolved` for entity names (usernames for
  users, as JDA's `User.getName`). Booleans are written `true` / `false`. Context menus (command
  types 2 and 3) give their name only.
- **Component keys** come from the component with the interaction's custom ID on
  `interaction.message`, searched through rows, containers and section accessories. A component
  with a `style` is a button; `component_style` is the discord.py style name in upper case, which
  matches JDA's names.
- **Duck typing** keeps the module free of a runtime discord.py import, as the other key
  families are; `InteractionLike` names what is read, and a type-only test checks that
  `discord.Interaction` fits it.

### v3 behaved differently

- v3 behaved differently: `channel_category_name` came from `asTextChannel()`, which failed for
  commands used in threads, voice-channel chats and announcement channels; it now comes from any
  channel's category, for components too.

## Risks / Trade-offs

- `command_string` for autocomplete interactions shows raw IDs, as JDA did; it is not logged.

## User-visible changes

None. No shipped template uses these keys; operators' templates that do keep working.
