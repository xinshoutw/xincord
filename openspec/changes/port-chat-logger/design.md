## Context

v3's ChatLogger (`Plugins/ChatLogger`, 11 Kotlin files, 995 lines) has two halves. The settings
half is VoiceLogger's code, copied: `ChannelData` (`ChannelData.kt:8-78`) computes a listen
channel's detected channels, `JsonManager` (`JsonManager.kt:17-118`) keeps every guild's listen
channel settings in `plugins/ChatLogger/setting/<guildId>.json`, and `ChatLogger.kt:53-117,229-295,
320-375` holds the command, the menu's buttons and select menus (`chat-logger@a:<action>`) and the
posts. The message half is ChatLogger's own: `DbManager` (`DbManager.kt:16-188`) stores every guild
message's text in `plugins/ChatLogger/data/<guildId>.db`, one table per channel, and
`ChatLogger.kt:119-226,298-317` turns `MessageUpdateEvent` and `MessageDeleteEvent` into embeds for
the listen channels that detect the message's channel. `Event` (`Event.kt:23-131`) forwards the JDA
events when `enabled` is true. The inventory is `docs/porting/analysis/inventory/ChatLogger.md`; its
section 12 lists 17 bugs and the behavior to preserve.

## Goals / Non-Goals

**Goals:** one implementation of the listen channel code for VoiceLogger and ChatLogger; v3's
command, menu, buttons, select menus and settings model; v3's two log templates for edits and
deletions in the guild's locale; v3's settings document in the store; a message log bounded in time,
in the store that decision B8 chose.

**Non-Goals:** migrating v3's settings files and message databases (B11); removing single list
entries; storing attachments, stickers or reactions; a purge command; the Web Dashboard (B13).

## Decisions

### Shared listen channels

v3 copied `ChannelData`, `JsonManager`, the settings menu and `sendListenChannel` between VoiceLogger
and ChatLogger. They move from `xincord.plugins.voice_logger` into
`packages/xincord-plugins/src/xincord/plugins/listen_channels/`, a package without an entry point
that both plugins import; neither plugin needs the other:

- `settings.py` (pure, VoiceLogger's): `Setting`, `detects`, `targets`, `list_text` and `units`
  (lengths in UTF-16 code units).
- `store.py`: `ListenSettings(store, namespace)`, VoiceLogger's store functions as methods of an
  object bound to the plugin's namespace (`VoiceLogger`, `ChatLogger`): `read_settings`,
  `read_setting`, `toggle`, `add_channels`, `remove`, `forget`, `guild_ids` and `prune`, with
  `DataError` and `Kind`. The documents, the locks (`<namespace>:<guild ID>`) and the log lines
  (which name the namespace) are VoiceLogger's.
- `menu.py`: `Menu(lang, templates, ids, key, template)`, what differs between the plugins' menus
  (the values' prefix `vl` or `cl` and the menu's template name), and `ListenChannels(bot,
  settings, menu)`: `show` (the command's menu), `handle` (the components), `post` (a log to the
  listen channels) and `check_guilds` (left guilds and deleted list entries at READY), moved from
  VoiceLogger's cog as they were.

Each plugin's cog keeps its command group (built in its own module, so that unloading the plugin
removes it), a `show_settings` callback and a `handle` route that call `ListenChannels`, and its
listeners. discord.py drops a plugin's own modules when it unloads it; the shared package stays
imported, holds no state, and its classes stay the same across reloads. VoiceLogger's tests keep
their assertions; their imports and setup calls follow the moved code.

