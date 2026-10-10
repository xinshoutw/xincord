## Context

v3's WelcomeByeGuild (`Plugins/WelcomeByeGuild`, 7 Kotlin files, 633 lines) is a JDA listener.
`Event` (`PluginEventConfigure`) exports the en-US and zh-TW lang files, reads `config.yaml`
(`enabled` only, `ConfigSerializer.kt:5-8`) and, when enabled, registers four administrator guild
commands (`Register.kt:43-75`) and handles them and three gateway events (`Event.kt:61-80`).
`WelcomeByeGuild.kt` keeps each guild's `GuildSetting(welcomeChannelId, byeChannelId)` (`0` =
unbound) in `plugins/WelcomeByeGuild/data/<guildId>.json` through `JsonGuildFileManager`; the
commands bind and unbind the two channels and answer ephemerally (`:120-303`); a join posts the
`welcome` template and a removal the `bye` template in the bound text channel (`:78-118`); leaving a
guild deletes its file (`:55-57`). `WelcomeByeGuildSubstitutorFactory.kt` fills about 70 `wbg@`
placeholders. The inventory is `docs/porting/analysis/inventory/WelcomeByeGuild.md`; its section 12
lists eight probable bugs and the behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's commands, replies, welcome and bye messages and placeholders; durable per-guild
bindings without v3's data-loss paths; replies in every kind of channel.

