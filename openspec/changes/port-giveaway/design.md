## Context

v3's Giveaway (`Plugins/Giveaway`, 8 Kotlin files, 1426 lines) has three parts. The builder
(`StepManager.kt:16-380`, `StepData.kt:16-148`) keeps an in-memory draft per user and guild, opened
by `/create-giveaway` (`Register.kt:19-24`), and drives it through an ephemeral preview with ten
buttons and six modals, re-rendered through the slash command's hook. The giveaway
(`Giveaway.kt:187-633`) posts the public message, toggles participants, draws and rerolls, and a
scheduled executor (`Giveaway.kt:93-185`) draws the due giveaways. The data (`GiveawayData.kt:7-102`)
is a Moshi document per guild in `plugins/Giveaway/data/<guildId>.json`, with the pure
`drawPrizeWinners`. `Event.kt:19-118` forwards JDA's events when `enabled` is true. The inventory
is `docs/porting/analysis/inventory/Giveaway.md`; its section 12 lists 18 probable bugs and the
behavior to preserve. Most user-facing texts are hard-coded in Kotlin, chosen by a `zh` prefix.

## Goals / Non-Goals

**Goals:** v3's command, builder, modals, validations, preview, post, buttons, permissions, draw
algorithm, automatic draw and texts; v3's templates and IDs, so that v3's posts keep working; v3's
per-guild JSON documents in the store; every v3 defect of the inventory's section 12 fixed or
recorded.

**Non-Goals:** migrating v3's data files (B11); new giveaway commands (cancel, edit, end early);
checking winners' membership; expiring drafts by time; the Web Dashboard (B13).

## Decisions

### Package and bundled files

`packages/xincord-plugins/src/xincord/plugins/giveaway/`:

- `__init__.py`: `DEPENDS = ()`, `SOFT_DEPENDS = ()`, `INTENTS = discord.Intents.none()` (guild
  leaves need only the default guilds intent; members come with each interaction), and `setup`,
  which loads the config first, then the lang files with the config's `defaultLocale`, the
  templates, the cog, the command and the route.
- `config.py`: `Config` (below) and `DEFAULT_LOCALE = "zh-TW"`, the default of `defaultLocale`.
- `channels.py`: the Protocols of the channels and messages that the plugin posts to and edits
  (`Posted`, `Editable`, `Postable`, `Channel`) and `postable`.
