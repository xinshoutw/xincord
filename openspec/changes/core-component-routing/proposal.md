## Why

In v3 every plugin listens to every button, select and modal event and checks whether the ID
starts with its prefix (`GlobalUtil.kt:52-62`). Decision B9 (with resolution 4) needs one place
that knows which plugin owns an ID, in the new or the legacy format, so the core can upgrade a
message's legacy IDs right after a plugin handled one of them.

## What Changes

- Plugins register a component ID codec and a handler from their setup; the bot sends each
  component and modal-submit interaction whose ID a codec owns to that handler with the parsed
  fields, and logs handler errors with the plugin's name.
- Routes follow the plugin's lifecycle: a failed load or a reload removes the old routes.
- After a legacy ID was handled, the bot fetches the message, rewrites its legacy IDs with the
  registered codecs and edits it once.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/GlobalUtil.kt:52-62`

Out of scope: the interaction placeholder keys (Core change `core-interaction-values`) and the
interaction log (Core change `runtime`).

## Capabilities

### New Capabilities

- `core-component-routing`: routing component and modal interactions to plugins and upgrading
  legacy IDs after use.

### Modified Capabilities

None.

## Impact

`xincord.core.bot.Bot` gains `route` and an `on_interaction` handler. No new dependencies.