`detects(setting, *ids)` takes the channel's ID and the IDs that contain it (None when there is
none): VoiceLogger passes a voice channel and its category, ChatLogger a channel and its category
or a thread, its parent channel and that channel's category. In the allow mode one of them must be
allowed; in the block mode none may be blocked. `targets(settings, places)` takes such tuples.

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/chat_logger/`: `__init__.py` (metadata and
  `setup`), `config.py`, `text.py` (pure: a message's text and the texts that fit a field),
  `logs.py` (pure: what a log shows of a channel and an author), `messages.py` (the stored
  messages), `cog.py` (the command, the listeners, the retention loop and the checks) and `lang/`.
  Entry point `ChatLogger = "xincord.plugins.chat_logger"`.
- `DEPENDS` and `SOFT_DEPENDS` are empty: v3's `SQLiteAPI` dependency is the core store (B12).
  `INTENTS = discord.Intents(guild_messages=True, message_content=True)`, v3's `GUILD_MESSAGES` and
  `MESSAGE_CONTENT`. The second is privileged: Discord refuses the connection (close code 4014) when
  the developer portal does not allow it, and without it messages arrive without their text. The
  members intent is not needed: messages carry their author, and the author of a deletion is
  fetched. `DEFAULT_LOCALE = "zh-TW"`, v3's default and fallback.
- `lang/` holds v3's 16 files (`register.yaml`, `placeholder.yaml` and `message/{chat-logger@setting,
  delete,modify-allow,modify-block,on-msg-delete,on-msg-update}.yaml` per locale), each with a final
  newline (six files had none). The texts are v3's.

### Config

`config.py`: `Config(Model)` with `log_all: bool = True` (v3's key and default) and
`retention_days: Annotated[int, Field(ge=1, le=3650)] = 30`. v3's `enabled` only warns. The bundled
`config.yaml` explains both keys and says that the plugin needs the Message Content intent.

### Storage of the message log (decision B8)

B8 left open whether ChatLogger's message log gets its own SQLite file. It does not: the log is a
plugin table in the shared store, `data/xincord.db`, through `Store.run`, as B8's single store
(`SQLite ... unified storage`) and the store's `<plugin>_<table>` convention intend.

- Data volume (inventory 8.1): one row per guild message, with the latest text only: about 100 to
  300 bytes with the IDs, the text and the index, and at most about 10 KB (Discord's 4000-character
  content and 6000-character embeds). v3 kept every row forever; `retention_days` now bounds the
  log to the messages of its window, about 10 MB for a guild with 2000 messages a day over 30 days.
  F1 calls the data set small, and F2 says that disk and CPU are no concern.
- Access patterns (inventory 5 and 8.1): one insert per message on the gateway path; a lookup and
  an update by message ID per edit; a lookup and a deletion by message ID per deletion; no scans.
  New: an hourly deletion of the messages older than the retention, a range of the primary key, and
  rare deletions by guild. Every operation is one short transaction, so the store's single worker
  thread, which also serves the other plugins, stays free: the hourly deletion runs in batches of
  1000 rows.
- One file keeps one volume and one backup (B16) and needs no core API; v3's per-guild files and
  per-channel tables become one table.
- Alternative: an own file, `data/ChatLogger.db`, with its own connection and thread (and WAL), so
  that the log's writes never wait for, or delay, the other plugins' store calls, and the operator
  can purge or back up the log alone. It needs a core API for the plugin's data path. Worth it if a
  guild's message rate ever makes the shared worker thread a bottleneck.

`messages.py`: `MessageLog(store)` over the table

```sql
CREATE TABLE IF NOT EXISTS ChatLogger_messages (
    message_id INTEGER PRIMARY KEY,  -- the snowflake: unique, and its time drives the retention
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,         -- the author at creation, a webhook's ID for its messages
    message TEXT NOT NULL,            -- the latest text
    update_count INTEGER NOT NULL     -- how often the text changed
);
CREATE INDEX IF NOT EXISTS ChatLogger_messages_guild ON ChatLogger_messages (guild_id);
```

v3's column names stay, so that the deferred migration (B11) can copy v3's rows (the guild from the
file name, the channel from the table name). `create` runs in `setup`; `add` inserts a message
once (`INSERT OR IGNORE`: a replayed event keeps the first row); `edit(message_id, text)` reads,
compares and updates in one transaction and returns the text before, the author and the new count,
or None when the message is not stored or its text did not change; `pop(message_id)` and
`pop_all(message_ids)` return the stored messages, oldest first, and delete them in one
transaction; `prune(before)` deletes the messages whose IDs are below a snowflake, 1000 at a time;
`forget(guild_id)` and `guild_ids()` serve left guilds.

### Command, menu and components

`ChatLogger.command()` builds v3's group with `app_commands.Group(name=..., description=...,
default_permissions=discord.Permissions(administrator=True))` in `cog.py` and the subcommand
`setting` with the cog's bound method `show_settings` as callback, from `register.yaml`
(`chat-logger.name`, `.description`, `.subcommands.setting.name` and `.description`; v3 looked them
up as `chatLogger.*`) with v3's base texts from `Register.kt`. The tree defers it ephemerally, as
v3's core did; there is no runtime permission check, as in v3.

`IDS = ComponentIds("chat_logger", ("action",), legacy_prefix="chat-logger@")`, v3's only field and
v3's `component_prefix`; `setup` routes it to the cog's `handle`. The menu, the buttons and the
select menus behave as VoiceLogger's (`ListenChannels.show` and `handle`) with the `cl_` values and
the template `chat-logger@setting`; the select menus offer v3's ten channel types.

### Storing messages

`on_message` stores each guild message that the bot did not send, other bots' and webhooks'
included (v3's filter), with `log_all` true; with `log_all` false, only when a listen channel of the
guild detects its channel. The channel (`logs.Place.of`) is read before anything awaits:
discord.py runs listeners as tasks and later events change its cache meanwhile.

`text.message_text(content, embeds)`: the content, then each rich embed's author name and title
(one line each), its description and its fields (name and value on two lines), the parts separated
by blank lines and the empty ones left out. Embeds of other types (link previews, images, videos)
are left out: Discord adds them to a message after it is sent, from the links in its content, so
they would count as edits; bots' and webhooks' embeds are rich.

### Edits

`on_raw_message_edit` gets every `MESSAGE_UPDATE`, cached or not (JDA fired `MessageUpdateEvent`
regardless of its cache; discord.py's `on_message_edit` needs the cached message). discord.py builds
the updated `Message` from the payload (`payload.message`, since 2.5). For a guild message that the
bot did not send, the listener reads the place, computes the text and calls `MessageLog.edit`;
nothing happens when the message is not stored or the text did not change (a pin, a link preview,
suppressed embeds, a thread started from the message). Then the guild's targets; without one it
stops. The values: the author's (`logs.author_values`: v3's `Placeholder.get(member)`, the member
from the payload; a webhook's user values with `-` for the member keys and no member avatar),
`cl_msg_after_url` (`https://discord.com/channels/<guild>/<channel>/<message>`, JDA's `jumpUrl`),
`cl_channel_mention`, `cl_category_mention` (the category of the channel, or of a thread's parent
channel, or `-`), `cl_change_count`, `cl_msg_before` and `cl_msg_after`.

