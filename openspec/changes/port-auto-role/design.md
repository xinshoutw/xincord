## Context

v3's AutoRole (`Plugins/AutoRole`, 3 Kotlin files, 81 lines) has no commands, text, components
or storage. `Event` (`PluginEventConfigure`, a listener) reads `config.yaml` (`enabled`,
`guilds[].guild_id`, `guilds[].role_ids`, `ConfigSerializer.kt:6-24`) and forwards
`GuildMemberJoinEvent` to the `AutoRole` object when enabled (`Event.kt:28-31`). On its first use
the object maps each configured guild to the roles that `JDA.getRoleById` finds, across every
cached guild (`AutoRole.kt:9-12`); for a join in a tracked guild it calls
`guild.modifyMemberRoles(member, roles).queue()` (`AutoRole.kt:21-25`), which replaces the
member's whole role set in one request after JDA's client-side checks. v3's core always requested
the members intent (`BotLoader.kt:68-72`). The inventory is
`docs/porting/analysis/inventory/AutoRole.md`; its section 12 lists seven defects.

## Goals / Non-Goals

**Goals:** v3's behavior (configured guilds only, every join, bots included, v3's config shape and
validation); the seven defects fixed; the first listener and the first privileged intent in a
plugin, with test helpers that later ports reuse.

