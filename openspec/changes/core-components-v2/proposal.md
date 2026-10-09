## Why

Decision B10 asks for Components V2 in message templates alongside the v1 format. v3's MessageCreator
v2 already accepts `is_components_v2` and a `components_v2` list (sections, text displays, media
galleries, separators, files, containers and V2 action rows). No shipped template uses it yet, but
plugins ported later may.

## What Changes

- Validate `is_components_v2` and `components_v2` when templates load: component types with v3's
  aliases, required fields, and the V2 mode rules.
- Render V2 templates into a discord.py `LayoutView`, with placeholders, `id`s, inferred section
  accessories, media from URLs or local files, buttons by style name or number, premium buttons,
  selects with default values, and container settings.
- Model keys in V2 components; an embed supplied for a top-level model becomes a container.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/builder/MessageBuilder.kt:9-485`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:92-127`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/example/message_components_v2_example.yml`

Out of scope: V2 modal components beyond text inputs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-templates`: message templates gain Components V2.

## Impact

`xincord.core.templates` gains the V2 schema and renderer; `Message` gains `files` and may carry a
`LayoutView`.
