## Context

CustomCommands (`xincord.plugins.custom_commands`, v3's SimpleCommand, ported in
`port-simple-command` and renamed in `rename-plugins`) registers five administrator guild
commands from the module table `COMMANDS`, localized from `lang/zh-TW/register.yaml`. Each posts
the message template named after it, rendered in the default locale zh-TW with v3's `%bot_id%` and
`%bot_name%`, in the command's channel, then deletes the command tree's ephemeral deferral; when
the channel takes no messages or refuses this one, the message replaces the deferral. The plugin
has no `config.yaml`. v3 hard-coded the same set in three Kotlin files (`Register.kt:9-60`,
`CmdFileSerializer.kt:7-23`, `SimpleCommand.kt:21-58`; inventory B3).

On 2026-10-10 the owner decided (`HANDOFF.md` section 6, and the task of this change) that the
commands are defined in `plugins/CustomCommands/config.yaml`, with as much customization as
practical: operators add, remove and change commands without code (names, descriptions and their
localizations, the template, who may use it, where it answers, which guilds get it); v3's five
commands are the bundled default, with the example account number, so a fresh install behaves
like v3; v3's lang files copied at cutover keep working; the config is validated at load and
followed on reload; what would need a new core subsystem is left out and recorded.

Checked on 2026-10-10: the local v3 copy (`XsDiscordBotKt/Server/plugins/SimpleCommand/`, a
3.2.x install) has no `config.yaml`, and its `register.yaml` and five templates compare equal to
the resources in v3's jar (compared with `cmp`, without reading the account numbers). So the
operator never edited `register.yaml`, and the bundled `config.yaml`, which holds the same names,
loses nothing.

## Goals / Non-Goals

**Goals:** the owner's decision, test-first; v3's five commands, payloads and messages unchanged
for a fresh install and for a migrated v3 install; every operator mistake that Discord would
refuse, or that would fail at each use, caught at load with the file and the key named.

**Non-Goals:** the features in "Left out"; another plugin's commands; the v3 data import.

## Decisions

### Config schema

```yaml
commands:                        # required; [] registers no command
  - name: cub-none-card          # Discord's name rules as discord.py checks them
    description: generate message  # 1 to 100 characters
    localizations:               # optional, per Discord locale; each key optional
      zh-TW: {name: 國泰世華-無卡, description: 取得訊息}
    template: cub-none-card      # optional: lang/<locale>/message/<template>.yaml; the name
    permissions: [administrator] # optional, discord.py's flag names; [] for every member
    reply: channel               # optional: channel, public or ephemeral
    guilds: []                   # optional: guild IDs; empty for every guild
```

- `config.py`: `Localization` (`name`, `description`, both optional), `CommandSpec` (the keys above,
  with the defaults shown) and `Config` (`commands`, required, no default). Each model is the
  core's frozen `Model`, so unknown keys warn, as v3's `enabled` does.
- `commands` has no default: the bundled `config.yaml` holds v3's five commands, whose zh-TW names
  cannot live in Python (no CJK in `*.py`), and a file without the key is an error that names it,
  rather than a plugin with no commands. A v3 file (only `enabled`) is therefore set aside by
  `migrate_v3` (below).
- Localizations live in the entry, grouped per locale (`zh-TW: {name, description}`), as
  `register.yaml` grouped them per command; Discord's payload keeps `name_localizations` and
  `description_localizations`. Renaming a command is one edit, and a command is one entry.
- `template` defaults to the command's name, as v3 named every template after its command, so the
  five bundled entries need no `template` and v3's copied templates keep their names.
- `permissions` lists discord.py's permission flag names (`discord.Permissions.VALID_FLAGS`:
  `administrator`, `manage_guild`, `manage_messages`, ...), the bits of Discord's
  `default_member_permissions`. The default is `[administrator]`, v3's
  `DefaultMemberPermissions.enabledFor(ADMINISTRATOR)`; `[]` sends no default permissions, so
  every member can use the command. Server administrators can still change it per role, user or
  channel in Server Settings > Integrations, as in v3.
- `guilds` lists guild IDs; empty means every guild the bot is in, as v3.
- The bundled `config.yaml` comments every key; its five entries give only `name`, `description`
  and the zh-TW localizations, so the defaults are v3's behavior.

### Validation

