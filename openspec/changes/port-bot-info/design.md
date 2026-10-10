## Context

v3's BotInfo (`Plugins/BotInfo`, 5 Kotlin files, 134 lines) has one global command and no
components, listeners or storage. `Event` (`PluginEventConfigure`) reads `config.yaml` (`enabled`
only, `ConfigSerializer.kt:5-8`), builds the command localizer when enabled (`Event.kt:16-29`) and
registers `Commands.slash("bot-info", "show about the bot data")` with `DefaultMemberPermissions.ENABLED`
as a global command (`Register.kt:14-19`, `Event.kt:48-54`); JDA's defaults give it the guild and
bot DM contexts and the guild install type. On `/bot-info`, `BotInfo` sums `memberCount` over
`jda.guilds`, writes `member_counts` and `guild_counts` into the process-wide
`Placeholder.globalSubstitutor` (`BotInfo.kt:24-27`) and edits the core's ephemeral deferred reply
into the v2 `bot-info` template in the user's locale, falling back to zh-TW (`BotInfo.kt:29-36`).
The global substitutor also holds `bot_id` and `bot_name` (`Placeholder.kt:15-18`). v3's core
always requested the members intent (`BotLoader.kt:68-72`), which keeps JDA's member counts
current. The inventory is `docs/porting/analysis/inventory/BotInfo.md`; its section 12 lists five
quirks. Decision C3 adds a source link with a configurable URL (AGPL section 13).

## Goals / Non-Goals

**Goals:** v3's command, reply and text in both locales; the source link of C3; the first global
command in a plugin, with v3's contexts and install type.

**Non-Goals:** counting unique users; other statistics (uptime, latency, version, plugins); a
license notice; guild-specific variants of the command.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/bot_info/`: `__init__.py` (metadata and `setup`),
  `config.py` (the config model), `cog.py` (the command, the reply and the counts),
  `config.yaml` and `lang/`. Entry point `BotInfo = "xincord.plugins.bot_info"`.
- `INTENTS = discord.Intents(members=True)`: discord.py updates `Guild.member_count` from member
  join and leave events, which Discord sends only with the privileged members intent; without it
  the counts would stay as they were when the bot connected. v3's core always requested the
  intent. The core adds it only when BotInfo, or another plugin that declares it, is enabled.
- `DEFAULT_LOCALE = "zh-TW"`, v3's default. `DEPENDS` and `SOFT_DEPENDS` are empty. No component
  IDs (v3 had no components; its unused `botinfo@` prefix has no counterpart) and no storage.
- `lang/`: v3's `register.yaml` (CRLF converted to LF) and `message/bot-info.yaml` per locale,
  with a final newline and a third field showing `%source_url%`, named `Source Code` in en-US (the
  zh-TW name is in `lang/zh-TW/message/bot-info.yaml`).
- `config.yaml` holds `source_url` with comments; v3's held only `enabled: false`.
- v3's `info.yaml` keys `author`, `coreApi` and `version` have no counterpart, as for _Example.
  v3 logged `BotInfo is disabled.` when off; a plugin missing from `plugins` is never imported.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists `bot_info/config.yaml`, the four lang files and the
  `BotInfo` entry point, and `xincord --no-online`, run from a scratch virtual environment with
  both wheels and `plugins: [BotInfo]`, loads the plugin, writes `plugins/BotInfo/config.yaml`
  and the en-US and zh-TW lang files, and exits with 0.

### Config

`Config(Model)` has `source_url`, a string that must match `https?://\S+` and hold at most 512
characters, by default `https://github.com/xinshoutw/xincord`. The owner's repository is the
default because neither the decisions nor the analysis name another URL; it is private today, so
the link works once the repository is public or the operator points `source_url` elsewhere. The
check runs when the plugin loads, so a typo disables BotInfo with an error that names `source_url`
instead of showing a broken link or making Discord refuse the reply. 512 characters is Discord's
limit for a link button's URL, the strictest place an operator's template can put the value (an
embed field takes 1024). v3's `enabled` is not part of the model: a v3 file loads and logs
`unknown key enabled`.

### Counts

`counts(guilds)` returns the number of guilds and the sum of their `member_count`, adding nothing
for `None` (a guild unavailable since the bot connected). The reply passes the bot's whole guild
cache, `interaction.client.guilds`, as v3 passed `jda.guilds`: a user in several guilds counts
once per guild, and bots count. discord.py keeps a guild that becomes unavailable during an outage
in that cache, with the member count it knew; JDA left such guilds out of both counts.