### Deletions

`on_raw_message_delete` and `on_raw_bulk_message_delete` take the stored messages out of the store
(`pop`, `pop_all`), then post `on-msg-delete` for each, oldest first, when a listen channel detects
the channel. The author is fetched as the guild's member (`guild.fetch_member`, v3's
`retrieveMemberById`), once per author in a bulk deletion. Without a member (the author left, a
webhook, a refusal), the values are the stored ID's mention and `-`, with no avatar URL, so the
templates show no thumbnail; v3 posted nothing.

### Texts in the logs

`text.fit(text)` keeps `cl_msg_before` and `cl_msg_after` within an embed field: a text longer than
1024 UTF-16 code units (JDA's count) is cut to the characters that fit before `...`. The core renders
each value once, so `%...%` in a message is shown as written.

### Posts

`ListenChannels.post` (VoiceLogger's `_post`): the template in `guild.preferred_locale` (falling
back to zh-TW), rendered again for each listen channel and sent through
`bot.get_partial_messageable(id, guild_id=...)`; a `discord.NotFound` forgets the listen channel's
settings, another `discord.HTTPException` is a warning, and the other channels still get the log.

### Retention

`cog_load` starts one task that waits for READY, then deletes the messages older than
`retention_days` (`MessageLog.prune(time_snowflake(now - retention))`) and sleeps an hour, again and
again; `cog_unload` cancels and awaits it. A failed deletion (`sqlite3.Error`) is logged with its
traceback and the loop goes on. `--no-online` never becomes ready, so it deletes nothing. The sleep
is the cog's `sleep` attribute, which tests replace.

### Left guilds and checks at READY

`on_guild_remove` forgets the guild's settings and, with `log_all` false, its stored messages (v3's
intent; its deletion used the wrong key). `on_ready`, and `cog_load` in a ready bot, run
`ListenChannels.check_guilds()` (VoiceLogger's: settings of guilds the bot left are deleted, deleted
channels are dropped from the lists of available guilds) and, with `log_all` false, delete the
stored messages of every guild the bot is no longer in, as v3's start did with their files. With
`log_all` true the messages of left guilds stay until the retention removes them, as v3 kept them.

