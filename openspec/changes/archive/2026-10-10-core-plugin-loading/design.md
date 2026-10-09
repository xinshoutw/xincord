## Context

v3's `PluginLoader` (`PluginLoader.kt:39-245`) scans `plugins/*.jar`, reads each `info.yaml`
(`InfoSerializer.kt:7-40`: name, main class, `depend_plugins`, `soft_depend_plugins`,
`require_intents`, cache flags, member cache policies, `component_prefix`), orders the plugins
with a recursive walk, and then calls `load()` on them in reverse (`PluginLoader.kt:147`), so
dependents start before their dependencies. Every installed plugin exports its config and lang
files (`PluginEvent.kt:23-73`); whether it does anything is decided by an `enabled` key in its own
config that each handler checks. GUILD_MEMBERS is always requested.

## Goals / Non-Goals

**Goals:** B3 and B4: entry-point discovery, metadata as module constants, `graphlib` ordering,
isolation, files under `plugins/<Name>/`, intents fixed before connecting, reload with dependents.

**Non-Goals:** logging in, command sync and interaction routing (command-tree, runtime); the
operator commands that trigger reloads (runtime); member cache flags (when a plugin needs them).

## Decisions

- **Entry points.** Group `xincord.plugins`; the entry-point name is the plugin's display name
  (B18), which is also its directory and its name in the core config; the value is the extension
  module. Official plugins register in `packages/xincord-plugins/pyproject.toml`.
- **Metadata** is read from the module constants `DEPENDS`, `SOFT_DEPENDS` (tuples of names) and
  `INTENTS` (`discord.Intents`). Discovery imports the module to read them before the bot exists,
  and discord.py's `load_extension` executes the module again, so plugin modules must not do work
  at import time.
- **Enabled list.** The core config's `plugins` list replaces v3's per-plugin `enabled` keys, so a
  disabled plugin is never imported and handlers need no checks. The v3 migration fills the list.
- **Ordering.** Plugins with missing hard dependencies are removed repeatedly until none remain;
  `graphlib.TopologicalSorter` orders the rest, with soft dependencies as edges when enabled; the
  members of a reported cycle are removed and sorting repeats.
- **Intents** are `discord.Intents.default()` plus each kept plugin's `INTENTS`, computed before
  the bot is created.
- **Bot.** `xincord.core.bot.Bot` subclasses `commands.Bot` (extensions and Cogs need it) with
  `command_prefix=commands.when_mentioned` and no help command, since xincord uses application
  commands only. The runtime change extends it.
- **Context.** Before loading a plugin the bot creates its `PluginContext`; the extension's
  `setup(bot)` fetches it with `bot.plugin_context(__name__)` and calls `config(Model)` and
  `lang(default_locale)`. Templates come from `Templates.load(lang)`.
- **Isolation.** discord.py wraps failures in `commands.ExtensionError`; the bot turns them into
  `PluginError` with the plugin's name, logs them, and skips the plugin's dependents.
- **Reload** uses `reload_extension`, which restores the previous module when the new one fails,
  for the plugin and then its loaded dependents in load order; it stops at the first failure.
  Hot-loading a plugin after startup checks its intents and dependencies first. Reloading a loaded
  plugin does not re-check intents: its code does not change while the bot runs.

### v3 behaved differently

- v3 behaved differently: plugins loaded in reverse dependency order; they now load after their
  dependencies.
- v3 behaved differently: an exception in one plugin's config or lang could stop the whole bot;
  now only that plugin and its dependents are skipped.
- v3 behaved differently: every installed plugin exported its files and checked an `enabled` key
  in each handler; only enabled plugins are imported now.
- v3 behaved differently: GUILD_MEMBERS was always requested; now only when an enabled plugin
  declares it.

## Risks / Trade-offs

- Discovery imports enabled plugins twice (once for metadata, once as an extension). Plugin
  modules are declarations; the cost is negligible.
- A plugin whose new code needs more intents must be restarted, not reloaded.

## User-visible changes

- Plugins are enabled in the core `config.yaml` (`plugins: [AutoRole, ...]`) instead of an
  `enabled` key in each plugin's config; `python -m xincord.core.migrate_v3` fills the list.
- Plugins that are not enabled no longer create files under `plugins/<Name>/`.
- The privileged members intent is requested only when an enabled plugin needs it.
