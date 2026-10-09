## Why

Plugins ship their user-facing text as YAML under `lang/<Discord locale>/`: `register.yaml` for
command names and descriptions, flat string files such as `placeholder.yaml`, and message and
modal templates. Decision B7 keeps these formats, translates commands through discord.py's
`app_commands.Translator`, falls back to the default locale per key, and validates key sets at
load.

## What Changes

- Export a plugin's bundled lang files to `plugins/<Name>/lang/`, keeping the operator's edits
  unless renewal is forced.
- Load a plugin's lang directory: locales, flattened `register.yaml` keys, flat text files, and
  the paths of message and modal templates.
- Validate at load: YAML structure, Discord's rules for command names and descriptions, and key
  sets compared with the default locale.
- Look up texts and templates with fallback to the default locale; look up command localizations
  without fallback.
- A `Translator` that resolves `locale_str` values created by a plugin's lang.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/localizations/StringLocalizer.kt:22-90`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:24-37`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/Arguments.kt:12-15`

Out of scope: parsing message and modal templates (Core change `templates`), placeholder
substitution (Core change `placeholders`), setting the translator on the command tree (Core
change `command-tree`).

## Capabilities

### New Capabilities

- `core-i18n`: lang file export, loading, validation and lookup, and command translation.

### Modified Capabilities

None.

## Impact

New module `xincord.core.i18n`; adds the runtime dependency discord.py.