- `model.py` (pure): `Prize`, `Policy`, `Draft` (v3's `GiveawayConfig`), `Winners`, `Instance`
  (v3's `GiveawayInstance`), `parse_instance` / `instance_json` (v3's Moshi JSON), `DataError`,
  `draw_winners` and the transitions `join`, `draw` and `is_due`.
- `times.py` (pure): `parse_end_time(text, zone)` and `format_end_time(epoch, zone)`.
- `inputs.py` (pure): `trim` (Kotlin's `String.trim()`), `winner_count`, `is_http_url`,
  `thumbnail` and `clip` (lengths in UTF-16 code units, as JDA counted them).
- `drafts.py` (pure): `submit(draft, sub_action, values, now, zone)` (a modal's change or the error
  key), `remove_last_prize`, `switch_policy` and `problem(draft, now)` (the confirmation's check).
- `texts.py`: `language(lang, locale)`, `Texts` (one language's texts with `%ga@...%` values) and
  the embeds and buttons that v3 built in code: `preview`, `post_embed`, `post_buttons`,
  `result`.
- `store.py`: `Giveaways(store)`: `get`, `ids`, `add`, `change` and `draw_due`, each under the
  guild's lock.
- `cog.py`: the cog `Giveaway`, `IDS`, the command, `handle` and its handlers, the automatic draw
  loop and `on_guild_remove`.
- `config.yaml` and `lang/<locale>/` with v3's `register.yaml`, `message/*.yaml` and
  `modal/*.yaml` unchanged, and the new `text.yaml`.

v3's texts that were written in Kotlin (`Giveaway.kt`, `StepData.kt`, `StepManager.kt`) move to
`lang/<locale>/text.yaml` (read with `Lang.text("text.<key>", locale)`), because Python files hold
no CJK text: the preview's and the post's titles, field names, values and footers, the button
labels, the statuses, the winner lines, the draw result's header and body, every reply and every
error. Values are `%ga@...%` placeholders rendered in one pass (`ga@title`, `ga@index`,
`ga@prize-name`, `ga@winner-count`, `ga@id`, `ga@end`). v3's templates keep their `model_key`s:
the plugin builds `ga@preview-embed`, `ga@giveaway-embed` and the three buttons and passes them to
`render_message` as models.

### Config

```yaml
defaultLocale: "zh-TW"          # v3's key: the fallback locale of texts and templates
autoDrawIntervalSeconds: 60     # v3's key: seconds between the automatic draw's passes
timeZone: ""                    # new: the IANA zone of the end times; empty: the host's
```

`Config(Model)` keeps v3's camelCase keys through pydantic aliases (`default_locale`,
`auto_draw_interval_seconds`, `time_zone`), so v3's files load unchanged and `enabled` only warns.
`defaultLocale` must be a Discord locale (`discord.Locale` values, case-sensitive as JDA's
`DiscordLocale.from`); a locale without a lang directory fails in `context.lang` with the locale
named. `autoDrawIntervalSeconds` is a strict integer, clamped to 5..3600 by the `period` property,
as v3's `coerceIn`. `timeZone` must be empty or a zone that `zoneinfo` knows; `zone` is the
`ZoneInfo`, or None for the host's local time, which `datetime` uses for naive values (v3's
`ZoneId.systemDefault()`).

### Language

v3 chose hard-coded texts by a `zh` prefix of the locale (zh-TW or English) and templates by the
locale's directory, else the configured default, so an en-GB user saw English texts and zh-TW
buttons. `language(lang, locale)` picks one locale for both: the locale itself when the plugin has
its files, else `zh-TW` for a `zh` locale and `en-US` otherwise; `Lang.text` and `Lang.template`
then fall back to `defaultLocale` per key, as for every plugin. The builder, the modals and their
replies use the user's locale (`interaction.locale`); the post, its replies, the draw result and
the announcement use the creator's locale stored in `localeTag`; the not-found reply uses the
user's, as in v3.

### Storage

v3's `JsonGuildFileManager` file is one document per guild in the store's key-value table:
namespace `Giveaway`, key the guild ID in decimal, value v3's JSON unchanged:
`{"<id>": {"id", "guildId", "channelId", "messageId", "creatorId", "localeTag",
"createdAtEpochSecond", "endedAtEpochSecond"?, "ended", "config": {"title", "description",
"sponsor", "thumbnailUrl", "endAtEpochSecond", "winnerDuplicatePolicy", "prizes": [{"name",
"winnerCount"}]}, "participantIds": [...], "winnerResults": [{"prizeName", "winnerIds"}]}}`, in
Moshi's field order, snowflakes as JSON integers (Python's `json` keeps those above 2^53 exact).

- `parse_instance` follows Moshi: `id`, the four IDs and `config` are required, `prize.name` and
  `prizeName` too; missing optional fields take v3's defaults (`localeTag` zh-TW, `ended` false,
  `endedAtEpochSecond` absent, `winnerCount` 1, empty lists and texts, the policy
  `ALLOW_DUPLICATE`), except `createdAtEpochSecond`, which Kotlin set to the time of reading and
  which reads as 0 (it was never read); unknown fields are dropped when the entry is rewritten, as
  Moshi did. Booleans are not integers; a text, a fraction, `null` for a required field or an
  unknown policy raises `DataError` naming the guild and the giveaway. Duplicate participants read
  once, in order, as v3's set did.
- Only the entries an operation needs are parsed: a broken entry raises for operations on it (the
  core logs the failed interaction) and is never rewritten; the automatic draw logs it and handles
  the guild's other giveaways. v3's Core replaced the whole file with `{}`.
- Every change of a guild's document runs under `store.lock("Giveaway:<guild ID>")`: read, change
  one entry, write only when something changed (DynamicVoiceChannel's pattern for changes that may
  change nothing). Only this plugin writes its namespace, so the lock serializes every writer:
  joins, draws, rerolls, the automatic draw and new giveaways never lose one another, and a draw
  and the automatic draw cannot both draw. The lock comes from the store, so it outlives reloads.
- Reads (`get`, `ids`) write nothing; a guild without a document has no giveaways.
- Giveaways are kept forever, as in v3 (rerolls need them), and when the bot leaves the guild
  (below).

### Drafts and the builder

The cog keeps `drafts: dict[(user ID, guild ID), Session]`, a frozen `Session(message_id, draft)`
replaced on each change (immutable `Draft`s). The command builds an empty draft, edits the deferred
response into the builder and keeps the session with the ID of the message that the edit returns;
a second command replaces the session, so only the newest builder works.

Builder presses (`action` `create`) and submissions look the session up by the user and the guild
and compare the message they come from (`interaction.message.id`, the builder for a modal too);
without a match they get the session-expired text, as v3 without a session. Presses then dispatch
on `sub_action`:

