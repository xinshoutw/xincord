## Why

Every message template uses `%key%` placeholders. v3 substitutes them with commons-text, which
expands placeholders found inside substituted values (so a nickname such as `%bot_name%` expands,
and a self-reference throws), and caches one mutable substitutor per user, shared by all plugins.
Decision B10 keeps the `%key%` syntax with a single pass, never parses user input, and gives every
render a fresh context.

## What Changes

- `render(text, values)`: one left-to-right pass over `%key%` placeholders, the `$` escape, and
  unknown keys left as written.
- Value families with the v3 key names and defaults, built per render from discord.py objects:
  the acting user (`Placeholder.get`), user, member, guild, channel and event families
  (`Placeholder.putUser`, `putMember`, `putGuild`, `putTextChannel`, `putEvent`), each with an
  optional key prefix such as `wbg@`.
- JDA's locale names (enum name and native name) for `guild_locale` and `language`.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Substitutor.kt:6-93`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:14-287`
- JDA 6.4.1 `net.dv8tion.jda.api.interactions.DiscordLocale` (locale names)

Out of scope: interaction-specific keys (`command_*`, `component_*`, `language`,
`channel_category_name`, `subcommand_name`), which come with Core change `command-tree`;
plugin-specific keys; per-user custom keys (`Placeholder.update`), which plugins now pass at render
time.

## Capabilities

### New Capabilities

- `core-placeholders`: placeholder substitution and the v3 placeholder key families.

### Modified Capabilities

None.

## Impact

New module `xincord.core.placeholders` and resource `xincord/core/resources/locales.yaml`.