The model checks each value, and `setup` checks what needs several entries or the lang files; both
fail the load with `ConfigError` lines `<file>: <key>: <problem>`, all problems at once. The core
logs the error and disables the plugin.

- `name`: discord.py's own `validate_name` (`discord.app_commands.commands`), which `Command`
  calls: 1 to 32 characters, lower case, letters, digits, `-` and `_`. It refuses the apostrophe
  that Discord allows, so the model refuses what discord.py would refuse with no key named.
- Localized names: the core's `is_command_name`, the check of `register.yaml` names, made public in
  this change (Discord's rules: also `'`).
- Descriptions and localized descriptions: 1 to 100 characters (`DESCRIPTION_MAX`), as
  `register.yaml`'s.
- Locales: `discord.Locale` values (`zh-TW`, `en-US`, `ja`, ...); permissions: discord.py's flag
  names; guild IDs: positive integers; `reply`: one of the three values.
- Names are unique in every locale: the base names among themselves, and in each locale that any
  entry localizes, the name that clients of that locale see (the localized name, else the base
  name). Discord refuses a guild's whole upload when two commands share a name, and two commands
  that look the same would confuse members anyway.
- At most 100 commands. Discord takes 100 slash commands per guild, and discord.py's tree refuses
  the 101st command because the core keeps every plugin's commands in it (guild lists are a filter
  of the upload, below). The other plugins' commands and `/xincord` share that limit; the plugin
  cannot count them, because it may load first, and discord.py's `CommandLimitReached` then names
  no key.
- Templates: the template of each command exists in the default locale (the fallback of every
  other locale); in every locale where it exists, it holds no `uid` (a component that needs an ID
  builder and a handler) and no `model_key` (a model the plugin cannot supply), found by walking
  the parsed template's fields. v3 had no ID manager in this plugin either, and such a template
  failed at each use. Link buttons, V2 buttons with a fixed `custom_id`, files and placeholders
  pass. `Templates.load` already refuses malformed templates with the file named.

### Commands

`CustomCommands.command(spec)` builds `app_commands.Command(name=localized(spec.name, names),
description=localized(spec.description, descriptions), callback=self.post_message,
extras=extras)`, where `names` and `descriptions` come from the localizations and `localized` is
the core's new helper. `default_permissions` is `discord.Permissions` of the listed flags, or None
for `[]`. `extras` holds `guilds` (a frozenset) when the entry lists guilds, and `defer: False`
for a public reply. `setup` adds one command per entry in the file's order. The cog keeps the
entries by name for the callback, which reads `interaction.command.name`.

### Answering

`post_message(interaction)` finds the entry and:

- `channel` (the default, v3): renders the template in the default locale, posts the whole
  message to `interaction.channel` and deletes the tree's ephemeral deferral; when the channel takes
  no messages or refuses this one, it logs a warning and edits the deferral into the message,
  rendered again (unchanged from `port-simple-command`).
- `public`: the tree does not defer it (`extras["defer"]` is False); the callback defers with
  `response.defer(thinking=True)`, which is public, then edits that response into the message in
  the default locale. A public reply cannot follow the tree's ephemeral deferral: the first
  follow-up of a deferred response takes the deferral's flags. Deferring first keeps Discord's
  three seconds when a Components V2 template uploads files.
- `ephemeral`: edits the tree's ephemeral deferral into the message, rendered in the user's locale
  (`interaction.locale`), else in the default locale through the core's template fallback.

Posts and public replies use the default locale for every user, as v3 did for its posts, since
everyone reads them; only an ephemeral reply, which only the user sees, follows the user's locale.

### Placeholders

Templates are rendered with `placeholder_values(interaction)` (v3's `Placeholder.get(event)`): the
bot's `bot_id` and `bot_name` (v3's global keys, as before), the user's `user_id`, `user_mention`,
`user_name`, `user_avatar_url` and `member_*` keys, `language`, the channel's `channel_*` keys and
the command's keys. User text is never parsed (B10). A mention in a posted message pings the user,
as the bot's `allowed_mentions` allows users (B19).

### Core API

- `xincord.core.i18n.is_command_name(name)`: the existing `register.yaml` name check, public.
- `xincord.core.i18n.localized(default, translations)`: an `app_commands.locale_str` whose extras
  carry `translations` (Discord locale to text); `Translator.translate` returns the requested
  locale's text, or None (no fallback, as for `register.yaml` keys). `Lang.command` strings work as
  before.
- `CommandTree.payloads(guild_id=None)`: given a guild, its guild payload leaves out the guild
  commands whose `extras["guilds"]` does not contain it; `sync_guild` builds each guild's payload
  so. Without a guild the guild payload holds every guild command, as before. The guild lists stay
  a filter: every plugin's commands stay in discord.py's global table, so discord.py still refuses
  a name that two plugins use, and the stored hash per guild already follows each guild's payload.
  discord.py's own guild commands (`add_command(..., guilds=...)`) would leave a duplicate name to
  Discord's refusal of the whole upload.

### Failed reloads (core fix)

Found while writing this change's reload tests and confirmed with a scratch probe on BotInfo on
2026-10-10: when a reload fails, discord.py's `reload_extension` runs the previous module's `setup`
again (`lib.setup(self)`), and that setup reads the plugin's files again, so a `config.yaml` or
lang file that broke the new version broke the previous one too. discord.py then left the plugin
unregistered (no cog, no commands) while the core kept it in `loaded`, and `reload_plugin` and the
full reload failed with `Extension ... has not been loaded` until a restart. `core-plugins`
promised the previous version ("a failed reload SHALL keep the previous version"), and this change
makes config reloads the operator's way to change CustomCommands.

- `PluginContext` records what `config(model)` (by the model's qualified name) and `lang(locale)`
  returned; `replaying()` gives a context that hands those back instead of reading the files.
- `Bot._reload` gives the new version a fresh context and keeps the previous one, which
  `plugin_context(module)` returns, replaying, while discord.py runs the previous setup. discord.py
  removes the extension's modules from `sys.modules` before that call and restores them only after
  it (2.7.1: `_load_from_module_spec` and `reload_extension`), while every setup of a load runs
  with its module in `sys.modules`; that is how the core tells the two apart. Should a later
  discord.py change that order, the previous setup reads the files again, as before this change,
  and the core test "Broken files keep the previous version" fails.
- When discord.py restored the previous version, the core keeps its context, with its recorded
  reads, and reports `plugin X failed to reload: ...` (the new version's error, which names the
  file and the key). When the previous version fails too, the core removes what that setup added
  (discord.py's `_remove_module_references`), forgets the plugin and reports `plugin X failed to
  reload and is unloaded: ...`; a full reload, or `load_plugin`, loads it again.
- Templates are not replayed: `Templates.load(lang)` parses again the files that the previous lang
  lists, so a broken template that the previous version used unloads the plugin. Replaying them
  would need plugins to load templates through their context.
- Plugins that depend on one that a failed reload unloaded stay loaded, as the reload stops at the
  failure; their own reload or a full reload sorts them out.

### Migration

`migrate_v3.set_aside_v3_configs(root)` renames `plugins/CustomCommands/config.yaml` to
`config.v3.yaml` when the file holds no key but `enabled` (SimpleCommand's, which
`move_renamed_directories` moved there), with a report line; a file with other keys stays, and a
file with a `config.v3.yaml` beside it stays with a report line. `migrate_directory` runs it last,
after writing the new core config: a failure before that leaves the v3 core config and the switch
file, so that a second run still lists CustomCommands, and a failure of the rename itself leaves
an error at the plugin's load that names `commands`. The plugin then writes its bundled
`config.yaml` with v3's five commands at its first load. The table `SET_ASIDE` names the plugins
concerned (CustomCommands only). A 3.2.x directory, which has no such file, needs nothing.

### Lang files

The bundled `lang/zh-TW/` keeps v3's five templates (example account number, v3's names) and drops
`register.yaml`. An operator's `register.yaml`, such as v3's copied at cutover, still loads and is
checked by the core, but nothing reads it; the bundled `config.yaml` holds the same names. An
operator who adds an en-US template for some commands only gets the core's warning at each load
that en-US lacks the others (`en-US lacks template keys of zh-TW: ...`), which is what happens:
those fall back to zh-TW.

### Checks (2026-10-10)

- The wheel from `uv build --package xincord-plugins` lists `config.yaml` and the five templates,
  no `register.yaml`, and the `CustomCommands` entry point.
- A scratch virtual environment with both wheels: `xincord --no-online` with `plugins:
  [CustomCommands]` in an empty directory exits 0 and writes `plugins/CustomCommands/config.yaml`
  (the bundled file, byte for byte) and the five templates; with a v3 `plugins/CustomCommands/
  config.yaml` holding only `enabled: true` it exits 1 and the log names `commands`; a v3-shaped
  directory (`plugins/SimpleCommand/` with `enabled: true`, v3's `register.yaml` and templates with
  other numbers) migrated with `python -m xincord.core.migrate_v3 .` reports the move and the
  set-aside file, and `--no-online` then exits 0 with the bundled config written and the
  operator's templates kept.
- A scratch probe through discord.py's own `Interaction` and `CommandTree._call`, with the bot's
  REST and webhook requests recorded: the channel command defers with flags 64, posts the embed
  to `POST /channels/{id}/messages` and deletes `@original`; a `public` one defers with type 5 and
  no flags, then patches `@original` with the zh-TW content and the user's mention and channel
  name; an `ephemeral` one defers with flags 64 and patches `@original` with the en-US template
  for an en-US user and the zh-TW one for a Japanese user; `payloads(10)` holds a command limited
  to guild 10 and `payloads(11)` does not, and `permissions: []` gives no default permissions.

### Tests (xfail-first)

- Core: `tests/core/test_i18n_load.py` (`is_command_name`), `test_i18n_lookup.py` (`localized`),
  `test_command_tree.py` (a guild list), `test_plugins.py` (failed reloads, with fake plugins
  that read a config, a lang directory or a file of their own), `test_migrate_v3.py` (the switch
  file).
- Plugin: `tests/plugins/custom_commands/`: `test_plugin.py` (installation), `test_command.py`
  (payloads from the bundled and operator configs, permissions, guild lists, the callback),
  `test_post.py` (the channel posts, the template key, the user's placeholders), `test_reply.py`
  (public and ephemeral replies), `test_config.py` (validation), `test_reload.py` (reloads).
  `conftest.py` gains Giveaway's `plugin_modules` autouse fixture, since failed loads and reloads
  make discord.py import the plugin's modules again; the reload tests look the new cog up by name.
- Golden data (`golden.yaml`) is unchanged: the bundled config must give v3's payloads and embeds.

## Left out

- Command options (arguments) and placeholders for their values: a schema for option types,
  choices and limits, and their rendering, is a feature of its own that the owner did not ask for.
- Per-role, per-user or per-channel command permissions: Discord lets only a user's OAuth2 Bearer
  token with `applications.commands.permissions.update` set them, never a bot token, so the bot
  would need an OAuth2 flow (a new core subsystem). Server administrators set them in Server
  Settings > Integrations, as in v3.
- Buttons and menus that run actions (post another template, give a role): they need component
  IDs routed to configured actions, a subsystem of its own; templates with a `uid` are refused.
  Link buttons work.
- Global commands (direct messages, user installs): v3's commands are guild commands, and a
  command that posts in a guild channel has no use outside a guild.
- One name with different templates per guild: names are unique, as in discord.py's command table
  that the core keeps for every guild; two names, each with its `guilds`, do the same.
- A configurable default locale, which picks the fallback templates and the locale of posts: the
  bundled templates are zh-TW, as v3; Giveaway's `defaultLocale` shows how to add one.
- Cooldowns and usage limits: not asked, and they need state per user.

## v3 behaved differently

- v3 behaved differently: adding, removing or renaming a command needed changes to three Kotlin
  files and a new jar (inventory B3); the commands come from `config.yaml` and follow reloads.
- v3 behaved differently: templates got only v3's global placeholders; they get the user's, the
  bot's and the channel's (`placeholder_values`).

## User-visible changes

1. The commands are defined in `plugins/CustomCommands/config.yaml` (bundled: v3's five, with
   v3's names, description, zh-TW localizations and Administrator permission); its comments are
   new copy.
2. Per command, operators set the localizations, the template, the permissions (everyone with
   `[]`), a public or an ephemeral reply instead of the channel post, and the guilds.
3. Ephemeral replies use the user's locale; posts and public replies the default locale zh-TW.
4. Templates may use the user's and the channel's placeholders (`%user_mention%`, `%user_name%`,
   `%channel_name%`, ...).
5. `lang/zh-TW/register.yaml` is no longer bundled or read.
6. A config error, or a template with a `uid` or a `model_key`, disables the plugin with the file
   and the key in the log; a broken edit followed by a reload keeps the commands that were loaded.
7. `python -m xincord.core.migrate_v3` renames v3's `plugins/CustomCommands/config.yaml` (only
   `enabled`) to `config.v3.yaml`, with a report line.
8. Every plugin: a reload whose `config.yaml` or lang files are broken keeps the previous version
   running with its old config and lang, and its summary names the file and the key; when the
   previous version fails too, the summary says `... failed to reload and is unloaded: ...` and a
   later reload loads it again (before: the plugin vanished, still listed as loaded, until a
   restart).

## Risks / Trade-offs

- A command whose guild list or name changed stays registered in a guild whose upload failed,
  until the next successful upload (the core logs the failure and retries at the next start or
  reload); there it still runs, since the callback does not check the guild.
- Another plugin's command with the same name: whichever plugin loads second fails to load
  (discord.py's `CommandAlreadyRegistered`), in the order of the core config's `plugins` list.
- A copied v3 `register.yaml` edited after the cutover changes nothing; the bundled config's
  comment says where the names live.
- A broken template that the loaded commands use, followed by a reload, unloads the plugin until a
  reload with the template fixed (templates are not replayed; see "Failed reloads").

## Manual smoke checklist

On a test guild, with a bot token and `plugins: [CustomCommands]` in `config.yaml`:

1. Start in an empty directory: `plugins/CustomCommands/config.yaml` lists the five commands, the
   five templates are under `lang/zh-TW/message/`, and there is no `register.yaml`.
2. As an administrator with a zh-TW client, the five commands show their zh-TW names; with an
   en-US client, v3's base names and `generate message`; a member without Administrator sees none.
3. `/cub-none-card` posts v3's embed in the channel and the "thinking" message disappears.
4. Add an entry `rules` with `reply: public`, `permissions: []`, an en-US localization and
   `lang/zh-TW/message/rules.yaml` holding `content: "%user_mention% read the rules"`, then
   `/xincord reload CustomCommands`: after the client refreshes its commands, a member without
   Administrator runs `/rules`, which answers publicly ("used /rules") and pings that member.
5. Set `reply: ephemeral` and add `lang/en-US/message/rules.yaml`: an en-US client gets the en-US
   text, a zh-TW client the zh-TW text, both visible to the user only.
6. Set `guilds: [<test guild ID>]` with the bot in a second guild: after the reload only the test
   guild lists `/rules`.
7. Repeat a name and reload: `/xincord reload CustomCommands` answers that the reload failed, the
   log names `commands.N.name`, and the commands keep working. Remove a command and reload: it
   disappears from the guild.
8. Cutover: run `python -m xincord.core.migrate_v3` on a copy of a v3.3+ directory whose
   `plugins/SimpleCommand/config.yaml` says `enabled: true`: the report names
   `plugins/CustomCommands/config.v3.yaml`, and the first start writes the bundled `config.yaml`;
   v3's copied templates (real account numbers) are the ones posted.

## Inventory audit

`docs/porting/analysis/inventory/SimpleCommand.md`, against this change (the rest stays as
`port-simple-command` audited it):

- Overview (1): the hard-coded command set is now the bundled config ("Commands come from the
  config", "Command payload").
- Lifecycle (2): `reload()` re-reading the config and rebuilding the commands is "Config changes
  apply on reload"; the localizer built from `register.yaml` is replaced by the entries'
  localizations ("Command payload", "Translated from the table").
- Slash commands (3): names, description, zh-TW localizations and the Administrator permission come
  from the bundled entries ("Command payload"); the posting steps are unchanged ("Message",
  "Command callback").
- Configuration (6): `enabled` is the core's `plugins` list; a v3 file that holds only `enabled` is
  set aside by the migration ("Switch file set aside") and refused by the plugin ("Missing
  commands").
- Localization and templates (7): the template per command and the default-locale rendering are
  "Template key" and "Default locale"; operator-editable files are the config and the templates.
- Bugs (12): B3 is fixed by this change (a "v3 behaved differently" entry); B1 and B2 stay as
  `port-simple-command` fixed them.
- Testability (13): the command-to-template mapping is the entry's `template`; the payload and
  embed goldens are unchanged.