- set-title, set-description, set-end-time, set-sponsor, set-thumbnail, add-prize:
  `response.send_modal(render_modal(...))` with `placeholder_values(interaction)` (v3's
  `Placeholder.get(event)`) and the draft's `ga@*` values; `ga@prize-name` is `text.new-prize`
  with the next prize's number.
- remove-prize and toggle-duplicate-policy: change the draft, then
  `response.edit_message(...)` with the whole builder (v3's `deferEdit` and hook edit in one
  response); remove-prize without prizes answers `text.error.no-prize` ephemerally.
- confirm-create and cancel: below. Unknown sub-actions get no response, as v3's buttons.

A submission reads `modal_values(interaction.data)` (a missing input is empty), trims each value as
Kotlin's `trim()` did and calls `drafts.submit`: an error key is sent ephemerally, a new draft is
kept and the builder message is replaced through `response.edit_message` (a modal opened from a
message may update it). An unknown sub-action gets no response.

End times (`times.py`): `\d{4}-\d{2}-\d{2} \d{2}:\d{2}` in ASCII digits, the year 0001 to 9999,
month 1 to 12, day 1 to 31 then clamped to the month's length, hour 0 to 23 or `24:00` for the next
day's start, minute 0 to 59 (Java's `DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")` with the
SMART resolver, verified in the inventory). The wall time is converted in the zone with
`datetime.timestamp()`, whose fold 0 takes the earlier offset in an overlap and moves a time in a
gap forward, as Java's `atZone`; a time beyond `datetime`'s range is no end time. Formatting writes
the four-digit year itself (`strftime("%Y")` does not pad below 1000 everywhere).

Inputs (`inputs.py`): winner counts take Kotlin's `toIntOrNull()` grammar, `[+-]?` and decimal
digits of any script (`\d` with `str` patterns, then `int`), then 1 to 50. Thumbnails follow
`java.net.URI` with a server-based authority: an `http` or `https` scheme in any case, `//`, an
optional user info, a host that is an RFC 2396 host name (labels of letters, digits and inner
hyphens, the last one starting with a letter), a dotted IPv4 address with parts up to 255 or a
bracketed IPv6 address (`ipaddress`), an optional port, then a path, a query and a fragment of
RFC 2396's characters, escapes and Java's "other" characters (non-ASCII, neither control nor
space). The preview and the post show a thumbnail whose URL starts with `http://` or `https://` in
any case, with the scheme in lower case.

Texts that may exceed Discord's limits are cut by `clip(text, limit)`: the characters that fit in
`limit - 3` UTF-16 code units, then `...` (v3's `clipFieldText`, without splitting a character
outside the BMP). The preview clips its description and its prize list to 1024 (v3 did not, and
the builder stopped updating); the post clips its prizes and results to 1024 and then shortens its
description until the embed holds at most 6000 code units; the draw result's body is clipped to
1800, as in v3.

### Confirming

