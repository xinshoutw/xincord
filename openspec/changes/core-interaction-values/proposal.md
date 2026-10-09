## Why

v3's `Placeholder.get(event)` adds interaction keys to every command, button and select render:
the command names and `command_string`, the user's language, the channel and its category, and
the clicked component's details. core-placeholders left them for later; the interaction log also
needs `command_string`.

## What Changes

- `interaction_values(interaction)` returns v3's interaction keys: `command_name`,
  `full_command_name`, `subcommand_name`, `command_string` (JDA's format), `language`,
  `channel_id`, `channel_name`, `channel_category_name`, and `component_*` for buttons and
  selects.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:59-142`
- JDA 6 `CommandInteractionPayload.getCommandString` and `getFullCommandName`

Out of scope: user and member keys (already `user_values` and `member_values`), and the
interaction log itself (Core change `runtime`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-placeholders`: adds the interaction key family.

## Impact

`xincord.core.placeholders` gains `InteractionLike` and `interaction_values`.