**Non-Goals:** importing v3's data files (deferred, Resolution 3); a bind-time check of the bot's
permissions; per-guild templates or locales; new commands.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/welcome_bye_guild/`: `__init__.py` (metadata and
  `setup`), `cog.py` (commands, handlers and listeners), `store.py` (the bindings in the store),
  `values.py` (the `wbg@` placeholders and the text-channel checks) and `lang/`. Entry point
  `WelcomeByeGuild = "xincord.plugins.welcome_bye_guild"`.
- `INTENTS = discord.Intents(members=True)`: member joins and removals need the privileged members
  intent, which v3's core always requested (inventory section 10). Guilds and channels come from
  discord.py's default intents. `DEPENDS` and `SOFT_DEPENDS` are empty; `DEFAULT_LOCALE = "zh-TW"`.
  No component IDs: v3 had no components, and its `welcome-bye@` prefix was unused.
- No `config.yaml`, and `setup` never calls `context.config`: v3's only key was `enabled`, which the
  core's `plugins` list replaces.
- `lang/` holds v3's 28 files: `register.yaml` and the 13 message templates (`welcome`, `bye`,
  `guild-only`, `no-permission`, `invalid-channel` and the eight bind and unbind replies) per locale,
  with final newlines added (the zh-TW `register.yaml` and the en-US `welcome.yaml` had none) and
  two zh-TW typos corrected: `welcome`'s last line read "不坊" for "不妨", and `bye`'s description
  "但願我們會能未來的道路相見..." becomes "但願我們能在未來的道路上相見...".

### Storage (`store.py`)

- The core store's key-value table, namespace `WelcomeByeGuild` (the plugin's name), key = the
  guild ID in decimal, value = v3's `data/<guildId>.json` document unchanged:
  `{"welcomeChannelId": <int>, "byeChannelId": <int>}`, `0` for an unbound channel. A missing
  document or field reads as `0` and other fields are ignored (Moshi's defaults), so a future
  migration (B11) can copy v3's files as they are.
- `Bindings(welcome, bye)` is a frozen dataclass. `read(store, guild_id)` never writes;
  `set_channel(store, guild_id, kind, channel_id)` reads, writes only when the channel changes and
  returns the bindings afterwards and the previous channel, under `store.lock("WelcomeByeGuild:<id>")`
  because discord.py runs handlers concurrently (v3's JDA thread was single); `forget` deletes a
  guild's document and `guild_ids` lists the stored guilds.
- Binding and unbinding are one setter: a bind is "already" when the previous channel is the new
  one, and an unbind (`0`) is "empty" when the previous channel was `0`; neither writes.

### Commands (`cog.py`)

- `WelcomeByeGuild.command(name)` builds each of v3's four commands from the `COMMANDS` table with
  `app_commands.Command`: base names and descriptions from `Register.kt:44-71`, the names,
  descriptions and option texts of `register.yaml` through `lang.command` (YAML keys such as
  `welcome_channel_bind.options.channel.description`), and
  `app_commands.default_permissions(administrator=True)`. Guild commands, as in v3. `setup` adds
  them in v3's order.
- The bind commands share the callback `bind_channel(interaction, channel=None)` and the unbind
  commands `unbind_channel(interaction)`; each reads its kind (`welcome` or `bye`) from
  `interaction.command.name` in `COMMANDS`, as SimpleCommand's commands share one callback.
- The `channel` option is `app_commands.Transform[AppCommandChannel, TextChannelOption]`: a
  `Transformer` whose `channel_types` is `[ChannelType.text]`, so Discord offers text channels only,
  as v3's `setChannelTypes(ChannelType.TEXT)`. discord.py's `discord.TextChannel` annotation would
  also offer announcement channels and needs the channel in the cache; the transformer passes the
  `AppCommandChannel` that Discord resolved.
- Before a handler runs, the command tree has deferred the response ephemerally, as v3's core did.
  `_reply` renders the template in `interaction.guild_locale` (v3's `event.guild.locale`), else the
  user's locale, falls back per file to zh-TW, and edits the deferred response with the content,
  embeds, view and files.

### Handlers

- Access, in v3's order: no guild (`interaction.guild is None`, which discord.py never reports for a
  guild command) replies `guild-only`; a user without Administrator replies `no-permission`. The
  check reads `interaction.permissions`, the permissions Discord resolved for the member: the guild
  owner and members with Administrator have every permission there, and Administrator cannot be set
  per channel, so it matches JDA's `member.hasPermission(ADMINISTRATOR)`. Both replies get
  `placeholder_values(interaction)`.
- Bind: the target is the option's channel when given, else `interaction.channel`, kept only if its
  type is `ChannelType.text` (not announcement channels, threads, voice or stage channels, as JDA's
  `ChannelType.TEXT`); otherwise `invalid-channel`. Then `set_channel` and `<kind>-bind-already` or
  `<kind>-bind-success`.
- Unbind: `set_channel(..., 0)`, then `<kind>-unbind-empty` or `<kind>-unbind-success` with the
  previous channel.

### Placeholders (`values.py`)

- `command_values(interaction, guild, bindings, selected=None, old_channel_id=0)` is v3's
  `forCommand`: `placeholder_values(interaction)` (v3's `Placeholder.get(event)`, moved into the
  core by this change), then with the prefix `wbg@` `guild_values`, `user_values`,
  `member_values` (when the user is a member), `event_values("command")`, `channel_values` of the
  chosen channel, `operator_id`, `operator_name` and `operator_mention`, the bound channels and the
  previous channel.
- `member_event_values(bot, user, guild, bindings, event_type)` is v3's `forMemberEvent`:
  `actor_values(user, bot)` (v3's `Placeholder.get(member)` or `Placeholder.get(user)`), then
  `guild_values`, `user_values`, `member_values` when `user` is a member, `event_values` (`join` or
  `leave`) and the bound channels.
- A bound or previous channel gives `<base>_id` (the stored ID, `0` when unbound) and
  `<base>_mention` (`<#id>`, `-` when unbound) from the stored ID, and `<base>_name` and
  `<base>_type` from the guild's cached channel when it is a text channel, else `-` (v3's
  `getTextChannelById`). The bound channels add `<kind>_channel_is_set` (`true` or `false`).
- `text_channel(channel)` returns a channel whose type is `ChannelType.text`, checked against a
  `runtime_checkable` Protocol so that discord.py's channels, `AppCommandChannel` and test fakes
  all pass; `postable(channel)` also requires `send`.

### Joins and removals

- `on_member_join(member)`: read the guild's bindings; when the welcome channel is set and
  `guild.get_channel` returns a text channel, render `welcome` in `guild.preferred_locale` and send
  the whole message (content, embeds, view and files), as v3's `sendMessage(...)`. No bot filter,
  as in v3. A `discord.HTTPException` is logged as a warning that names the plugin, the guild and
  the channel (v3: JDA logged the exception).
- `on_raw_member_remove(payload)`: discord.py's `on_member_remove` fires only for cached members, so
  the raw event covers leaves, kicks and bans as JDA's `GuildMemberRemoveEvent` did. The guild comes
  from `bot.get_guild`; the user is a `Member` when discord.py had it cached. The bot's own removal
  is ignored, as JDA did. Then the same as a join with the bye channel and the `bye` template.