`confirm-create` checks `drafts.problem(draft, now)` (title, then a future end time, then a prize)
and then `interaction.permissions.administrator` (v3's `member.hasPermission(ADMINISTRATOR)`), each
failure an ephemeral reply. It then takes the session out of `drafts` before its first await, so a
second press gets the session-expired text (v3 posted two giveaways), acknowledges the press with
`response.defer()` (a deferred update, v3's `deferEdit`), picks an ID (`uuid.uuid4().hex[:16]`,
again while the guild has it, v3's loop) and posts `giveaway-post` to `interaction.channel` through
a `Postable` check (SimpleCommand's `_postable`). It stores the giveaway (`Giveaways.add`, which
refuses an ID that appeared meanwhile) with the post's ID, and edits the builder through
`edit_original_response` into `create-finished` with `%ga@jump-url%`, replacing its embeds and
buttons. When the channel takes no messages or refuses the post, or the store fails (the post is
then deleted, as v3's `message.delete()`), the session goes back unless the user started a new
one, the builder stays, and `create-failed` with `%ga@error%` (the error's text, cut to 1000
characters so that the reply stays within Discord's 2000) goes to the user as an ephemeral
follow-up; the failure is logged. Any other failure before a post (Discord refusing the deferral,
a cancellation) also gives the session back, then propagates to the core's log.

`cancel` takes the session out and replaces the builder with `create-cancelled` (content only,
`embeds=()` and `view=None`, as v3's replace edit).

### The post, joins and draws

The post is `giveaway-post` with models: the embed from `texts.post_embed` (v3's colors `0xF1C40F`
and `0x95A5A6`; the status at render time: drawn, else ready to draw once the end time has come,
else running) and the buttons from `texts.post_buttons` (`IDS.build({"action": ...,
"giveaway_id": id})`, v3's styles and disabled states).

Post presses resolve the giveaway from the `giveaway_id` field in the interaction's guild; a missing
field, an unknown ID or a press outside a guild answers `text.error.not-found` in the user's
language (v3's English-only `Invalid giveaway id.` and `Guild not found.` fold into it). Changes go
through `Giveaways.change(guild, id, transition)`, which runs a pure transition under the guild's
lock and writes only a changed instance:

- `model.join(instance, user, now)`: closed when drawn or `now >= end`; else the user is added or
  removed. A press from another message than `messageId` changes nothing, as v3's `deferEdit`.
- `model.draw(instance, user, admin, reroll, now, rng)`: not allowed unless (draw) the creator or an
  administrator or (reroll) an administrator; then already drawn, too early (`now < end`) or not
  drawn; else every prize is drawn, `ended` true and `endedAtEpochSecond` now.

Each press is acknowledged at once with `response.defer()` (a deferred update), before it waits for
the guild's lock: a burst of presses on a large document would otherwise run past Discord's three
seconds, and the user would see a failure for a join that was stored. Then every press from the
post shows the giveaway as stored, through `edit_original_response(...)` with the whole post (the
press's webhook, which no channel rate limit delays, where v3 edited the message through the REST
API), refusals included, so that a post left stale (a restart during a draw, a refused edit,
responses that crossed) is repaired by the next press; v3 left such a post with Reroll disabled for
good. The user is told with `followup.send(..., ephemeral=True)`: the joined or left text, the
rendered `draw-result` (`%ga@header%`, `%ga@body%`, `%ga@title%`) or the refusal, in the
giveaway's language. Winners are drawn with the cog's `random`, a `random.SystemRandom()`
that tests replace with a seeded `random.Random`; `draw_winners` samples with `rng.sample`, which
draws the same distribution as v3's Fisher-Yates `shuffled(...).take(k)`.

### The automatic draw

One task created in `cog_load` awaits `bot.wait_until_ready()`, sleeps 5 seconds (v3's initial
delay), then repeats `draw_due()` and `sleep(period)`; `cog_unload` cancels and awaits it. The
period counts from the end of each pass (v3's `scheduleAtFixedRate` counted from each start; passes
take milliseconds). `sleep`, `clock` and `random` are attributes of the cog, so tests drive the loop
on a fake clock.

`draw_due()` reads the namespace once (`store.items`), skips guilds the bot is not in or that are
unavailable (their giveaways wait for the guild), and for each guild with due giveaways calls
`Giveaways.draw_due`, which re-reads the document under the lock, draws every due entry, writes the
document and returns the drawn instances. Only then does it update each post with
`bot.get_partial_messageable(channel, guild_id=...).get_partial_message(message).edit(...)` and
send `auto-draw-result` (`global_values` with `%ga@title%`, `%ga@header%` and `%ga@body%`) to the
same partial messageable, so threads, announcement channels and voice channel chats work and no
cache or Read Message History is needed. Each refusal is a warning naming the giveaway, and an
unexpected failure while posting one drawn giveaway is logged (`logger.exception`) before the pass
posts the others, which are stored as drawn already; a failed pass is logged and the loop goes on,
as v3's `runCatching`.

### Component IDs

`IDS = ComponentIds("giveaway", ("action", "sub_action", "giveaway_id"),
legacy_prefix="giveaway@")`: v3's three string fields in v3's order (no hex fields), v3's
`component_prefix`. The builder's buttons and modals are `giveaway:1:a=create;b=<sub-action>`, the
post's `giveaway:1:a=<participate|draw|reroll>;c=<id>`. `handle` dispatches on the interaction type
and `action`: buttons (component type 2) with `create`, `participate`, `draw` and `reroll`, modals
with `create`; anything else, select menus included, gets no response, as v3. The core logs
malformed IDs and upgrades a v3 post's IDs after the handler; the post's own response already
replaced them when it updated the post.

### Tests

`tests/plugins/giveaway/`: `test_plugin.py`, `test_config.py`, `test_language.py`, `test_times.py`,
`test_inputs.py`, `test_winners.py`, `test_store.py`, `test_command.py`, `test_preview.py`,
`test_modals.py`, `test_submit.py`, `test_builder.py`, `test_confirm.py`, `test_post.py`,
`test_join.py`, `test_draw.py`, `test_auto_draw.py`, `test_routes.py` and `test_leave.py`.
`conftest.py` loads the plugin (the `config` and `files` fixtures, which tests parametrize, are the
operator's `config.yaml` and other files), gives the bot its user, stands for READY
(`plugin_fakes.Ready`) and puts the plugin's modules back after each test (`plugin_modules`: a failed
load would make discord.py import new dataclasses, which never equal the old ones); its `scene`
fixture fixes the cog's clock and bundles the bot, the store, the builder's channel and helpers that
run the command's draft (`keep`, `draft`), press builder buttons (`press`), submit modals
(`submit`), press a post's buttons (`click`) and store giveaways (`add`, `stored`) through the
plugin's route handler, as `Who` (`scene.who(...)`: the member, the locale, Administrator, the
message). Tests that draw seed the cog's `random`; `test_auto_draw.py` drives the loop with
`Ticks` (each sleep recorded and moving the clock); `test_confirm.py` catches a double press with a
`GatedChannel`; `test_routes.py` goes through `bot.on_interaction` with v3's IDs. `tests/fixtures/plugins/giveaway/golden.yaml` holds
v3's texts per locale (the preview, the post, the buttons, the modals, the replies, the draw
results and the command payload) and v3's example document. `discord_fakes` gains the message that
`FakeChannel.send` and `FakeInteraction.edit_original_response` return (with `id` and `jump_url`)
and `FakeChannel.get_partial_message`.

### v3 behaved differently

- v3 behaved differently: two quick presses of Confirm Create both passed the checks and posted two
  giveaways (the session was removed in the post's callback); the draft is taken before the first
  await, and the second press gets the session-expired text.
- v3 behaved differently: the builder re-rendered through the slash command's hook, so after 15
  minutes every preview update, the finish and the cancel failed silently; each press and
  submission updates the builder through its own interaction.
- v3 behaved differently: a description over 1024 characters (the modal allows 4000) or a prize
  list over 1024 made the preview throw in its callback, so the builder stopped updating; both
  fields are clipped with `...`.
- v3 behaved differently: sessions were keyed by user and guild only, so an older builder message
  drove the newest draft; only the builder message that shows the draft works.
- v3 behaved differently: a failed post replaced the builder with `create-failed` and kept an
  orphaned session without buttons, and JDA's client-side permission checks and an embed over 6000
  characters threw after the acknowledgement without telling the user; every failure keeps the
  builder and sends `create-failed` with the error.
- v3 behaved differently: the automatic draw refreshed and announced only in text channels, so
  giveaways in threads, announcement channels and voice channel chats were drawn silently; it
  posts through partial messageables, in any channel kind.
- v3 behaved differently: the automatic draw saved the guild's file after queuing the posts, and a
  manual draw and the automatic draw could both draw the same giveaway with different winners;
  every draw is stored under the guild's lock before anything is posted.
- v3 behaved differently: the guild's file was deleted when the bot left the guild (only while the
  plugin was enabled), losing every giveaway for rerolls; the giveaways stay, and only the drafts
  are dropped.
- v3 behaved differently: an invalid `defaultLocale` (`zh-tw`) became JDA's `UNKNOWN` instead of
  the intended zh-TW, and the missing `register.yaml` then aborted the whole bot; the plugin does
  not load, and the error names the key or the locale.
- v3 behaved differently: an uppercase scheme (`HTTPS://`) passed the thumbnail check but was never
  shown; it is shown, with the scheme in lower case.
- v3 behaved differently: draft values were expanded as placeholders in the modals, the draw result
  and the announcement (a title naming its own key made the modal throw), and the `ga@*` values
  stayed in the shared global substitutor; values are inserted as written, for one render.
- v3 behaved differently: JDA's default mentions let the announcement ping roles and everyone
  named in a title; the core's default allows user mentions only (B19), so winners are still
  pinged.
- v3 behaved differently: texts and templates were chosen separately (en-GB: English texts and
  zh-TW buttons; ja: an English post with a zh-TW announcement wrapper); one language per message.
- v3 behaved differently: shared state (the sessions, the files, the giveaways, the global
  substitutor) was changed from the gateway, callback and scheduler threads without locks; the
  plugin runs on the event loop and changes giveaways under the guild's lock.
- v3 behaved differently: a v3 data file whose name was not a guild ID aborted the bot, a broken
  entry replaced the guild's whole file with `{}`, and a disabled plugin still loaded the files and
  templates; giveaways are read from the store when needed and broken entries are left as they
  are.
- v3 behaved differently: the auto draw drew the giveaways of guilds the bot had left while
  offline, without refreshing or announcing them; they wait until the bot is back in the guild.
- v3 behaved differently: a modal with an unknown sub-action re-rendered the preview; it gets no
  response, like an unknown button. A post button without a giveaway ID answered `Invalid giveaway
  id.` in English and one outside a guild `Guild not found.`; both answer `Giveaway not found.` in
  the user's language.
- v3 behaved differently: `24:00` on 9999-12-31 and years after 9999 written with a sign
  (`+12026-01-05 10:00`) were end times; they get the format error, as do times whose UTC time is
  past 9999 (9999-12-31 23:59 west of UTC).
- v3 behaved differently: a drawn giveaway whose post was not refreshed (a crash after the draw, a
  refused edit) kept Join and Draw enabled and Reroll disabled for good; every press repairs it.

Kept from v3: drafts have no time limit (one per member and guild, gone at confirmation, cancel, a
new command, the guild's leave, a reload or a restart); there is no limit on the number of prizes;
the post is not re-rendered when its end time comes, so `Ready to draw` shows only if something
renders it before the draw; unknown actions and malformed IDs get no response; the automatic draw
waits five seconds after READY (v3: after each load); winners who left the guild can win.

### User-visible changes

- The builder keeps working after 15 minutes; its updates come from each press or submission.
- Only the newest builder message of a draft works; an older one answers that the session expired.
- A second Confirm Create press while the giveaway is posted answers that the session expired.
- A failed post keeps the builder and sends `create-failed` with the error as an ephemeral
  message (v3: the builder turned into `create-failed` without buttons).
- Long descriptions and prize lists end with `...` in the preview and the post (v3: the preview
  stopped updating, or the post or its refresh failed).
- Joining and drawing are acknowledged at once and update the post through the press; the joined,
  left, draw result and refusal replies arrive as ephemeral follow-ups, and any press repairs a
  post that shows an outdated state.
- Giveaways in threads, announcement channels and voice channel chats are refreshed and announced
  when drawn automatically.
- The announcement pings the winners but no roles or everyone (B19).
- An uppercase `HTTPS://` thumbnail is shown.
- A user whose locale has no lang files (en-GB, ja) sees English texts and English buttons, a zh-CN
  user zh-TW ones (v3 mixed them).
- Typed `%...%` in titles, descriptions and sponsors is shown as written.
- Giveaways stay when the bot leaves a guild, and are rerolled after it returns; due giveaways of a
  guild the bot left are drawn when it is back.
- New config key `timeZone`; an invalid `defaultLocale` stops only this plugin.
- `plugins/Giveaway/lang/<locale>/text.yaml` holds the texts v3 wrote in code; operators can edit
  them.
- A post button without a giveaway ID answers `Giveaway not found.` in the user's language.
- v3's `plugins/Giveaway/data/*.json` are not read: the giveaways made by v3 are not found after
  the switch until the deferred migration copies them (B11).

### Packaging and the probe

`uv build --package xincord-plugins` ships `giveaway/config.yaml` and the 30 lang files, and the
entry point `Giveaway = xincord.plugins.giveaway`; `xincord --no-online` in an empty directory with
`plugins: [Giveaway]`, from a scratch venv holding both wheels, wrote the 31 files, loaded the
plugin and exited 0. A scratch probe (not committed) drove the plugin through discord.py's own
objects, recording HTTP: the command deferred ephemerally (type 5, flags 64) and edited
`@original` into the builder; set-title answered with a type-9 modal whose input sits in a
label (type 18); the modal submission, a `discord.Interaction` with the builder as its message,
updated the builder with type 7; the confirmation deferred (type 6), posted
`POST /channels/5/messages` and edited `@original` into `create-finished` with empty embeds and
components; Join / Leave and Draw Winners answered with type 7 and an ephemeral follow-up (flags
64); a v3 `giveaway@a:reroll;c:<id>` reached the plugin, after which the core fetched the message
and upgraded its IDs; the automatic draw sent `PATCH /channels/41/messages/777` and
`POST /channels/41/messages` without a fetch. Every message carried the core's allowed mentions
(users only).

### Inventory audit

Every section of `docs/porting/analysis/inventory/Giveaway.md` maps to this change:

- Overview (1): the entry object and `info.yaml` are "The plugin installs as Giveaway" ("Discovered
  by name"); `component_prefix: giveaway@` is `IDS`'s legacy prefix ("v3's posts keep working");
  no intents is `INTENTS`.
- Lifecycle (2): exporting the lang files and reading the config are "First load creates the files"
  and "The config keeps v3's keys"; the first-touch loading of every data file and template is gone
  (the store is read when needed; a "v3 behaved differently" entry); `enabled` is the core's
  `plugins` list; the `defaultLocale` resolution is "Invalid values" and "Locale without lang
  files"; the `StringLocalizer` is the Translator; the scheduler's start, clamp, five-second delay,
  `runCatching` and stop are "Due giveaways are drawn automatically" ("First pass", "Later
  passes", "Failed pass", "Unload") and "Clamped interval"; the drafts that survived v3's plugin
  reload are dropped by xincord's reload (kept: drafts are memory, as v3's full reload).
- Slash command (3): the definition is "Command payload"; the core's defer is "Command callback";
  the unreachable `guild == null` branch is a guard (`test_outside_guild`); the session that
  replaces an older one is "New draft"; the first render is "Builder".
- Components (4.0): the codec is `IDS` with v3's fields and prefix; the routing table is `handle`
  ("v3's post", "v3's builder", "Other actions"); malformed IDs are logged by the core; select menus
  and unknown actions get no response, as in v3.
- Builder (4.1): v3's rows, styles and labels are "Builder" (golden data); the preview is "The
  preview shows the draft"; the language rules are "Each message uses one language" (v3's mixed
  languages are a difference); rendering through the command's hook is fixed (each interaction
  answers); who can press and the session-expired reply are "Only the latest builder of a draft
  works"; the sub-actions are "Builder buttons open pre-filled modals", "The builder removes prizes
  and switches the winner policy", "Confirming checks the draft and the administrator",
  "Confirming posts the giveaway" and "Cancelling ends the draft".
- Modals (4.2): the labels, the value and placeholder set only when non-blank and no `min_length`
  are the core's `render_modal` (checked in `test_modals.py`); the modal table is golden data; the
  pre-fill is "Title modal", "End time modal", "Prize modal" and "Typed placeholders" (v3's
  recursive substitution is a difference); the core placeholders of the press are
  `test_interaction_values`; submissions, Kotlin's trim and the validation table are "Submitted
  modals change the draft" and "Trimmed values"; the unknown sub-action is a difference; end-time
  parsing is "End times are read and shown in the configured zone" (years past 9999 a difference);
  winner counts and thumbnail URLs are "Winner counts" and "Thumbnail URLs".
- Confirm (4.3): v3's order of checks is "Incomplete draft" and "Not an administrator"; the
  unreachable `Guild not found.` is left out (guild-only); `deferEdit`, the ID, the instance, the
  post, the store after the post and the deleted post are "Posted", "Double press", `test_new_ids`,
  "Channel refuses" and "Store fails"; `create-finished` is "Posted"; `create-failed`, the orphaned
  session and the silent synchronous failures are differences ("A giveaway that cannot be posted
  keeps the builder").
- Post (4.4): the creator's language, the embed, the colors, the status, the fields, the clipping,
  the thumbnail, the footer and the buttons are "The post shows the giveaway" (golden data, "Long
  texts"); `resolveGiveaway` is "Unknown giveaway" (`Guild not found.` and `Invalid giveaway id.`
  fold into it: a difference); participate is "Members join and leave"; draw, reroll, permissions,
  rejections and `draw-result` are "The creator or an administrator draws and administrators
  reroll"; mentions in an ephemeral result or an embed never ping.
- Expiry (4.5): drafts without a time limit are kept; the 15-minute builder is fixed; the posts'
  buttons are permanent through the store and the routes.
- Events (5): the slash command, button and modal routes are above; select menus get no response;
  the guild leave is "Leaving a guild drops its drafts" (the deleted file is a difference).
- Configuration (6): `enabled`, `defaultLocale` and `autoDrawIntervalSeconds` are "The config keeps
  v3's keys"; kaml's strict mode is the core's unknown-key warning.
- Localization (7): the locales, the fallback and the hard-coded texts are `text.yaml` and "Each
  message uses one language"; the files are "First load creates the files"; the content templates
  are `create-finished`, `create-failed`, `create-cancelled`, `draw-result` and `auto-draw-result`
  in "Posted", "Channel refuses", "Cancelled", "Draw" and "First pass"; the `ga@*` keys keep v3's
  names.
- Persistence (8): the document per guild, its schema and defaults and v3's example are "Giveaways
  are stored as v3's documents"; the writes (create, join, draw, auto draw) run under the guild's
  lock; the non-atomic whole-file write, the re-save at load and the reset of broken files are
  differences; no retention, as in v3; the deletion at the leave is a difference; the migration is
  deferred (B11), and the documents keep v3's shape for it.
- External dependencies (9): `java.time` is `times.py`, `java.net.URI` `inputs.is_http_url`,
  `UUID` `model.new_id` and `Random.Default` `random.SystemRandom`.
- Discord requirements (10): no intents; the permissions are in the smoke checklist; the automatic
  draw no longer needs Read Message History (no fetch), the core's upgrade of v3 posts does (a
  risk); mentions follow B19; joins answer with interaction responses instead of channel edits.
- Concurrency (11): the races are fixed by the guild's lock and the event loop ("Joins at once",
  `test_draws_at_once`, "Double press", `test_new_draft_while_posting`).
- Bugs (12): items 1 to 14, 16 and 18 are "v3 behaved differently" entries; 15 (unknown actions get
  no response, malformed IDs are logged) and 17 (`Ready to draw` rarely shown) are kept, with the
  reason in "Kept from v3"; the dead code (`isReady`, the select handlers, the `runCatching`
  fallback, the unread timestamps, the identical footers) is not ported, except the timestamps,
  which stay in the documents.
- Testability (13): the pure functions are `times.py`, `inputs.py`, `model.py`, `drafts.py` and
  `texts.py`, each with its tests; the Discord doubles are `discord_fakes` and the scene.

## Risks / Trade-offs

- In Docker the host's zone is UTC unless `TZ` is set, so end times typed by Taiwanese
  administrators would be read 8 hours off: the operator should set `timeZone: Asia/Taipei` (the
  owner review lists it).
- Drafts live in memory: a reload or a restart drops them, as v3's restart did.
- The automatic draw reads every guild's document at each pass (60 seconds by default); the
  documents keep every giveaway forever, as v3's files did.
- A burst of joins sends one interaction response per press; each renders the stored count, so
  two responses that cross may show a count one behind until the next press.
- A pass that is cancelled (an unload) after storing a draw and before posting it leaves that
  giveaway drawn without an announcement; the next press on its post shows the winners.
- The core's upgrade of a v3 post fetches the message and needs Read Message History; without it
  the core logs the failure, and the post's own updates replace the IDs anyway. The upgrade edits
  the components of the copy it fetched, so an edit that lands between its fetch and its edit (an
  automatic draw, another press) can get its buttons reverted until the next press; it matters
  only for v3 posts with stored giveaways, after the deferred migration (B11), and is the core's.
- `Store.put` encodes a document on the event loop: a guild with very many stored participants
  delays other interactions for the time of a `json.dumps`, which the acknowledgement keeps within
  Discord's limit.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [Giveaway]` and `timeZone: Asia/Taipei` in
`plugins/Giveaway/config.yaml`; a text channel `#giveaways`, a thread in it, and two accounts (an
administrator and a member). The bot needs View Channel, Send Messages (in threads too) and Embed
Links there.

1. Start the bot: the log lists `Giveaway` as loaded, and `plugins/Giveaway/config.yaml` and the 30
   lang files exist.
2. As the member, the command list does not show `create-giveaway`. As the administrator, run
   `/create-giveaway` in `#giveaways`: an ephemeral green `Giveaway Draft` embed with `Not set`
   and ten buttons in four rows.
3. Press each set button and submit: a title, a description, the end time two minutes ahead
   (`yyyy-MM-dd HH:mm` in Taipei time), a sponsor and an image URL; add two prizes (2 and 1
   winners), remove one and add it back, and switch the policy twice. Each submission updates the
   same message; a blank title, `2026-1-5 9:00`, a past time, the count 51 and `ftp://x.com` each
   answer v3's error ephemerally.
4. Wait 16 minutes and press a set button and submit: the builder still updates (v3: silently
   stuck).
5. Run `/create-giveaway` again, then press a button of the first builder: the session-expired
   text.
6. Confirm the new draft as the administrator, pressing twice quickly: one post with Join / Leave,
   Draw Winners and a disabled Reroll; the builder says it was created, with the post's link.
7. As the member, press Join / Leave twice: the post's participant count goes 1, 0, with
   ephemeral joined and left texts; press it again to join. As the member, press Draw Winners:
   the not allowed text.
8. After the end time, within a minute, the post turns gray with the winners and the channel gets
   the announcement, pinging the winners. Press Join / Leave: closed.
9. As the administrator, press Reroll: new winners in the post and the ephemeral result.
10. Create a giveaway inside the thread and let it end: it is refreshed and announced in the thread.
11. Remove Send Messages from the bot in a channel and confirm a giveaway there: the builder stays
    and an ephemeral `create-failed` names the error.
12. Restart the bot after a giveaway's end time passed while it was stopped: about five seconds
    after it is ready, the giveaway is drawn and announced.
13. Switch the administrator's client to zh-TW and en-GB: the builder and its modals are zh-TW,
    then English throughout. A giveaway created in zh-TW shows zh-TW texts to every member.
14. Remove the bot from the guild and invite it back: the giveaways are still there and can be
    rerolled.
