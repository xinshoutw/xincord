## Why

Buttons, selects and modals carry their state in Discord custom IDs. v3 builds them as
`{prefix}{a..z}:{value};...` without escaping or a version, and Ticket panels, giveaway posts and
feedback forms keep those IDs on long-lived messages. Decision B9 (with resolution 4) asks for a new
versioned format, a v3 decoder that stays in the code permanently, and a lazy upgrade that edits a
message the first time one of its legacy IDs is used, instead of re-sending panels.

## What Changes

- A per-plugin codec that builds and parses versioned IDs with escaped values, 100 characters at
  most, and serves as the ID builder that templates take.
- The permanent v3 decoder: legacy prefix, letters in each plugin's v3 field order, hex fields.
- Converting a legacy ID to the new format, and rewriting the legacy IDs of a view rebuilt from a
  message so the caller can edit the message once.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:277-285`

Out of scope: routing interactions to plugins and editing the message after a legacy interaction
(Core change `command-tree`), and each plugin's legacy prefix, field list and golden IDs (each
plugin's change).

## Capabilities

### New Capabilities

- `core-component-ids`: the component and modal ID codec, its v3 decoder and the lazy upgrade.

### Modified Capabilities

None.

## Impact

New module `xincord.core.component_ids`. No new dependencies.