**Non-Goals:** waiting for membership screening, an audit log reason, removing roles when members
leave, per-guild commands to edit the config.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/auto_role/`: `__init__.py` (metadata and
  `setup`), `config.py` (the config model), `cog.py` (the listeners) and `config.yaml`. Entry point
  `AutoRole = "xincord.plugins.auto_role"`. No `lang/` and no `DEFAULT_LOCALE`: v3 had no text, so
  `setup` never calls `context.lang`.
- `INTENTS = discord.Intents(members=True)`: member joins need the privileged members intent. The
  core adds it to the bot's intents only when AutoRole (or another plugin that declares it) is
  enabled, and a hot load into a bot created without it is refused (core-plugin-loading).
- `DEPENDS` and `SOFT_DEPENDS` are empty; there are no component IDs (v3 had no components) and no
  storage (v3 kept only the config).
- The bundled `config.yaml` lists no guilds (`guilds: []`) and shows an example with placeholder
  IDs in a comment: v3's shipped the owner's real guild and role IDs, which never go into the
  repository.
- v3's `info.yaml` keys `author`, `coreApi` and `version` have no counterpart, as for _Example.
  v3 logged `AutoRole is disabled.` when off; a plugin missing from `plugins` is never imported.

### Config

`Config(Model)` has a required `guilds: tuple[GuildRoles, ...]`; `GuildRoles` has
`guild_id: PositiveInt` and `role_ids`, a tuple of integers with at least one item. These are v3's
rules (`require(guildId > 0)`, `require(roleIds.isNotEmpty())`, `guilds` without a default); role
IDs stay any integers, as v3's `List<Long>`, and one that names no role is skipped and logged at the
join. `Config.roles_by_guild()` maps each guild to its role IDs; a guild listed twice keeps its last
entry, as v3's `associate` did. v3's `enabled` is not part of the model: a v3 file logs
`unknown key enabled`. An invalid file raises `ConfigError` in `setup`, so the core disables only
AutoRole and logs the key.

### Join

`AutoRole.on_member_join` is a `commands.Cog.listener()`; discord.py adds it with the cog and
removes it when the plugin unloads. discord.py builds the member from the `GUILD_MEMBER_ADD`
payload, so the event needs no member cache (unlike `on_member_remove`). For a guild in the config,
the handler looks each configured role up in the joined guild (`guild.get_role`), once per distinct
ID, and adds the roles it can give one by one with `member.add_roles(role)`: discord.py's atomic
default sends `PUT /guilds/{guild}/members/{member}/roles/{role}`, which adds the role and leaves the
member's other roles alone. Joins in other guilds return at once. Bots and members who join again
get the roles, as in v3. No audit log reason is sent, as in v3.

### Skipped roles and logs

- A role ID that names no role in the joined guild (deleted, mistyped or another guild's) is
  skipped with a warning that names the ID and the guild.
- A role the bot cannot give is skipped with a warning that names the role and the guild.
  discord.py's `Role.is_assignable()` makes v3's client-side checks: not `@everyone`, not managed
  (bot, integration and booster roles), and below the bot's highest role unless the bot owns the
  guild.
- Without Manage Roles in the guild (`guild.me.guild_permissions.manage_roles`), the handler logs
  one warning that names the guild and sends nothing, as JDA refused before sending.
- A request that fails (`discord.HTTPException`, such as a role deleted since the lookup or a
  member who left) is logged with the role, the member and the error, and the remaining roles are
  still requested.

### Ready check

`AutoRole.check()` logs a warning for each configured guild the bot is not in, each one where it
lacks Manage Roles, and each configured role it cannot give there, with the same messages as the
join. It runs from an `on_ready` listener, and from `cog_load` when the bot is already ready (a
reload with `/xincord reload`, the console or SIGHUP), because `on_ready` does not fire again for
a reloaded plugin. `setup` runs before the gateway connects, and `--no-online` never connects, so
nothing is checked before the bot is ready. A guild that Discord reports unavailable (an outage)
is skipped: discord.py knows neither its roles nor the bot's member there (`guild.me` is None), and
no member can join it meanwhile.

### Tests

- `tests/plugins/auto_role/`: `test_plugin.py`, `test_config.py`, `test_join.py`,
  `test_skipped_roles.py` and `test_check.py`; `conftest.py` loads the plugin through its entry
  point with a config of two guilds and provides a fake guild.
- `tests/support/discord_fakes.py` gains `FakeRole` (`is_assignable()` answers its `assignable`
  field), `FakeGuild` (roles, `get_role`, and `me` with the bot's permissions) and `FakeMember`
  (records each `add_roles` call with its `atomic` flag in `requests`, or raises the error set for
  a role).
- `tests/support/plugin_fakes.py` gains `dispatch(bot, event, *args)`, which awaits the listeners
  that plugins added for an event (`bot.dispatch` needs the event loop of a logged-in bot), and
  `load_plugin(..., config=...)`, which writes the plugin's `config.yaml` before loading it.
- The ready check is tested by replacing `get_guild` (and `is_ready` for a load into a ready bot)
  on the offline bot.
- No golden data: v3 had no text, templates or component IDs.

### v3 behaved differently

- v3 behaved differently: `modifyMemberRoles(member, roles)` replaced the member's whole role set,
  so a role that another bot gave at the join was removed if it landed before AutoRole's request;
  each role is now added with its own request, which never removes a role.
- v3 behaved differently: roles were looked up across every cached guild (`JDA.getRoleById`), so
  another guild's role made JDA refuse the whole assignment; roles are now looked up in the joined
  guild, and another guild's role is skipped as missing.
- v3 behaved differently: one role the bot could not give (managed, `@everyone`, at or above its
  highest role) made JDA throw before sending, so the member got no role at all; such roles are
  now skipped one by one, with a warning, and the others are given.
- v3 behaved differently: roles were resolved once, at the first join after startup or a dashboard
  reload, so a role created later, or the roles of a guild the bot joined after that first join,
  were dropped until a reload; roles are now looked up at each join.
- v3 behaved differently: role IDs that resolved to no role were dropped without a log, and other
  problems surfaced only as JDA exceptions at a join; the plugin now logs them when the bot is
  ready and at each join.
- v3 behaved differently: `reload()` replaced the tracked guilds and the role map in two steps on
  the dashboard's thread, so a join in between could throw `NoSuchElementException`; a reload now
  replaces the whole cog.
- v3 behaved differently: the bundled `config.yaml` held real guild and role IDs; it now lists no
  guilds and shows placeholder IDs in a comment.
- v3 behaved differently: a config without `guilds`, or with an invalid entry, stopped the whole
  bot; it now disables only AutoRole (core-plugin-loading).
- v3 behaved differently: the members intent was always requested; it is now requested only when
  AutoRole or another plugin that needs it is enabled (core-plugin-loading).

Kept on purpose: bots and returning members get the roles; members who have not passed membership
screening get them at the join; a guild listed twice uses its last entry; role IDs are any
integers; `guilds` is required; no audit log reason.

## Risks / Trade-offs

- One request per role: a guild with six roles costs six requests per join instead of v3's one.
  discord.py waits out rate limits, so during a raid the roles arrive later. One request for all
  roles (`add_roles(*roles, atomic=False)`) would still drop a role given between the join and the
  request.
- With the members intent, discord.py also downloads every guild's members before `on_ready`
  (`chunk_guilds_at_startup` follows the intent) and caches them; v3 did not chunk. Memory is not a
  concern on the host (F2); the core can turn chunking off if startup gets slow.
- discord.py fires `on_ready` again after a reconnect that starts a new session, so the check's
  warnings repeat then.
- discord.py drops a `GUILD_MEMBER_ADD` for a guild it has not cached or a member it already
  caches, and a join that arrives while the plugin reloads, between the old cog's removal and the
  new one's addition, finds no listener; those members get no roles.
- If Discord refuses roles for members who have not passed membership screening, the per-role
  warnings show it.

## Manual smoke checklist

On a test guild, with a bot token, the Server Members intent allowed for the bot in the Discord
developer portal, and `plugins: [AutoRole]` in `config.yaml`:

1. Start the bot: the log lists `AutoRole` as loaded, `plugins/AutoRole/config.yaml` is the bundled
   default, and AutoRole logs nothing. Without the Server Members intent in the portal, startup
   stops with a privileged-intents error.
2. Configure the test guild with two roles below the bot's highest role, one above it and one
   unknown ID, then run `/xincord reload AutoRole`: warnings name the role above the bot and the
   unknown ID, and nothing names the two others.
3. Join with a second account: it gets the two roles, and the log warns about the two others.
4. Invite another bot: it gets the two roles too.
5. Remove Manage Roles from the bot and join again: no role, and one warning names the guild.
6. List a guild the bot is not in, restart: a warning names it. Invite the bot there and join with
   the second account: the roles are given without a reload.
7. Join a guild that the config does not list: no role is given.

## User-visible changes

Copy: the comments of the bundled `config.yaml`; operator log warnings (English).

1. Roles are added to the member's roles instead of replacing them (v3 removed a role that another
   bot gave at the join if it landed first).
2. A role that cannot be given (missing, another guild's, managed, `@everyone`, not below the bot's
   highest role) is skipped and logged, and the others are given (v3 gave none of them).
3. Roles created and guilds joined after startup work without a reload.
4. Configuration problems are logged when the bot is ready and at each join (v3 logged nothing
   for unknown role IDs).
5. The bundled `config.yaml` lists no guilds (v3 shipped real IDs, disabled).