### Reply

`BotInfo.bot_info(interaction)` takes the counts at each use and renders `bot-info` in
`interaction.locale` (the user's locale, v3's `userLocale`), falling back to zh-TW per file, with
`guild_counts`, `member_counts`, `source_url`, and v3's global keys `bot_id` and `bot_name`, built
for this render only. Keys that other v3 plugins leaked into the global substitutor have no
counterpart. The numbers are plain integers, as v3's string templates wrote them. The reply edits
the deferred response, which the command tree deferred ephemerally as v3's core did, with the
rendered content, embeds and view (a link button an operator adds to the template).

### Command

`BotInfo.command()` builds the command with `app_commands.Command`, as the other plugins do:
`name=lang.command("bot-info", "bot-info.name")`, `description=lang.command("show about the bot
data", "bot-info.description")`, `callback=self.bot_info` and `extras={"global": True}`, which
puts it in the global payload. discord.py sends no `contexts` or `integration_types` unless they
are set, which would leave them to Discord's defaults; the command sets JDA's explicitly:
`allowed_contexts=AppCommandContext(guild=True, dm_channel=True, private_channel=False)` and
`allowed_installs=AppInstallationType(guild=True, user=False)`. `default_member_permissions` stays
unset, as v3's `DefaultMemberPermissions.ENABLED`. `setup` adds the command to the tree; the core
uploads it with the global commands when they change, and discord.py removes it when the plugin
unloads.

### Tests

- `tests/plugins/bot_info/`: `test_plugin.py`, `test_config.py`, `test_counts.py`,
  `test_reply.py` and `test_command.py`; `conftest.py` loads the plugin through its entry point.
- `tests/support/discord_fakes.py`: `FakeGuild` gains `member_count` (None by default, as
  discord.py reports for a guild whose count is unknown).
- `tests/fixtures/plugins/bot_info/golden.yaml`: v3's text, as the translated command payload and
  the reply embed per locale.
- The reply tests give the fake interaction a client whose `guilds` are fake guilds.

### v3 behaved differently

- v3 behaved differently: `member_counts` and `guild_counts` were written into the process-wide
  global substitutor at each use, so every plugin's later renders saw them, and per-user
  substitutors created afterwards kept a stale copy; the counts are now values of one render.
- v3 behaved differently: the reply edited the core's automatic deferral, so with
  `--no-auto-defer-interactions` the command got no reply; the command tree always defers it.
- v3 behaved differently: JDA left guilds that became unavailable during an outage out of both
  counts; discord.py keeps them, with the members it knew (none for a guild unavailable since the
  bot connected).
- v3 behaved differently: there was no source link; `/bot-info` shows `source_url` in a third field
  (C3), and the bundled `config.yaml` holds it instead of `enabled: false`.

Kept on purpose: the per-guild member sum (users in several guilds counted once per guild, bots
included); the user's locale with the zh-TW fallback; the ephemeral reply; v3's branding in the
templates (`ORDERLY BOT`, `ORDERLY SERVER`, the imgur icon), which operators change in
`plugins/BotInfo/lang/`; the base description `show about the bot data`, which differs from the
en-US localization `show about this Bot` and which only clients in other locales see.

### Inventory audit

Every section of `docs/porting/analysis/inventory/BotInfo.md` maps to this change:

- Overview (1): the global command and its embed are the command and reply requirements; the
  entry object, `info.yaml` and the plugin name are "The plugin installs as BotInfo".
- Lifecycle (2): exporting the lang files and reading the config are "First load creates the
  files" and the config requirement; the `enabled` warning is the core's `plugins` list; the
  localizer is `lang.command`; the lazily built message creator is `Templates.load` in `setup`, so
  a broken template fails the load; `reload()` is the core's reload, which replaces the whole cog;
  the global substitutor keys are a "v3 behaved differently" entry. No background jobs.
- Slash commands (3): the name, description, localizations, missing options and permissions,
  contexts and install type are "Command payload"; the uploads at startup and after reloads are
  the core's `sync_global` (core-command-tree, core-reload); the auto-defer is "Command callback"
  and a "v3 behaved differently" entry; the `enabled` and command-name checks are the `plugins`
  list and the tree's routing; the counts are "The counts sum the bot's guilds"; rendering in
  the user's locale and editing the deferred response are the reply requirement; use in DMs is
  the bot DM context in the payload. The core's interaction log covers v3's `[CMD]` line.