- discord.py counts the new member before `on_member_join`, as JDA did, so
  `%wbg@guild_member_count%` includes them.

### Forgetting guilds

- `on_guild_remove(guild)` deletes the guild's document, as v3's `GuildLeaveEvent` handler did.
  discord.py fires it when the bot leaves or is removed, not during an outage
  (`on_guild_unavailable`).
- `forget_left_guilds()` runs from `on_ready` and from `cog_load` when the bot is already ready (a
  load or reload into a running bot gets no `on_ready`): it deletes the documents of guilds that
  `bot.get_guild` does not know and logs each one. At that point discord.py holds every guild of
  the READY payload, unavailable ones included, so only guilds the bot left are deleted: while it
  was offline, or while the plugin was not enabled.

### Core: `placeholder_values`

`xincord.core.placeholders.placeholder_values(interaction)` returns `actor_values(interaction.user,
bot) | interaction_values(interaction)`, or the interaction values alone while
`interaction.client.user` is None. It reads the interaction through the Protocols `ClientLike` and
`EventLike(InteractionLike)` that `discord.Interaction` satisfies. _Example's copy is removed and its
cog imports the core function. BotInfo's and SimpleCommand's `_bot_values` stay: this plugin does
not need v3's bare global keys.

A check of the commands through discord.py's own invocation path (a real `discord.Interaction` from
a gateway payload, in a guild that discord.py had not cached) showed that `interaction_values`
failed in a thread: `getattr(thread, "category", None)` lets discord.py's `ClientException` ("Parent
channel not found") through when the parent channel is not cached. `interaction_values` now treats
that thread as having no category, so `channel_category_name` is absent and the command still
answers. With the guilds intent the parent is normally cached, so this affects guilds discord.py
has not cached, such as an unavailable one.

### Tests

- `tests/plugins/welcome_bye_guild/`: `test_plugin.py`, `test_store.py`, `test_values.py`,
  `test_bind.py`, `test_unbind.py`, `test_access.py`, `test_join.py`, `test_leave.py`,
  `test_forget.py` and `test_command.py`; `conftest.py` loads the plugin through its entry point.
  `tests/core/test_placeholders_events.py` covers `placeholder_values`.
- `tests/fixtures/plugins/welcome_bye_guild/golden.yaml`: v3's replies per locale, the welcome and
  bye embeds per locale and the four translated command payloads.
- `discord_fakes` gains what the plugin reads: `FakeInteraction.guild`, `guild_locale` and
  `permissions`; `FakeGuild`'s placeholder attributes, `channels` and `get_channel`;
  `FakeChannel.type` and `mention`; `FakeMember`'s user and member attributes; `FakeRole.position`,
  `mention` and `is_default`.

### v3 behaved differently

- v3 behaved differently: every command reply built `Placeholder.get(event)`, which called
  `asTextChannel()` and threw in threads, voice channel chats, stage and announcement channels, so
  the command got no reply; a bind with the `channel` option there was saved before the reply
  failed, and `invalid-channel` could never be delivered (inventory 3 and 12.1). The commands now
  answer in every channel.
- v3 behaved differently: values were expanded again, so `%...%` in a member's, guild's or
  channel's name was substituted, and a self-reference stopped the welcome or bye message (12.2);
  values are inserted as written (core-placeholders).
- v3 behaved differently: placeholders were cached per user across events and plugins, and the bye
  message used the user cache, so the `wbg@member_*` keys and v3's unprefixed member keys never
  rendered in it (12.3); each render builds its own values, and the bye message has the member keys
  when discord.py still knew the member.
- v3 behaved differently: `invalid-channel`, `*-bind-already` and `*-unbind-empty` created the
  guild's data file (12.4); nothing is written unless a channel changes.
- v3 behaved differently: a corrupt data file was reset to the defaults, a non-numeric file name
  stopped the bot, and writes were not atomic (12.5); the bindings are SQLite rows written in
  transactions.
- v3 behaved differently: the data of a guild was deleted only on a `GuildLeaveEvent` received while
  the plugin was enabled, so guilds the bot left while offline or disabled kept their files (12.7);
  their bindings are deleted when the bot is ready.
- v3 behaved differently: `guild-only` was rendered with the global placeholders only; it gets the
  interaction's placeholders like `no-permission` (the commands are guild commands, so it does not
  show).
