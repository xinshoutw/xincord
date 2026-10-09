## Why

Plugins describe their messages and modals in YAML under `lang/<locale>/message/` and
`lang/<locale>/modal/`. Decision B10 keeps the format used today (content, embeds, components
tagged `!ButtonsComponent`, `!StringSelectMenu` and `!EntitySelectMenu`, `uid` maps and
`model_key`) and adds Components V2. This change ports the format the shipped templates use; a
follow-up change adds Components V2, which no shipped template uses yet.

## What Changes

- Parse and validate message and modal templates when a plugin loads, with warnings for unknown
  keys and errors that name the file.
- Render a message template into content, embeds and components (a discord.py view), applying
  placeholders, v3's URL and empty-embed rules, colors, timestamps, buttons, string selects and
  entity selects, and `model_key` replacements.
- Render a modal template into a discord.py modal with text inputs.
- Build component and modal IDs from `uid` maps through a builder the plugin passes in, so the
  new ID format (Core change `component-ids`) plugs in without changing templates.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:2-91`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v1/serializer/MessageDataSerializer.kt`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v1/builder/MessageBuilder.kt:1-309`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/modal/`

Out of scope: Components V2 (Core change `components-v2`), the ID format (Core change
`component-ids`), routing component interactions (Core change `command-tree`).

## Capabilities

### New Capabilities

- `core-templates`: loading, validating and rendering message and modal templates.

### Modified Capabilities

None.

## Impact

New module `xincord.core.templates`. `xincord.core.config` exposes its unknown-key walker for
reuse.