### Tests

- `tests/plugins/chat_logger/`: `test_plugin.py`, `test_config.py`, `test_detect.py`,
  `test_menu.py`, `test_components.py`, `test_command.py`, `test_text.py`, `test_messages.py`,
  `test_store_messages.py` (the listener), `test_edit.py`, `test_delete.py`, `test_post.py`,
  `test_retention.py`, `test_forget.py` and `test_check.py`; `conftest.py` loads the plugin, records
  REST requests with `FakeRest` (autouse), gives the bot its user (autouse), stands for READY with
  `plugin_fakes.Ready` (autouse: the retention loop waits for it), sends the posts to fake channels
  through `get_partial_messageable` and finds the cog with `cast`.
- Messages, edits and deletions reach the listeners as discord.py builds them: `discord.Message`
  objects from gateway payloads with `bot._connection` (a guild added with `_add_guild_from_data`),
  and the raw events from `plugin_fakes.gateway`.
- `tests/fixtures/plugins/chat_logger/golden.yaml`: v3's embeds per locale for the menu, `delete`,
  the select menus and the two logs, and the translated command payload.

### v3 behaved differently

- v3 behaved differently: `JsonManager`'s first use threw a `ConcurrentModificationException` when a
  settings file belonged to a guild the bot had left or held a deleted listen channel, and every
  later use threw `NoClassDefFoundError`, so the plugin forwarded nothing until a restart, or never
  again; settings are read from the store at each use.
- v3 behaved differently: a listen channel's first selection was saved in the block mode while the
  menu showed the allow mode, so after a restart the channel logged every channel; new entries keep
  the allow mode.
- v3 behaved differently: "Delete" deleted the guild's whole settings file, so every other listen
  channel of the guild lost its settings at the next restart; it deletes the channel's settings
  only.
- v3 behaved differently: `log_all: false` froze the logged channels to those that already had a
  table and never consulted the settings; it stores the messages of the channels that a listen
  channel detects.
- v3 behaved differently: with `log_all: false`, the startup tried to drop the tables of deleted
  channels with an unquoted numeric name, which always failed; there are no per-channel tables, and
  the messages of deleted channels leave with the retention.
- v3 behaved differently: leaving a guild with `log_all: false` deleted nothing (the database key
  lacked its `CL:` prefix); the guild's stored messages are deleted.
- v3 behaved differently: the database connections were never closed (the keys were listen channel
  IDs); the log lives in the core store, which the core closes.
- v3 behaved differently: the deletion of a message whose author had left, or of a webhook's
  message, was not logged (the fallback was dead code); it is logged with the stored author's
  mention and `-`.
- v3 behaved differently: a message or a list longer than an embed field's 1024 characters made the
  render throw, so the log was lost, or the menu never opened again; texts are cut and lists end
  with `...`.
- v3 behaved differently: edits and deletions in threads were never forwarded
  (`asStandardGuildChannel()` threw), and the block mode never detected threads; threads are logged,
  detected through their parent channel and its category or by their own ID.
- v3 behaved differently: a log stopped at the first listen channel that no longer existed, removed
  the wrong cache entry, and threw for listen channels that were neither text nor voice channels;
  each listen channel gets the log on its own, a deleted one is forgotten and a refusing one is a
  warning.
- v3 behaved differently: message texts went through the substitutor recursively, so `%bot_id%` in
  a message was expanded, and a message holding `%cl_msg_after%` or `%cl_msg_before%` made the log
  throw, a way to edit or delete without a log; texts are shown as written.
- v3 behaved differently: `cl_category_mention` was set only for channels with a category, in the
  member's shared substitutor (the global one for webhooks), so other channels showed an earlier
  event's category or the placeholder; it shows `-`, and each log renders with its own values.
