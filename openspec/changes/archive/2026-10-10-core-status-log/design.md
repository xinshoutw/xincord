## Context

v3 started `StatusChanger` and `ConsoleLogger` when the bot was ready (`ListenerManager.kt:26-27`)
and restarted both when the core settings were reloaded (`BotLoader.kt:140-148`).
`StatusChanger` looped over `TYPE;text;ms` strings on a thread; `InteractionLogger` printed a
console line per interaction; `ConsoleLogger` sent `Placeholder.get(user)` plus `cl_type` and
`cl_interaction_string` to every configured channel for slash commands, buttons and modals.
xincord's config already has `status.activities` (`type`, `text`, `seconds`, `url`) and
`interaction_log` targets (`guild_id`, `channel_id`, `types`, `format`).

## Goals / Non-Goals

**Goals:** v3's rotation, console lines and log channels, driven by the validated config and
refreshed by a full reload.

**Non-Goals:** logging more interaction kinds to channels than v3 did (selects, message commands);
per-guild filtering, which v3 did not have either.

## Decisions

- **Config in the bot.** `Bot(..., config=CoreConfig)` keeps the core config; `cli.run` passes the
  loaded one and a full `reload` replaces it before restarting the rotation.
- **Rotation.** `xincord.core.status.activity(entry)` converts an entry: `discord.Streaming` with
  the URL, `discord.CustomActivity` for custom, otherwise `discord.Activity` of the matching
  `discord.ActivityType`. `rotate(client, activities)` calls `change_presence` for each entry and
  sleeps its `seconds`, cycling; one entry is set once (discord.py sends the stored presence again
  when it reconnects), none returns at once. Exceptions from `change_presence` are logged and the
  loop continues. `on_ready` starts the task unless it runs (it fires again after reconnects),
  a full reload cancels and restarts it when the bot is ready, and `close` cancels it.
- **Console lines.** `xincord.core.interaction_log.describe(interaction)` returns the v3 kind and
  text: `CMD` with `interaction_values(...)["command_string"]` for slash commands, `MSG` with the
  name for message commands, `BTN`, `STRING` or `ENTITY` (component types 2, 3, 5-8) and `MODAL`
  with the custom ID. Autocomplete and user commands return None, as v3 never logged them.
  `Bot.on_interaction` logs `[KIND] name: text` after routing, so a plugin's handler is not delayed.
- **Log channels.** For `CMD`, `BTN` and `MODAL` (target types `command`, `button`, `modal`),
  `post(...)` renders each matching target's `format` with `actor_values(user, bot.user)` (v3's
  `Placeholder.get(user)` keys), `interaction_values(...)`, `cl_type` and
  `cl_interaction_string`, and sends it through `get_partial_messageable(channel_id,
  guild_id=...)`, so no channel cache is needed. Each send uses `AllowedMentions.none()`.
  `HTTPException` is logged per target. Targets are read from the bot's current config at each
  interaction, so a reload applies at once.

### v3 behaved differently

- v3 behaved differently: modal submissions were posted to log channels with `cl_type` `BTN`;
  xincord uses `MODAL`.
- v3 behaved differently: log channel messages used JDA's default mentions, so a format with
  `%user_mention%` pinged the user; xincord's log messages never ping.
- v3 behaved differently: an unknown activity type or a malformed entry was logged on every pass
  of the loop; xincord rejects it when the config loads (`core-config`).
- v3 behaved differently: a single activity was set again after every delay; xincord sets it once.

## Risks / Trade-offs

- Every interaction from every guild goes to every matching target, as in v3; busy bots should
  list few types.

## User-visible changes

1. Status rotation as in v3, from `status.activities` in the new config format; a single
   activity is set once.
2. Console lines as in v3: `[CMD] alice: /ping count: 2`, `[MSG] alice: Report`, `[BTN]`,
   `[STRING]`, `[ENTITY]` and `[MODAL]` with the custom ID.
3. Log channel lines use the configured `format` (default
   ``[%cl_type%] %user_name% `%cl_interaction_string%` ``); modals now show `MODAL` instead of
   `BTN`; the lines never ping; formats can also use the interaction keys (for example
   `%channel_name%`, `%command_name%`).
4. `/xincord reload`, SIGHUP and the console's `reload` apply new activities and log targets.