- v3 behaved differently: the commands needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers them.
- v3 behaved differently: two zh-TW texts had typos; they are corrected in the bundled files.

Kept on purpose: the double Administrator gate (default permission and runtime check); replies and
messages in the guild's locale (most non-Community guilds get en-US), with zh-TW for other locales;
no bot filter on joins; one channel allowed for both kinds; silence when a channel is unbound,
deleted or not a text channel; embed URLs that do not start with `http` dropped (the core's
templates). v3's issue 12.6 (no check that the bot can post in the bound channel) is kept: the
permissions a message needs depend on the operator's template and can change after the bind, so a
failed welcome or bye is logged instead, and a bind-time check is left to the owner. Issue 12.8 (no
upload of an empty command list) is fixed by the core.

### Inventory audit

Filled in by task 10.3.

## Risks / Trade-offs

- Existing deployments lose their bindings at cutover until the channels are bound again or a
  migration copies `plugins/WelcomeByeGuild/data/*.json`; the stored document keeps v3's shape for
  that.
- A raid posts one message per join, as in v3; discord.py's rate limiter queues them.
- `forget_left_guilds` trusts discord.py's guild list at `on_ready`. Sharding would break that
  assumption; xincord runs one shard.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [WelcomeByeGuild]` in `config.yaml` and the Server
Members intent allowed for the bot in the developer portal:

1. Start the bot: the log lists `WelcomeByeGuild` as loaded; `plugins/WelcomeByeGuild/lang/en-US/`
   and `lang/zh-TW/` hold `register.yaml` and the 13 templates, and no
   `plugins/WelcomeByeGuild/config.yaml` exists.
2. As an administrator with an en-US client, the four commands are listed with their en-US
   descriptions; the `channel` option of the bind commands lists text channels only.
3. As a member without Administrator, the commands are not listed; after granting one in the
   server's integration settings, running it replies `no-permission`.
4. In a text channel, run `/welcome-channel-bind` without the option: the ephemeral reply names the
   channel; run it again: `already`. Run `/bye-channel-bind channel:#other`: the reply names
   `#other`.
5. In a thread, run `/welcome-channel-bind` without the option: `invalid-channel`; with the option:
   the channel is bound.
6. Join with a second account: the welcome channel shows the green embed with the guild's name and
   icon, the account's name and avatar, the member count and the rules channel.
7. Leave with it, then rejoin and kick it, then ban it: the bye channel shows the red embed each
   time.
8. Turn on Community and set the server's primary language to Chinese (Taiwan): replies, welcome
   and bye messages are in zh-TW.
9. Deny the bot Send Messages in the welcome channel and join again: no message, and the log has a
   warning that names the guild and the channel.
10. Run `/welcome-channel-unbind`: the reply mentions the old channel; run it again: `empty`. Delete
    the bye channel and run `/bye-channel-unbind`: the reply still mentions it.
11. Bind a channel, kick the bot and invite it again: `/welcome-channel-unbind` replies `empty`.
12. Bind a channel, stop the bot, remove it from the guild, start it: the log notes the deleted
    bindings of that guild.

## User-visible changes

Copy: the corrected zh-TW `welcome` and `bye` texts; no new text.

1. The commands answer in threads, voice channel chats, stage and announcement channels (v3: no
   reply); without the `channel` option there, the reply is `invalid-channel`.
2. `%...%` in member, guild and channel names is shown as written (v3 expanded it).
3. The bye message can use the `wbg@member_*` keys and v3's unprefixed member keys when discord.py
   still knew the member (v3: never).
4. Bindings live in the SQLite store; v3's `plugins/WelcomeByeGuild/data/*.json` files are not read,
   so the channels must be bound again after moving from v3.
5. Bindings of guilds the bot left while offline or while the plugin was off are deleted when the
   bot is ready.
6. A welcome or bye message that Discord refuses logs a warning naming the guild and the channel.
7. The commands always answer (v3 needed the core's auto-defer switch).
8. No `plugins/WelcomeByeGuild/config.yaml`: the core's `plugins` list replaces v3's `enabled`.
9. The zh-TW welcome and bye texts have their typos corrected in the bundled files; existing
   `plugins/WelcomeByeGuild/lang/` files keep v3's text.
