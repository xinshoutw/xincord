## Context

v3's `InteractionLogger` (`InteractionLogger.kt:25-41`) calls `deferReply(true)` for every slash
and message-context command before plugins see it; the only way out is the CLI flag
`--no-auto-defer-interactions`, so plugins open modals from buttons, never from commands. Plugins
return `guildCommands()` (every plugin with commands except BotInfo) or `globalCommands()`
(BotInfo). `ListenerManager` (`ListenerManager.kt:18-36`) overwrites the guild commands of every
guild at each start and again on guild join, which grows with the number of guilds.

## Goals / Non-Goals

**Goals:** B5's ephemeral defer with an `extras` opt-out, the guild/global split, and uploads only
when the payload changed.

**Non-Goals:** when to sync and setting the translator (runtime); component routing; autocomplete
routing, which discord.py already does per command and parameter.

## Decisions

- **Defer** happens in `CommandTree.interaction_check`, which discord.py awaits before every
  application command and autocomplete interaction; only `InteractionType.application_command`
  is deferred, with `ephemeral=True, thinking=True` like JDA's `deferReply(true)`. The opt-out is
  the invoked command's own `extras["defer"]`.
- **Scopes.** All plugin commands stay registered globally in the tree, so discord.py dispatches
  them in every guild. Uploading splits them: `extras["global"]` marks the few global commands;
  the rest are uploaded to each guild, as v3's guild commands were.
- **Uploads** go through `client.http.bulk_upsert_global_commands` and
  `bulk_upsert_guild_commands`, the calls `CommandTree.sync` makes, because `sync` cannot upload a
  subset of the tree. Payloads use `get_translated_payload` when a translator is set, as `sync`
  does.
- **Hashes** are SHA-256 of the payload as compact JSON with sorted keys, stored in the core's
  store (`core` namespace, `commands:global` and `commands:guild:<id>`) after a successful upload.
  Forcing a guild is for guild joins: a guild that removed the bot may have lost its commands.

### v3 behaved differently

- v3 behaved differently: every start re-uploaded the guild commands to every guild; now only
  changed scopes are uploaded.

## Risks / Trade-offs

- If commands are changed in Discord by another tool, the stored hash does not notice; forcing a
  sync (on guild join, or by clearing the stored hashes) repairs it.

## User-visible changes

None. Commands keep their ephemeral "thinking" response and their guild or global scope.
