## Context

v3's Ticket (`Plugins/Ticket`, 8 Kotlin files, 1583 lines) has three parts. The builder
(`StepManager.kt:17-332`, `StepData.kt:23-196`) keeps an in-memory draft per user, opened by
`/create-ticket` or `/add-ticket` (`Register.kt:29-43`), and drives it through an ephemeral message
with v3's screens, selects and modals, re-rendered through the slash command's hook; confirming
posts a panel or adds a button to an existing message. The runtime (`Ticket.kt:105-310`) answers a
panel button with a reason modal and opens a ticket channel with a control row; lock, unlock,
delete and save act on it (`Ticket.kt:148-376`), and save copies the channel's history into a
thread of another channel through a temporary webhook (`Ticket.kt:378-878`). Panels are a Moshi
document per guild in `plugins/Ticket/data/<guildId>.json`. `Event.kt:18-89` forwards JDA's events
when `enabled` is true. The inventory is `docs/porting/analysis/inventory/Ticket.md`; its section 12
lists 17 probable bugs, a security concern and the behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's commands, builder screens, modals, defaults, preview, panel, reason modal, ticket
channel (name, overwrites, opener), control row, delete and save checks, and archive (names,
order, forwarded fields, thread flattening, markers); v3's templates and IDs, so that v3's panels
and ticket channels keep working; v3's per-guild JSON documents in the store; every defect of the
inventory's section 12 fixed or recorded.

**Non-Goals:** reading v3's data files (the v3 data import); limits on open tickets, cooldowns or
confirmations (v3 had none); cleaning up panels whose message was deleted; clearing a selected
category or role list; archiving embeds, stickers, reactions or edits; the Web Dashboard (B13).

## Decisions

### Package and bundled files

`packages/xincord-plugins/src/xincord/plugins/ticket/`:

- `__init__.py`: `DEPENDS = ()`, `SOFT_DEPENDS = ()`, `INTENTS = discord.Intents.none()` (guild
  leaves need only discord.py's default guilds intent; members come with each interaction, and the
  history is read through REST), `DEFAULT_LOCALE = "zh-TW"`, and `setup`, which loads the lang
  files, the templates, the cog, the commands and the route. No `config.yaml`: v3's only key was
  `enabled`, which the core's `plugins` list replaces; an operator's v3 file is left unread.
