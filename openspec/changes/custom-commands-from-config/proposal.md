## Why

On 2026-10-10 the owner decided that CustomCommands (v3's SimpleCommand) defines its commands in
`plugins/CustomCommands/config.yaml`, with as much customization as practical (`HANDOFF.md`
section 6). The port kept v3's command set: five commands fixed in code (`COMMANDS`), localized
from `register.yaml`, each posting the template named after it in the channel, for administrators
only. v3 needed Kotlin changes in three files to add one (inventory B3), and so does the port.

## What Changes

- `config.yaml` lists the commands. Per entry: `name` and `description` with `localizations` per
  Discord locale; `template`, the message template it posts (v1 or Components V2, from
  `lang/<locale>/message/`, the command's name by default); `permissions`, Discord's default member
  permissions (Administrator by default, as in v3; an empty list lets every member use it);
  `reply`, where it answers: `channel` (a message in the channel, v3's way and the default),
  `public` (a public reply) or `ephemeral` (a reply only the user sees, in the user's locale);
  `guilds`, the guilds that get it (every guild by default).
- The bundled `config.yaml` defines v3's five commands with v3's zh-TW names and descriptions, so a
  fresh install behaves like v3; the bundled templates keep their names and their example account
  number, so v3's lang files copied at cutover keep working. `register.yaml` is no longer bundled
  or read: the localizations live in `config.yaml`.
- Templates get the placeholders of the user, the bot and the channel (`%user_mention%`,
  `%channel_name%`, ...), not only v3's `%bot_id%` and `%bot_name%`.
- The config is validated at load: Discord's name rules, description lengths and locales, known
  permissions, positive guild IDs, names unique in every locale, at most 100 commands, and
  templates that exist in the default locale and can be posted (no component IDs or models). An
  error disables the plugin with the file and the key named. A reload reads the config again, and
  the core uploads the commands whose payload changed.
- Core: `is_command_name` (the `register.yaml` name check) becomes public, `localized(default,
  translations)` gives command strings that the translator resolves from a table, and a guild
  command whose `extras` sets `guilds` is uploaded to those guilds only.
- `xincord.core.migrate_v3` sets v3's `plugins/CustomCommands/config.yaml` (SimpleCommand's, which
  held only `enabled`) aside as `config.v3.yaml`, so that the plugin writes its bundled commands.
- Core fix found here: a reload whose `config.yaml` or lang files no longer validate removed the
  plugin for good (discord.py runs the previous version's setup again, which read the same broken
  files, and the core kept listing the plugin, which no reload could bring back until a restart).
  The previous version now gets the config and lang it loaded before; when it fails anyway, the
  plugin is unloaded cleanly and a later reload loads it.

Kotlin sources (v3's fixed command set, replaced):
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:9-60`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/CmdFileSerializer.kt:7-23`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-62`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:21-58`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/config/ConfigSerializer.kt:5-8`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/config.yaml:1`
- `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/register.yaml:1-19`

Out of scope, each because it needs a new core subsystem or was not asked (`design.md`, "Left
out"): command options and their placeholders; per-role or per-user command permissions, which
only a user's OAuth2 token can set; buttons or menus that run actions; global commands for direct
messages and user installs; one command name with different templates per guild; a configurable
default locale; cooldowns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-custom-commands`: commands come from the config, answer in the channel or with a public
  or ephemeral reply, take the user's placeholders, are validated at load and follow reloads.
- `core-i18n`: the command name check is public; command strings can carry their translations.
- `core-command-tree`: a guild command can be limited to some guilds.
- `core-config`: the migration sets CustomCommands' v3 switch file aside.
- `core-plugins`: a failed reload keeps the previous version with the config and lang it had, or
  unloads the plugin cleanly when that version fails too.

## Impact

`packages/xincord-plugins/src/xincord/plugins/custom_commands/` (a new `config.py`, `cog.py`,
`__init__.py`, the bundled `config.yaml`; `lang/zh-TW/register.yaml` removed) and its tests;
`src/xincord/core/i18n.py`, `command_tree.py`, `plugins.py`, `bot.py` and `migrate_v3.py` and
their tests. No new
dependencies. Operators edit `plugins/CustomCommands/config.yaml` instead of code; a v3 install
runs `migrate_v3` as before and gets v3's five commands.