- Components (4) and events (5): none besides the command, so no component IDs, listeners or
  component golden data.
- Configuration (6): `enabled` is replaced by the core's `plugins` list; `source_url` (C3) is
  "The config sets the source link".
- Localization and templates (7): both locales, the zh-TW default and the whole-locale fallback
  (`en-GB` and `ja` get zh-TW) are "Locale and fallback"; the template text is the golden reply;
  the placeholders are "Reply" and "Bot placeholders"; v3's http-only filter is the core's
  (the icon URL passes it).
- Persistence (8) and external dependencies (9): none; the imgur icon stays in the templates.
- Discord requirements (10): the members intent for current counts is part of the install
  requirement; no permissions are needed beyond answering the command.
- Concurrency (11): a reload replaces the whole cog, and the counts are local values of one render
  instead of entries in an unsynchronized shared map.
- Bugs and quirks (12): the behaviors to preserve are scenarios (ephemeral reply: "Command
  callback"; user locale with the zh-TW fallback: "Locale and fallback"; global command in guilds
  and DMs without a permission restriction, and the zh-TW name: "Command payload"). Smells 1 and 2
  are "v3 behaved differently" entries ("Counts at each use" tests the second); 3, 4 and 5 are
  kept on purpose, as listed above.
- Testability (13): `compute_stats` is `counts` (`test_counts.py`); rendering per locale with the
  fallback is the golden reply; the command metadata snapshot is the golden payload.
- Assessment (14): the contexts and install types, the translator, the defer with
  `edit_original_response` and the local render values are the Command and Reply decisions.

## Risks / Trade-offs

- The members intent is privileged: if the bot's application does not allow it, the bot cannot
  connect. v3 always requested it, so the application probably allows it. With the intent,
  discord.py downloads every guild's members before `on_ready` (see AutoRole's design).
- The default source URL points to a repository that is private today: users who follow the link
  see a 404 until the repository is public or the operator changes `source_url`.
- An operator who keeps v3's `plugins/BotInfo/lang/` gets v3's embed without the source field,
  because only missing lang files are exported. `--force-renew-lang-resources` replaces them with
  the bundled ones, together with every other enabled plugin's lang files.
- Member counts are as current as discord.py's cache: member events missed while the bot was
  disconnected are corrected when a new session starts.

## Manual smoke checklist

On a test guild, with a bot token, the Server Members intent allowed for the bot in the Discord
developer portal, and `plugins: [BotInfo]` in `config.yaml`:

1. Start the bot: the log lists `BotInfo` as loaded, and `plugins/BotInfo/` holds the bundled
   `config.yaml` and the en-US and zh-TW lang files.
2. With an en-US client, run `/bot-info` in a guild: an ephemeral embed with v3's text, the number
   of guilds the bot is in, the sum of their member counts, and a Source Code field with
   `https://github.com/xinshoutw/xincord`.
3. With a zh-TW client, the command is listed under its zh-TW name and answers with the zh-TW
   embed; a client in another language, such as Japanese or English (UK), gets the zh-TW embed.
4. Run `/bot-info` in a DM with the bot: the same reply.
5. Have a second account join the test guild, then run `/bot-info` again: the member count is one
   higher, without a restart.
6. Set `source_url` to another https URL and run `/xincord reload BotInfo`: the reply shows the
   new link. Set it to `not-a-url` and reload: the log names `source_url`, and BotInfo keeps its
   previous version.
7. Without the Server Members intent in the portal, startup stops with a privileged-intents error.

## User-visible changes

Copy: the comments of the bundled `config.yaml`, and the new field name `Source Code` (en-US; the
zh-TW name is in `lang/zh-TW/message/bot-info.yaml`).

1. `/bot-info` shows a third field, Source Code, with the link from `source_url` (C3).
2. `plugins/BotInfo/config.yaml` has `source_url`, by default `https://github.com/xinshoutw/xincord`
   (a private repository today); an invalid URL disables the plugin with an error that names the
   key, and a v3 file warns `unknown key enabled`.
3. The command always answers; v3 needed the core's auto-defer switch.
4. During a Discord outage, unavailable guilds still count as guilds.
5. v3 lang files kept in `plugins/BotInfo/lang/` show v3's embed, without the source field, until
   they are renewed or edited.