- `model.py` (pure): `Draft` (v3's `StepData` and `DataContainer` together, frozen), `Entry` (v3's
  `DataContainer`), `parse_entry` / `entry_json` (v3's Moshi JSON), `DataError`, `parse_color`,
  `hex_color` and `STYLES`.
- `drafts.py` (pure): `defaults(texts)`, `submit(draft, sub_action, values)` (a modal's change or the
  error key), `select_roles`, `select_category`, `select_style`.
- `texts.py`: `Texts(lang, locale)`, the texts of `text.yaml` with `%tt@...%` values inserted as
  written, and `units` / `clip` / `chunks` (lengths in UTF-16 code units, as JDA counted them).
- `views.py`: what v3 built in code: `preview_embed`, `preview_button`, `panel_button`,
  `control_row` and `save_select`, each a stopped view or a component for the templates' models.
- `store.py`: `Panels(store)`: `entry`, `entries`, `add`, `forget` and `guild_ids`, writes under the
  guild's lock.
- `tickets.py`: `category_of`, `overwrites` (the ticket channel's map) and `opener` (its messages).
- `archive.py`: the archive engine over Protocols of the channels, messages, threads and webhook,
  with `thread_name`, `webhook_name`, `forwarded_name` and the markers.
- `ids.py`: `IDS`, which `cog.py` re-exports.
- `controls.py`: `ControlRow`, the cog's base: the texts of the replies and the control row's
  handlers (lock, unlock, delete, save and the save select), so that `cog.py` stays under 800 lines.
- `targets.py`: the message that `/add-ticket` adds a button to: `fetch`, `refusal`, `is_full`
  (its first row full or holding a select) and `unplace` (its earlier view back when the button's
  entry cannot be stored), also kept out of `cog.py` for its size.
- `cog.py`: the cog `Ticket`, the commands, `handle` and the other handlers, `on_guild_remove` and
  the READY check.
- `lang/<locale>/` with v3's `register.yaml`, `message/*.yaml` and `modal/*.yaml`, two of them fixed
  (below), and the new `text.yaml`. `confirm-add.yaml`, which v3 never used, ships unchanged.

v3's `register.yaml` files had CRLF line endings; the bundled ones have LF. The zh-TW
`modal/modify-btn-text.yaml` gets `sub_action: "modify-btn-text"` (v3: `modify-btn-content`, which
the handler did not know, B2), and `modal/press-ticket.yaml` gets its own locale's title in both
locales (v3 swapped them, B13). Operators' exported files keep v3's text; the handler takes
`modify-btn-content` as `modify-btn-text`.

### Texts

v3's texts written in Kotlin (`Ticket.kt`, `StepManager.kt`, `StepData.kt`) move to
`lang/<locale>/text.yaml`, read with `Lang.text("text.<key>", locale)`, because Python files hold
no CJK text: the replies and errors, the control row's labels, the save select's placeholder, the
archive's markers and the builder's defaults (reason title, author, icon URL, title, description,
button text and emoji). zh-TW holds v3's strings, the four that v3 wrote in English translated
(`Cannot found the message by id`, `This message is full of buttons`, `Cannot find a category with
the id`, `Either ButtonText or ButtonEmoji must be provided!`); en-US holds English, taking v3's
English ones and the English texts of v3's en-US modal placeholders for the defaults. Values are
`%tt@...%` placeholders rendered in one pass (`tt@channel`, `tt@thread`, `tt@error`,
`tt@message-id`, `tt@category-id`, `tt@owner`, `tt@name`, `tt@time`).

Replies to one user use `interaction.locale`; `Lang.text` and `Lang.template` fall back per key to
zh-TW, which is what v3 showed for a locale without lang files (its templates fell back to zh-TW
and its texts were Chinese), so only en-US users see a difference: English replies. Public texts,
the control row's labels and the archive's markers, use zh-TW, as v3. The builder's defaults follow
the administrator's locale.

### Storage

v3's `JsonGuildFileManager` file is one document per guild in the store's key-value table:
namespace `Ticket`, key the guild ID in decimal, value v3's JSON unchanged,
`{"<message ID>": [{"reasonTitle": "...", "adminIds": [<role ID>, ...], "categoryId": <ID>}, ...]}`,
the list index being the button's `btn_index`. Snowflakes are JSON integers (Python's `json` keeps
those above 2^53 exact).

- `parse_entry` follows Moshi's `KotlinJsonAdapterFactory` for v3's `DataContainer`, whose fields
  have no defaults: the three fields are required, `reasonTitle` text, `adminIds` a list of
  integers, `categoryId` an integer; booleans are not integers. Anything else raises `DataError`
  naming the guild and the message; unknown fields are ignored.
- Reads (`entry`, `entries`) write nothing; v3 created the guild's file when reading. A guild
  without a document has no panels.
- `add(guild, message, entry)` appends `entry_json(entry)` (v3's field order) to the message's list
  under `store.lock("Ticket:<guild ID>")` and returns the new index; the other messages' lists and
  the list's earlier entries are written back as they were read. A message's value that is not a
  list raises `DataError`, and nothing is written. An optional `place(index)` puts the button on
  its message under the lock and returns what takes it off again, which runs when the write fails.
- `forget(guild)` deletes the document under the same lock, as v3 deleted the file.

### Component IDs

`IDS = ComponentIds("ticket", ("action", "sub_action", "color_index", "user_id", "msg_id",
"btn_index"), legacy_prefix="ticket@", legacy_hex=("user_id",))`: v3's fields in v3's order (letters
`a` to `f`), `user_id` written in hex by v3 (`FieldType.LONG_HEX`), the others text. `setup` routes
them to `cog.handle`, which dispatches on the interaction's type, the component type and `action`,
as v3's `onButtonInteraction`, `onEntitySelectInteraction` and `onModalInteraction`:

| Interaction | `action` | Handler |
|---|---|---|
| button | `create` | the builder (`press`) |
| button | `press`, `lock`, `unlock`, `delete`, `save` | the panel and the control row |
| entity select (5 to 8) | `create` | the builder's selects |
| entity select | `save` | the archive (`sub_action` `select-channel`) |
| modal | `create` | the builder's modals |
| modal | `submit` | the ticket |

Anything else gets no response, as in v3. New IDs: builder buttons `ticket:1:a=create;b=<sub>`,
color buttons with `c=<1-4>`, the preview button `a=create;b=prev` (v3's `ticket@b:prev` had no
action), the panel button `a=press;f=<index>`, the reason modal `a=submit;e=<message>;f=<index>`,
the control row `a=<lock|unlock|save|delete>;d=<user>;e=<message>;f=<index>` (64 characters with
19-digit IDs) and the save select `a=save;b=select-channel;d=...;e=...;f=...` (at most 81). v3's IDs
from before `b4d10e2` (only `f:`) have no action and get no response, as on v3's `main`.

### Commands

`create-ticket` (no options) and `add-ticket` (`message_id`, a required string) are guild commands
built in `setup` from `register.yaml` (`create_ticket.name`, `add_ticket.options.message_id.name`,
...), with v3's base names and descriptions and `app_commands.default_permissions(administrator=
True)`. The command tree defers both ephemerally, as v3's core did; they answer with
`edit_original_response`.

### The builder

The cog keeps `drafts: dict[(user ID, guild ID), Session]`, a frozen `Session(message_id, draft,
target)`: the builder message's ID, the immutable `Draft`, and for `/add-ticket` the target message's
ID and first embed. v3 kept one `Step` per user across guilds.

- `/create-ticket` builds `defaults(texts)` in the user's locale and edits the deferred response into
  `create-ticket`; the session keeps the ID of the message that the edit returns.
- `/add-ticket` reads `message_id` (digits only, else `error.invalid-message-id` with the text's
  first 100 characters, since Discord's string options take 6000 and its replies 2000), fetches the
  message from `interaction.channel` (any failure: `error.message-not-found`), requires the bot's
  own message (`error.not-own-message`; v3 failed silently at the confirmation), a first action row
  with fewer than five components and no select (`error.message-full`; v3 compared with five only),
  and an embed (`error.no-embed`; v3 stayed "thinking"), then shows `add-ticket` with that embed.
- The builder's templates get v3's models: `tt@embed-demo` (`preview_embed`, or the target's first
  embed) and `tt@btn-demo` (`preview_button`), rendered with `global_values` (v3 had no substitutor
  there) in the user's locale.
- Presses, selections and submissions look the session up by user and guild and compare
  `interaction.message.id` with the session's; without a match they answer `error.expired` (v3:
  `deferEdit` without a session, and any builder of the user drove the newest draft).
- Modals (`modify-author`, `modify-content`, `modify-color`, `modify-btn-text`, `modify-reason` and
  the preview's `prev`) open with `response.send_modal(render_modal(...))`, values
  `placeholder_values(interaction)` with the draft's `tt@*` values (v3's `Placeholder.get(event)`).
- Screens (`modify-category`, `modify-admin`, `modify-btn-color`, `back`) and every change answer
  with one `response.edit_message(...)` of the whole builder (v3's `deferEdit` and the hook's
  `editOriginal`): the builder keeps working after the command's 15 minutes (B14).
- A change is kept only once Discord took the builder that shows it: `_update` edits first and
  stores the new draft after; when the edit raises `discord.HTTPException`, the response is still
  open and answers `error.refused` with the error (v3 logged the failure, left the builder as it was
  and kept the broken draft, so every later render failed too). Discord checks what discord.py does
  not: emojis, URLs, empty embeds.
- Submissions (`drafts.submit`): `modify-author` sets the author and icon URL, an empty one meaning
  none (v3 set `""`, which JDA refused for the icon); `modify-content` the title and description,
  empty meaning none (JDA refused an empty title); `modify-reason` the reason title unless empty
  (v3); `modify-embed-color` a color written `#RRGGBB`, `0xRRGGBB` or `RRGGBB` with one to six hex
  digits, else `error.invalid-color` (v3 parsed `substring(1)`, so `0x00FFFF` failed and `FFFFFF`
  became `0x0FFFFF`, B5); `modify-btn-text` (and v3's `modify-btn-content`) the button's text and
  emoji, both empty refused with `error.button-empty` (v3 checked for missing inputs, which Discord
  never sends); `prev` changes nothing. The emoji is kept as written (`PartialEmoji.from_str` reads
  custom ones too; v3's `Emoji.fromUnicode` made them invalid).
- Selections: the role select replaces the staff roles; the category select takes the first value
  and answers `error.category-not-found` unless the guild's cache knows it as a category (v3's
  check); a color button sets the style from `color_index` 1 to 4, anything else changing nothing
  (v3's `ButtonStyle.fromKey` threw).

### Confirming

`confirm-create` takes the session before its first await (a second press gets `error.expired`),
acknowledges with `response.defer()` and:

- for a new panel, renders `confirm-create` with `tt@embed` (the preview embed) and `tt@btn` (the
  panel button `a=press;f=0`), sends it to `interaction.channel` and stores `[entry]` under the
  posted message's ID (`Panels.add`); a store failure deletes the post, as Giveaway does;
- for an added button, under the guild's lock: fetches the target again, checks its first row
  again, builds its view with `View.from_message` and appends the panel button to the first row
  (a new first row when it has none; v3 threw), with the index `len(stored list)` (v3 used the row's
  size, which differed with other buttons in the row, B6), edits only the view (v3 kept the first
  embed and the first row only, B17), and appends the entry; when the store fails, the message gets
  its earlier view back (`targets.unplace`, a refusal logged), since a button without its entry
  would answer `error.not-found` and the next confirmation would give a second button its ID,
  which Discord refuses.

Then it deletes the builder (`delete_original_response`; v3 deleted it first, B15). On any failure
(`discord.HTTPException`, `DataError`, `sqlite3.Error`, the row full) the session comes back unless
the user started another, and `error.create-failed` with the error follows ephemerally; the builder
stays.

### Panels and tickets

- `press`: the entry of the message (`msg_id` when the ID has one, else the pressed message) and
  `btn_index`; without one, `error.not-found`. The modal `press-ticket` gets `tt@msg-id` (the same
  message; v3 put the pressed message's ID there even when the lookup used `msg_id`), `tt@btn-index`
  and `tt@reason`, the reason title clipped to Discord's 45-character label.
- `submit`: `response.defer(ephemeral=True, thinking=True)` (v3's `deferReply(true)`), then the entry
  (`error.not-found`; v3 threw, B4), the category (`categoryId` 0: the category of the panel's
  channel, a thread's parent's; else `guild.get_channel`, which must be a category;
  `error.no-category` otherwise; v3 replied after deferring, which never arrived, B3), the channel
  (`category.create_text_channel(<username>, overwrites=...)`), the opener and
  `edit_original_response` with `reply.go-to-channel`. A refused channel answers
  `error.ticket-failed`; a refused opener deletes the channel first (v3 left it without controls,
  B10), so that no channel stays without its control row.
- Overwrites (`tickets.overwrites`): discord.py's `create_text_channel(overwrites=...)` does not copy
  the category's overwrites as JDA's `createTextChannel` did, so the map is built: the category's
  overwrites when the bot is an administrator or holds every permission they allow or deny in the
  category (JDA's `trySync`), leaving out uncached roles, which discord.py would send as member
  overwrites; then @everyone denied View Channel only, the member and each staff role that still
  exists allowed View Channel only (each replacing a copied one, as JDA's `addPermissionOverride`),
  and the bot's member with View Channel allowed on top of its copied overwrite (v3 added none, so
  the bot needed Administrator or a staff role, B11).
- Opener (`tickets.opener`): v3's text, `<@&id> ` per stored staff role, `\n\n` and the reason, cut
  into parts of at most 2000 UTF-16 code units (v3 threw above 2000, B10), the unlocked control row
  on the last; `allowed_mentions` pings the staff roles only (v3 pinged everything, so a typed
  `@everyone` pinged everyone, S1).

### The control row

`control_row(locked, user, message, index, texts)` is v3's row with the labels of `text.yaml` in
zh-TW: unlock (green, U+1F513) or lock (gray, U+1F512), save (blue, U+1F4BE) and delete (red,
U+1F5D1), each ID carrying the ticket's member, the panel's message and the button's index.

- `lock` / `unlock` acknowledge at once (`response.defer()`; v3 answered after two REST calls,
  risking Discord's three seconds), find the member (`guild.get_member`, else `fetch_member`), set
  their overwrite with View Channel denied or allowed and the other permissions as they were
  (`channel.overwrites_for`, `set_permissions`), then show the other row through
  `edit_original_response`. No permission check, as in v3 (the member can lock themselves out). A
  failure answers `error.lock-failed` ephemerally (v3: the press failed).
- `delete`: the entry (`error.not-found`); a member with a staff role or Administrator
  (`interaction.permissions.administrator`, v3's `hasPermission(ADMINISTRATOR)`) gets
  `response.defer()` and the channel's deletion (`error.delete-failed` on a refusal); anyone else
  gets `response.defer()` only, as in v3.
- `save`: the entry (`error.not-found`), staff only (`error.admin-only`), then an ephemeral reply
  `reply.choose-channel` with `save_select`, a channel select of text channels, one value, the same
  text as its placeholder.
- The select (`sub_action` `select-channel`, else `response.defer()` as v3's `deferEdit`) checks in
  v3's order: a member (`error.no-member`), the entry, staff, a text channel as the source
  (`error.not-text-channel`), a text channel among the values (`error.choose-text-channel`), the
  bot's View Channel and Read Message History in the source (`error.no-history-permission`), its
  View Channel, Send Messages, Send Messages in Threads, Create Public Threads and Manage Webhooks
  in the target (`error.no-target-permission`); then `response.defer(ephemeral=True, thinking=True)`
  (a new ephemeral message, so the select stays usable), `reply.saving`, the archive, and
  `reply.saved` or `error.save-failed`. A final edit refused after Discord's 15 minutes is logged.

### The archive

`archive.archive(source, target, texts, now, zone, upload_limit)` runs v3's steps in order, one
request at a time, over Protocols that discord.py's objects satisfy:

1. `target.create_thread(name=thread_name(source.name, now, zone), type=public_thread)`:
   `-yyyy-MM-dd_HH:mm:ss` in the host's zone (v3's `ZoneId.systemDefault()`), the name cut to
   `100 - 20` UTF-16 code units at a character boundary (Python has no `BreakIterator`: a cut never
   splits a surrogate pair, nor separates a combining mark, a variation selector, an emoji modifier
   or a zero-width joiner from what it belongs to).
2. `target.create_webhook(name=webhook_name(ms, n))`: `ticket-save-content-<base36 epoch ms>-<base36
   (nanosecond counter & 0xFFFFF)>`. When it fails, the empty thread is deleted (v3 left it).
3. `source.history(limit=None, oldest_first=True)`; each message with text or attachments is sent
   with `webhook.send(content, files, username, avatar_url, thread=, wait=True,
   allowed_mentions=AllowedMentions.none())` (v3 pinged everything again, S1). The name is the
   member's display name when discord.py has the member, else the username (v3's
   `member?.effectiveName ?: author.name`), the first of the display name, the username and the ID
   that Discord takes as a webhook name (1 to 80 characters, none of `@`, `#`, `:`, three backticks,
   `discord` or `clyde`, not `everyone` or `here`; v3's archive failed there). The avatar is
   `display_avatar.url`. Text over 2000 UTF-16 code units is sent in parts, the files with the last
   (v3 hung, B12); a file over the guild's upload limit is sent as its URL on its own line (v3's
   upload failed).
4. A top-level message whose `thread` is set and not yet flattened is followed by
   `archive.start`, the thread's messages forwarded the same way (threads in threads are not
   flattened), and `archive.end` with the time of the thread's last message, or
   `archive.no-message`; Discord refusing the start marker, the thread's history or one of its
   messages (`discord.HTTPException`) sends `archive.error` with the error and `archive.end`
   without a time, and the archive goes on (a refused error marker is logged); a refused end
   marker stops it, as in v3. Other errors (a lost connection) stop the archive like any failure
   outside a thread; v3 caught every error there. The markers use the
   webhook's own name; the owner is the thread owner's display name when cached, else its ID; times
   are `yyyy-MM-dd HH:mm:ss` in the host's zone, the thread's start being its ID's time (JDA's
   `timeCreated`).
5. The webhook is deleted, errors ignored, whether the archive ended or failed.

Any exception stops the archive (v3 lost those thrown in callbacks and hung, B12); the cog edits the
answer into `error.save-failed` with `readable_error`: the error's text without line breaks, its
URLs cut to their origin by `xincord.plugins.redaction.redact` (a timed-out webhook request names
the webhook's URL, whose path holds its token), at most 200 UTF-16 code units, or the exception's
class name.

### Shared redaction

UptimeHeartbeat's `origin`, `private_parts` and `redact` move from its `logs.py` into
`xincord.plugins.redaction`, a package without an entry point that both plugins import
absolutely; UptimeHeartbeat's `Failures` stays in its `logs.py`. Behavior is unchanged.

### Left guilds

`on_guild_remove` deletes the guild's document (v3, only while enabled) and its drafts (v3 kept the
user's step). `on_ready`, and `cog_load` in a ready bot, delete the documents of guilds that
`bot.get_guild` does not know (WelcomeGoodbye's `forget_left_guilds`); keys that are not guild IDs
are skipped with a warning.

### Channel names (TicketAwayNotice)

A ticket channel is named after the member's username (`interaction.user.name`), which Discord
keeps as written for text channels since usernames are lowercase letters, digits, `_` and `.`;
duplicates are allowed. This is v3's name (`Ticket.kt:281`), and the port keeps it. TicketAwayNotice
(v3 TicketAddons, ported next) posts its notice in new channels whose names start with one of its
configured prefixes, `客服單-` and `ticket-` by default; v3's Ticket channels matched them only when a
username did. Contract for TicketAwayNotice: Ticket creates text channels in a category, named
exactly the member's username, through discord.py's `create_text_channel` (so `on_guild_channel_create`
fires once per ticket), before it sends the opener.

### Time zone

The thread names and the markers use the host's zone, as v3 (`datetime.now().astimezone()`), with
no config key; in the compose container that is UTC unless `TZ` is set. The cog keeps `clock` and
`zone` (None for the host's) so that tests fix them.

### Choices made while building

- A channel that has no permission overwrites or cannot be deleted (not a guild channel) answers
  `lock-failed` or `delete-failed` with a fixed English reason; v3's handlers threw before
  answering.
- A control row or save select whose member ID is not a number gets no response, as v3 threw
  before answering.
- A failed archive is logged with its redacted error text, and with a redacted traceback when it
  is not a Discord refusal.

## Inventory audit

Each behavior of `docs/porting/analysis/inventory/Ticket.md` is a requirement with tests, or is
listed here:

| Inventory | Where |
|---|---|
| 1 Overview, info.yaml, `component_prefix` | "The plugin installs as Ticket"; `IDS` (legacy prefix `ticket@`) |
| 2 Lifecycle: `enabled`, reload, lazy init, in-memory steps | no config (the core's `plugins` list); a reload rebuilds the cog, so drafts go ("Only the latest builder of a draft works"); the store is read at each use |
| 3 Slash commands, auto-defer, localizations | "The commands are localized administrator guild commands" |
| 3.1 `/create-ticket` and the defaults | "The create command opens the builder" |
| 3.2 `/add-ticket` (B7, B8, B9, B16) | "The add command opens the builder for a message" |
| 3.3 Wizard buttons, sub-screens, selects, modals, render failures (B1, B2, B5, B14) | "Builder buttons open pre-filled modals", "Builder buttons switch screens", "Submitted modals change the draft", "Selections change the draft", "A change that Discord refuses keeps the draft", "Only the latest builder of a draft works" |
| 3.4 Preview and defaults | "The preview shows the draft", "The create command opens the builder" |
| 3.5 Confirm (B6, B15, B17) | "Confirming posts a new panel", "Confirming adds a button to the message", "A panel that cannot be posted keeps the builder" |
| 3.6 press, submit (B3, B4, B10, B11, S1), control row, lock, unlock, delete, save | "Pressing a panel button asks for the reason", "Submitting the reason opens a ticket channel", "Ticket channels get v3's permissions and the bot's", "The control row locks and unlocks the ticket", "Administrators delete the ticket", "Administrators choose where to save the conversation" |
| 3.7 Archive engine (B12) | "The archive copies the conversation into a thread", "Threads started in the ticket are flattened", "A failed archive is reported and cleans up" |
| 4 Component IDs, legacy IDs before `b4d10e2` | "v3's panels and tickets keep working"; golden tests decode every ID shape; IDs without an action get no response |
| 5 Events, guild leave | `handle`'s dispatch; "Leaving a guild forgets its panels" |
| 6 Configuration (`enabled`, strict KAML) | no config: out of scope, the core's `plugins` list replaces it |
| 7 Localization, templates, model keys, placeholders, fallback | "Texts follow the reader"; golden tests render every template; recursive substitution is gone in the core (B10 of the decisions) |
| 8 Persistence, corrupt files, migration | "Panels are stored as v3's documents"; reading v3's files is the v3 data import's (out of scope); stale panels of deleted messages stay (out of scope, as v3) |
| 9 External dependencies (the lovepik icon) | the default icon URL is v3's, in `text.yaml` |
| 10 Discord requirements (Message Content, permissions, rate limits, 15 webhooks) | "Risks" and the smoke checklist; discord.py handles rate limits; a refused webhook is a reported failure |
| 11 Concurrency (steps, lost updates, double confirmation, archive hangs) | per-guild lock for appends; the draft taken before the first await; archive failures reported |
| 12 Bugs B1 to B17 and S1, dead code (`confirm-add.yaml`, the ignored prefix check, the TODO) | "v3 behaved differently" below; `confirm-add.yaml` ships unused; the prefix check is the core's routing |
| 13 Testability, 14 assessment | the module split above |

## v3 behaved differently

- v3 behaved differently: the preview button's ID had no action, so pressing it failed and the
  `preview-reason` modal was unreachable (B1); it opens that modal.
- v3 behaved differently: the zh-TW button modal's ID said `modify-btn-content`, which the handler
  did not know, so zh-TW users (and every locale that fell back to zh-TW) could not change the
  button's text or emoji (B2); the bundled file is fixed and the old ID is accepted.
- v3 behaved differently: a missing category and missing panel data after the reason left the
  member's response "thinking" (B3, B4); they get v3's error texts.
- v3 behaved differently: colors were read after their first character, so the placeholder's
  `0x00FFFF` failed the modal and `FFFFFF` became `0x0FFFFF` (B5); `#`, `0x` and no prefix work, and
  anything else is refused with an error.
- v3 behaved differently: an added button's index was its row's size, which pointed at another
  entry when the row held other buttons (B6); it is the stored list's length.
- v3 behaved differently: `/add-ticket` with a non-numeric ID, an unknown message or a message
  without an embed stayed "thinking" or stored a broken draft (B7, B8, B9); each gets an error.
- v3 behaved differently: an opener over 2000 characters was never sent, leaving the channel
  without controls (B10); it is split.
- v3 behaved differently: the ticket channel had no overwrite for the bot, which then needed
  Administrator or a staff role (B11); the bot allows itself View Channel.
- v3 behaved differently: an archive failure thrown in a callback (a 4000-character message, a
  webhook name Discord refused, an upload over the limit) hung the archive and leaked the webhook
  (B12); every failure is reported and the webhook deleted, and long texts, names and large files
  are handled.
- v3 behaved differently: `press-ticket`'s titles were swapped between zh-TW and en-US (B13); the
  bundled files are fixed.
- v3 behaved differently: the builder rendered through the slash command's 15-minute hook (B14);
  each interaction answers itself.
- v3 behaved differently: confirming deleted the builder first and never acknowledged, so any
  failure was invisible (B15); failures are reported and keep the builder and the draft.
- v3 behaved differently: a first row with a select passed the full check and failed at the edit
  (B16); it counts as full.
- v3 behaved differently: adding a button dropped the message's other rows and embeds (B17); they
  stay.
- v3 behaved differently: the opener and the archive used JDA's default mentions, so a typed
  `@everyone` or role mention pinged (S1); the opener pings the staff roles only, the archive nobody.
- v3 behaved differently: an invalid value (an empty title, an invalid emoji) stayed in the draft
  and every later render failed silently; the change is refused with Discord's error.
- v3 behaved differently: a user's step served any guild and any of their builder messages, and
  outlived the guild; drafts are per user and guild, only the newest builder works, and leaving a
  guild drops its drafts.
- v3 behaved differently: lock and unlock answered after fetching the member and setting the
  overwrite, and a failure left the press failed; they acknowledge at once and report failures.
- v3 behaved differently: panels were kept in `plugins/Ticket/data/<guildId>.json`, rewritten at
  every load and created when read; they are v3's documents in the store, and a guild left while
  the bot was offline is forgotten at READY.

## User-visible changes

- en-US users get English replies and errors (v3: Chinese for all but four English errors), and
  zh-TW users get those four in Chinese; the builder's defaults follow the administrator's language.
- New error texts: session expired, invalid message ID, not the bot's message, no embed, invalid
  color, refused change, create failed, ticket failed, lock failed, delete failed.
- The preview button opens the reason modal; the builder keeps working past 15 minutes; an older
  builder message answers that the session expired (v3 did nothing).
- Colors accept `#RRGGBB`, `0xRRGGBB` and `RRGGBB`; custom emojis (`<:name:id>`) work on buttons.
- Confirming keeps the builder on a failure; added buttons keep the message's other rows and
  embeds; `/add-ticket` refuses other users' messages at once.
- The ticket channel gets an overwrite for the bot; long reasons arrive in several messages; the
  opener pings the staff roles only.
- Lock and unlock answer at once; the archive pings nobody, splits long messages, links large
  files, and renames authors whose name Discord refuses.

## Risks / Trade-offs

- The archive copies other members' text only when the application has the Message Content intent
  in the developer portal (REST history is gated as the gateway is); v3 had the same undeclared
  requirement. The plugin does not request the intent, so the bot connects without it.
- Long archives run inside the interaction's handler for minutes (discord.py handles the rate
  limits); the final edit fails after Discord's 15 minutes and is logged.
- After a handler deletes a v3 ticket channel (delete on a v3 row), the core's upgrade cannot fetch
  the message and logs an error, as for Feedback.
- `create_text_channel` with overwrites needs Manage Roles, as v3's did; copied overwrites that
  name a role discord.py has not cached are left out.
- The core's upgrade of a v3 panel fetches the message after the handler and edits the components
  of that copy: an `/add-ticket` confirmation whose edit lands between that fetch and that edit
  loses its button again while its entry stays stored. It needs a v3 panel pressed during the
  confirmation, and is the core's, as for Giveaway's posts.
- Until the v3 data import, a v3 panel has no stored list: `/add-ticket` on it gives the new button
  index 0, which the panel's v3 button (`ticket@a:press;f:0`) names too, so both open the new
  entry, and Discord refuses the core's upgrade of the v3 button for the duplicate ID at each press
  (logged). The import should run before administrators add buttons to v3 panels, and expect lists
  that `/add-ticket` started meanwhile.
- Only Discord's refusals are handled where the plugin creates something: a ticket whose opener
  fails otherwise (a lost connection, an unload) keeps its channel without the control row, the
  member's answer stays "thinking", and the core logs the error, as for the other plugins.
- The archive downloads a message's files into memory before sending them (discord.py's
  `Attachment.to_file`), where JDA streamed them: a message with ten files near a boosted guild's
  upload limit (100 MB at level 3) holds about 1 GB at once.

## Checks

- Package: the `xincord-plugins` wheel holds the 32 lang files and no `ticket/config.yaml`;
  `xincord --no-online` from a scratch venv with both wheels exits 0 with Ticket loaded.
- Image: `docker compose build`, then `docker compose run --rm -T bot --no-online` with the fourteen
  ported plugins enabled, exits 0 with every one loaded.
- Probe (a scratch script driving discord.py's own objects with HTTP recorded): the commands, the
  builder, the confirmation, the reason modal (a label holding the paragraph input), the ticket
  channel (overwrite types 0 for roles and 1 for members, @everyone denied View Channel, the
  member, the staff roles and the bot allowed it, an uncached role's overwrite left out), the
  opener, lock and unlock (`PUT .../permissions/{member}` with type 1), the save select
  (`channel_types` [0]), the archive (a type-11 thread, the webhook, executions with `thread_id`
  and `wait`, the markers, the webhook's deletion), `/add-ticket`, delete, and v3's panel and lock
  IDs with the core's upgrade. It found that the opener let typed user mentions ping, fixed in
  `dd324fd`.

## Manual smoke checklist

Needs a token, a test guild, a second account and a category; the bot needs View Channel, Send
Messages, Embed Links, Manage Channels and Manage Roles, and Read Message History, Create Public
Threads, Send Messages in Threads and Manage Webhooks in the archive channel; the Message Content
intent on in the developer portal for the archive.

1. Enable `Ticket` in `config.yaml`; start; `/create-ticket` shows the zh-TW builder (en-US client:
   English buttons and defaults).
2. Change every value through each button, select and modal; the preview button opens the reason
   modal; `0x00ff00` sets the color, `green` is refused; an invalid emoji such as `abc` answers the
   refused text and the preview stays.
3. Confirm: the panel is posted and the builder disappears. `/add-ticket` with the panel's ID adds
   a second button; another user's message, a message without an embed and `abc` are refused.
4. From the second account, press each panel button: the reason modal shows the reason title; the
   ticket channel is named after the account's username, visible to it, the staff roles and the bot
   only, and the opener pings the staff roles.
5. Lock, then unlock: the account loses and regains the channel. Save into a text channel: a public
   thread holds the messages in order with their authors, a thread started in the ticket is
   flattened between markers, and the webhook is gone afterwards. Delete as staff: the channel goes;
   as the member: nothing happens.
6. With v3's data imported (later), press a v3 panel and a v3 control row: they work, and their
   IDs are rewritten.
