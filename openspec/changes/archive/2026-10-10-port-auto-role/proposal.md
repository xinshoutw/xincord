## Why

Decision C1 ports AutoRole after BasicCalculator, and F3 lists it as in use. v3's AutoRole
(`Plugins/AutoRole`, 3 Kotlin files, 81 lines) has no commands, text or components: when a member
joins one of the guilds in its config, it sets that member's roles to the guild's configured list.
It is the first port with a gateway listener and a privileged intent.

## What Changes

- New plugin package `xincord.plugins.auto_role`, registered as `AutoRole`, declaring the members
  intent, with a bundled `config.yaml` that lists no guilds (v3 shipped real guild and role IDs)
  and no lang files.
- `config.yaml` keeps v3's shape (`guilds[].guild_id`, `guilds[].role_ids`) and validation, so v3
  files load unchanged; v3's `enabled` key only warns.
- A member who joins a configured guild, bots included, gets that guild's roles, looked up in that
  guild at the join. v3's defects are fixed: each role is added with its own request instead of
  replacing the member's roles; a role that is missing, belongs to another guild or that the bot
  cannot give is skipped and logged instead of failing the whole assignment; roles created after
  startup work without a reload.
- When the bot is ready, or when the plugin loads into a ready bot, the plugin logs the configured
  guilds, permissions and roles that keep it from giving roles; v3 showed nothing until a member
  joined.
- Test helpers for listeners: guild, role and member fakes, `plugin_fakes.dispatch` and a `config`
  argument for `plugin_fakes.load_plugin`.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:8-25`
- `XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:7-31`
- `XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/config/ConfigSerializer.kt:6-24`
- `XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/resources/config.yaml:1-10`
- `XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/resources/info.yaml:1-8`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:68-72` (the members intent)

Out of scope: waiting for members to pass membership screening (v3 gave the roles at the join); an
audit log reason (v3 sent none); removing roles when members leave; the Web Dashboard's reload
path (B13).

## Capabilities

### New Capabilities

- `plugin-auto-role`: the AutoRole plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/auto_role/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/auto_role/`; new fakes in
`tests/support/discord_fakes.py` and helpers in `tests/support/plugin_fakes.py`. No core changes
and no new dependencies. Enabling the plugin makes the bot request the privileged members intent,
which the bot's application must allow in the Discord developer portal.