- v3 behaved differently: a message with embeds was stored without its content, and a missing embed
  title or description was stored as `null`; the text is the content and the rich embeds, without
  missing parts.
- v3 behaved differently: `/chat-logger setting` gave no reply outside plain text channels
  (`Placeholder.get(event)` threw); the menu works in every channel, which can then be a listen
  channel.
- v3 behaved differently: bulk deletions (a purge) were never logged (the core disabled JDA's
  splitting of them and the plugin ignored `MessageBulkDeleteEvent`); each stored message of one is
  logged.
- v3 behaved differently: a settings or database file whose name was not a number made the plugin's
  start-up throw; the store has no such files, and a stored key that is not a guild ID is skipped
  with a warning.
- v3 behaved differently: every `MESSAGE_UPDATE` with an author counted as an edit and was logged,
  link previews included, whose embed text replaced the stored content; only a change of the text
  counts.
- v3 behaved differently: stored texts were kept forever, deleted messages' included; they are kept
  for `retention_days` days (30 by default), and a deleted message's text is removed once its
  deletion is handled.
- v3 behaved differently: an edit by a webhook rendered with the global substitutor, so the embed
  showed the placeholders themselves; it shows the webhook's mention and `-` for the member keys.
- v3 behaved differently: an unknown select menu action threw; it gets no response, as unknown
  buttons did.
- v3 behaved differently: the command needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers it.
- v3 behaved differently: an unreadable settings file was replaced by `{}`, losing the guild's
  settings; an unreadable document stops the handling with an error and is never overwritten.

Kept on purpose: the bot's own messages are not stored, other bots' and webhooks' are; only the
latest text of a message is kept, with the count of its changes (the count after the edit in an
update, the edits so far in a deletion); messages sent before they could be stored are not logged
and not stored when edited; logs use the guild's locale and the menu the user's, with zh-TW as
fallback; the settings model (allow or block, add-only lists, categories expanded at each event,
the allow mode for channels without settings); "Delete" without a confirmation; the menu is
ephemeral and its buttons have no expiry; no permission check besides Discord's default; the
`ALLOW` and `BLOCK` literals; attachments, stickers and reactions are not stored; `log_all: true`
keeps the messages of a guild the bot left (until the retention).

### User-visible changes

- The plugin needs the Message Content intent allowed in the developer portal (v3 required it
  too); without it, Discord refuses the bot's connection.
- New config key `retention_days` (30 by default): edits and deletions of messages older than that
  are not logged (v3 kept every message forever).
- `log_all: false` stores the messages of the detected channels (v3: of the channels stored
  before).
- Edits and deletions in threads are logged; threads are detected through their channel.
- Bulk deletions are logged, one embed per stored message.
- Deletions by authors who left, and by webhooks, are logged with the author's mention and `-`.
- Updates that keep the text (pins, link previews) are no longer logged as edits; the text of a
  message with embeds keeps its content and loses `null`.
- Long texts are cut with `...` instead of losing the log; long lists end with `...`.
- A missing category shows `-`; texts are shown as written.
- The menu answers in every channel, and logs reach listen channels of every kind; a deleted
  listen channel is forgotten; a refusing one no longer stops the others.
- A listen channel's first selection keeps the allow mode; "Delete" deletes only that channel's
  settings.
- Settings of a guild the bot leaves are deleted at once; deleted channels are dropped from the
  lists when the bot is ready.
- v3's `plugins/ChatLogger/setting/*.json` and `data/*.db` are not read: listen channels must be set
  up again, and messages stored by v3 are not logged (the data migration is deferred, B11).

## Risks / Trade-offs

- Message content is stored for `retention_days` days in the shared database file; anyone with the
  file can read it. The default is 30 days.
- With `log_all: false`, the settings are read for every message, and a message that is deleted
  before its insert reached the store (the insert waits for that read) stays stored until the
  retention removes it.
- A purge of many detected messages posts one embed per message; Discord's rate limit spreads them
  over time (about one per second per listen channel).
- The message log shares the store's worker thread with the other plugins (see the storage
  decision); a guild with a very high message rate would delay their store calls.
- Edits are detected by comparing texts: an edit that only changes attachments, or a link preview's
  text, is not logged.
