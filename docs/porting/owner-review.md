# Owner review queue

Changes pushed while the owner was away, for review afterwards. Each plugin port adds one section
with what the owner has not seen yet:

- **User-visible changes:** copy, commands, options, permissions and interaction flows that differ
  from v3 or are new.
- **Choices made without the owner:** questions the inventory and `decisions.md` did not settle,
  the option implemented, and the alternative.
- **Manual checks:** what needs a real guild, a token or Docker (the smoke checklist lives in the
  archived change's `design.md`).

When the owner answers an item, record the answer in `HANDOFF.md` section 6 and delete the item
here; delete a section once it is empty.

## _Example (`port-example`)

### User-visible changes
- `/example-command` replies with a third embed field, `Config value`, showing `example_key` from `plugins/_Example/config.yaml` (zh-TW name in the plugin's `lang/zh-TW/message/example.yaml`).
- A new `Count: 0` button under the reply counts presses (zh-TW label in `lang/zh-TW/message/counter.yaml`).
- `option1` accepts at most 1024 characters; v3 gave no reply above that.
- Option text is shown as typed (v3 expanded `%...%`), and the command answers in threads, voice channel chats and announcement channels (v3 gave no reply there).
- `example_key` is optional (default `example_value`); a v3 config's `enabled` key now logs an unknown-key warning.
### Choices made without the owner
- Whether _Example gets an entry point: implemented yes (`_Example = "xincord.plugins.example"`), inert unless `plugins` lists it, as v3 shipped it disabled; alternative: copy-only code that operators cannot enable.
- What the template adds to v3's sample: implemented a used config value (`example_key` in the reply) and a counter button whose count lives in its component ID; alternative: v3's unused `example_key` and no component.
- v3 plugin config files: implemented keeping v3's YAML keys so v3 files load, with `enabled` only warning; alternative: make `migrate_v3` strip `enabled` from every plugin config.
- Where v3's `Placeholder.get(event)` lives: implemented `placeholder_values` in the plugin, to move into `xincord.core.placeholders` when a second plugin needs it; alternative: a core helper now.
- How commands are built: implemented `app_commands.Command` in `setup` with the cog's bound method as callback and `rename`/`describe` applied to it; alternative: a nested callback function, without the cog as binding.
- Test layout: implemented `tests/plugins/<package>/`, golden data in `tests/fixtures/plugins/<package>/golden.yaml`, fakes in `tests/support/discord_fakes.py` and the `store` fixture in `tests/conftest.py`; alternative: fixtures and fakes next to each plugin's tests.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-example/design.md` (needs a token and a test guild).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `_Example` enabled); an image build with the plugin enabled is still open.

## BasicCalculator (`port-basic-calculator`)

### User-visible changes
- `formula` takes at most 1018 characters; values over 50,000 digits and results over 1018 characters fail with `Too many digits` (v3: no reply).
- New error messages, English in every locale like v3's: `Division by zero`, `Exponent must be an integer`, `Too many digits`, `Formula too long`.
- `%...%` in a failing formula is shown as typed (v3 expanded it, and `%bc_question%` gave no reply).
- When the bot cannot post in the channel, the answer replaces the ephemeral "thinking" response (v3: "thinking..." forever).
- `%bc_answer_round%` is the part before the decimal point (v3: the whole answer); the shipped templates do not use it.
- The en-US `formula` description says the multiplication sign can be omitted (v3: "bracket is ignorable"); existing `plugins/BasicCalculator/lang/` files keep v3's text unless renewed with `--force-renew-lang-resources`.
- No `plugins/BasicCalculator/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
### Choices made without the owner
- Size limit: implemented 50,000 digits per value (admits `(1+1/1000)^1000`, refuses `(1+1/10000)^10000`) and a worker thread; alternative: a larger limit or a timeout.
- Error messages: kept English in every locale, as v3's; alternative: localized texts in the lang files.
- A channel that refuses the message: implemented the answer in the deferred ephemeral response; alternative: an error message, or a public interaction reply instead of a channel message.
- `%bc_answer_round%`: implemented the part before the decimal point, which v3's `split('.')` meant; alternative: round half up, or drop the key.
- `formula` length: implemented 1018 characters, which fit the code fence in a 1024-character embed field; alternative: Discord's 6000 with an error above 1018.
- Non-ASCII digits (`３`, `١٢`): kept v3's `Unknown Token` error; alternative: read them as digits.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-basic-calculator/design.md` (needs a token and a test guild).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `BasicCalculator` enabled); an image build with the plugin enabled is still open.

## AutoRole (`port-auto-role`)

### User-visible changes
- Roles are added one by one to the member's roles instead of replacing them all (v3 removed a role that another bot gave at the join if it landed first).
- A role that cannot be given (missing, another guild's, managed, `@everyone`, not below the bot's highest role) is skipped with a log warning and the others are given (v3 gave none); without Manage Roles, one warning names the guild.
- Roles created and guilds joined after startup work without a reload (v3 resolved the roles once, at the first join).
- When the bot is ready, and after a reload, warnings name configured guilds the bot is not in, a missing Manage Roles and roles it cannot give (v3 logged nothing for unknown role IDs).
- The bundled `plugins/AutoRole/config.yaml` lists no guilds and shows placeholder IDs in a comment (v3 shipped real guild and role IDs, disabled); a v3 file loads unchanged and warns `unknown key enabled`.
### Choices made without the owner
- How roles are added: implemented one atomic add-role request per role, which never removes a role; alternative: one request for all roles as v3 (`add_roles(atomic=False)`), cheaper under rate limits but able to drop a role given at the same moment.
- A guild listed twice: implemented v3's last entry wins; alternative: reject duplicates when the config loads, or merge their roles.
- Members who have not passed membership screening: implemented roles at the join, as v3; alternative: wait until they pass.
- Config problems: implemented warnings when the bot is ready, on a reload into a ready bot and at each join; alternative: warnings at joins only.
- Validation: kept v3's (`guilds` required, positive `guild_id`, at least one role ID, role IDs any integers); alternative: positive role IDs only.
- Member chunking: kept discord.py's default, which downloads every guild's members before ready once the members intent is on (v3 did not chunk); alternative: `chunk_guilds_at_startup=False` in the core.
- Audit log: no reason on the role requests, as v3; alternative: a reason such as `AutoRole`.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-auto-role/design.md` (needs a token, a test guild and a second account).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `AutoRole` enabled); an image build with the plugin enabled is still open.

## BotInfo (`port-bot-info`)

### User-visible changes
- `/bot-info` shows a third embed field, `Source Code`, with `source_url` from `plugins/BotInfo/config.yaml` (decision C3; zh-TW name in the plugin's `lang/zh-TW/message/bot-info.yaml`).
- An invalid `source_url` (not http or https, spaces, over 512 characters) disables BotInfo with an error that names the key; a v3 `config.yaml` (`enabled` only) loads with the default URL and warns `unknown key enabled`.
- v3 lang files kept in `plugins/BotInfo/lang/` show v3's embed without the source field until renewed with `--force-renew-lang-resources` (which renews every enabled plugin's lang files) or edited.
- The command always answers (v3 needed the core's auto-defer switch), and guilds that are unavailable during a Discord outage still count as guilds (JDA left them out).
### Choices made without the owner
- Where the link shows: implemented a third embed field in both locales; alternative: a link button under the embed, or a link on the embed title.
- URL check: implemented http or https without spaces and at most 512 characters (Discord's link-button limit), checked at load; alternative: any text, unchecked.
- Current member counts: implemented the privileged members intent, so the counts follow joins and leaves as in v3; alternative: no privileged intent, with counts as of the last connection.
- Member count: kept v3's per-guild sum (users in several guilds counted once per guild, bots included); alternative: unique users from the member cache.
- Unavailable guilds: counted, with the members discord.py knew (none if unknown); alternative: left out of both counts, as JDA did.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-bot-info/design.md` (needs a token and a test guild).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `BotInfo` enabled); an image build with the plugin enabled is still open.

## SimpleCommand (`port-simple-command`)

### User-visible changes
- When the bot cannot post in the channel (missing permissions, or a channel that takes no messages), the administrator gets the message as the ephemeral response and the log has a warning (v3: the "thinking" message vanished and nothing was posted).
- The commands always answer (v3 needed the core's auto-defer switch).
- No `plugins/SimpleCommand/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
- Placeholders that other plugins left in v3's shared global substitutor no longer expand in these templates; `%bot_id%` and `%bot_name%` still do.
### Choices made without the owner
- A channel that refuses the message: implemented the message in the deferred ephemeral response, as BasicCalculator; alternative: an error text telling the administrator that the bot cannot post there.
- What is posted: implemented the whole template, as v3 posted the built message (an operator's link buttons, Components V2 layouts and their uploaded files too); alternative: content and embeds only, as BasicCalculator posts.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-simple-command/design.md` (needs a token, a test guild and a member without Administrator).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `SimpleCommand` enabled); an image build with the plugin enabled is still open.

## WelcomeByeGuild (`port-welcome-bye-guild`)

### User-visible changes
- The four commands answer in threads, voice channel chats, stage and announcement channels (v3: no reply, and a bind chosen with the `channel` option there was saved silently); without the option there, the reply is `invalid-channel`.
- `%...%` in member, guild and channel names is shown as written in replies and in the welcome and bye messages (v3 expanded it, and a self-reference stopped the message).
- The bye message can use the `wbg@member_*` keys and v3's unprefixed member keys when discord.py still knew the member (v3: never; they stayed as written).
- Bindings of guilds the bot left while it was offline or while the plugin was off are deleted when the bot is ready, with one log line per guild (v3 kept their files).
- A welcome or bye message that Discord refuses logs a warning that names the guild and the channel (v3: JDA's exception log).
- `invalid-channel`, `*-bind-already` and `*-unbind-empty` no longer create data; the commands always answer (v3 needed the core's auto-defer switch).
- No `plugins/WelcomeByeGuild/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
### Choices made without the owner
- Where the bindings live: implemented v3's document per guild in the store's key-value table (namespace `WelcomeByeGuild`, key = guild ID), so that a later migration can copy v3's files; alternative: a plugin table with one column per channel.
- Bye message keys: implemented the member keys when discord.py still knew the member; alternative: v3's user-only keys.
- Bindings of guilds left while offline or disabled: implemented their deletion when the bot is ready; alternative: keep them until the bot leaves that guild again, as v3.
- A channel where the bot cannot post: implemented v3's unchecked bind, with a log warning at each refused message; alternative: check View Channel, Send Messages and Embed Links when binding and tell the administrator (new copy).
- `guild-only`: kept as a guard that guild commands never reach, rendered with the interaction's placeholders like `no-permission` (v3: global ones only); alternative: drop the check and its two templates.
- Core API: implemented `placeholder_values(interaction)` (Protocols `EventLike`, `ClientLike`) in `xincord.core.placeholders`, moved from _Example, which now imports it; alternative: a copy per plugin.
- Core fix: `interaction_values` gives no `channel_category_name` for a thread whose parent channel discord.py has not cached, where it raised and left the command unanswered (found by a probe through discord.py's own objects); alternative: none.
- Core gap found in the audit, unchanged: v3's commons-text read `%key:-fallback%` as a fallback for a missing key, while the core's `render` leaves it as written (no shipped template uses it); alternative: support the syntax in `render`.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-welcome-bye-guild/design.md` (needs a token, a test guild and a second account).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `WelcomeByeGuild` enabled); an image build with the plugin enabled is still open.

## IntervalPusher (`port-interval-pusher`)

### User-visible changes
- The plugin shows nothing in Discord: the changes are in `plugins/IntervalPusher/config.yaml` and the log.
- The bundled `config.yaml` lists no listeners and shows an example on `status.example.com` in a comment (v3 shipped one listener on `status.xinshou.tw` with a placeholder token, disabled); a v3 file loads unchanged and warns `unknown key enabled`.
- An `interval` below 1 (v3: a busy loop) or a `url` that is not an http or https URL with a host (v3: an error at every push) disables the plugin at load, with the key named.
- `%ping%` is measured only for URLs that contain it (v3 asked Discord at every push).
- Stopping or reloading the plugin no longer logs a spurious error.
- New English log lines number the listener (`IntervalPusher listener 1 started (every 60 s)`, `IntervalPusher listener 2 stopped: the status monitor refused the push (code 404)`), at v3's levels.
### Choices made without the owner
- Bundled config: implemented no listeners and a commented example on `status.example.com`; alternative: v3's sample listener on the owner's status domain with a placeholder token.
- `%ping%`: implemented v3's REST ping, a timed `GET /users/@me` through discord.py's undocumented `HTTPClient.request` and `Route`; alternative: discord.py's public gateway latency (`bot.latency`), a different quantity.
- HTTP client: implemented aiohttp, already installed with discord.py and now declared by `xincord-plugins`; alternative: httpx, a new dependency.
- Interval range: implemented 1 to 2147483647 seconds (v3's `Int` without zero and negatives); alternative: a larger minimum, such as 10 seconds.
- URL check: implemented an http or https URL with a host and no spaces, checked at load; alternative: v3's unchecked URL, which fails at every push.
- When pushing starts: implemented at READY (at once when the plugin loads into a ready bot), so that the monitor shows the bot as up only once it is connected; alternative: at load, before the gateway connects.
- Redirects: kept v3's behavior of not following them (a 3xx logs an error); alternative: follow them, so that an `http://` URL redirected to `https://` works.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-interval-pusher/design.md` (needs a token and an Uptime Kuma push monitor or another endpoint that shows its requests).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `IntervalPusher` enabled, with and without a listener); an image build with the plugin enabled is still open.
- After a discord.py upgrade, check that pushes carry a real ping and not `-1`: the ping uses discord.py's undocumented `HTTPClient.request` and `Route`.

## Feedbacker (`port-feedbacker`)

### User-visible changes
- The form is deleted only after its review is posted.
- The pressed star turns blue through an edit of the bot's own message after the modal opens (v3 queued it on the interaction hook before acknowledging the press).
- Feedback text is shown as typed (v3 expanded `%...%` in it, and `%fb_content%` made the modal fail).
- A star count outside 0 to 5 in an operator's template fails the press at once (v3: after the member typed a feedback).
- A v3 `config.yaml` loads unchanged and warns `unknown key enabled`; there the two new replies are English (`Failed to create the form`, `Failed to submit the feedback`) until added; a blank reply or one over 2000 characters disables the plugin with the key named.
- The command always answers (v3 needed the core's auto-defer switch).
- Core, every plugin: embed field names and values are trimmed and an empty one becomes U+200E, as v3 did through JDA (xincord sent them as rendered, and Discord refuses an empty field).
### Choices made without the owner
- A `member` option naming a user outside the server: implemented `form_failure`; alternative: post the form anyway (only that user could press it, after joining).
- A refused review: implemented keeping the form and telling the member; alternative: v3's deletion regardless.
- Star counts: implemented whole numbers 0 to 5 (where v3 did not throw), checked at the press; alternative: clamp them, or allow any count.
- Double submission from two clients: kept v3's two reviews (the second deletion is a logged warning); alternative: a per-form lock that posts only the first.
- The highlight: implemented after the modal, with the bot's token; alternative: through the interaction webhook, as v3 tried.
- Core: JDA's field trimming in the renderer for every plugin (VoiceLogger and ChatLogger rely on it too); alternative: U+200E for the empty feedback in this plugin only.
- Core: `modal_values` in `xincord.core.templates` for every plugin with modals; alternative: a parser in this plugin.
- `TextChannelOption` copied from WelcomeByeGuild (no other v3 command restricts a channel option); alternative: move it into the core.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-feedbacker/design.md` (needs a token, a test guild and a second account).
- This is the first modal xincord sends (a label around the text input, as discord.py builds it): check that it opens in both languages.
- At cutover, add `form_failure` and `form_submit_failure` to the existing `plugins/Feedbacker/config.yaml` for zh-TW texts, and press one star of a v3 form if any remains.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `Feedbacker` enabled, with the bundled and v3's config); an image build with the plugin enabled is still open.

## Economy (`port-economy`)

### User-visible changes
- A user whom `admin_id` does not list and who names someone else in `/balance` gets `no-permission` (v3: their own wallet, without a word).
- `/balance` and `economy@` buttons no longer create a zero wallet, so members appear on `/top-money` and `/top-cost` only once an administrator changed their wallet (v3 ranked everyone who had run `/balance`, at 0).
- Board ties are ordered by user ID, the lowest first (v3: no defined order).
- Amounts stay exact past 2147483647 (v3 wrapped them to negative numbers, and a `value` above that got no reply).
- Every change reply has both `%economy_money_before%` and `%economy_cost_before%` (matters only for operators' templates).
- The bundled `config.yaml` lists no administrator, so Economy stays disabled, with `admin_id` named in the log, until one is added (v3 shipped two real IDs); a v3 file loads unchanged and warns about `enabled` and the eight Google Sheets keys.
- Economy no longer needs the GoogleSheetAPI plugin.
- A `top-money` or `top-cost` template whose first embed has no description disables the plugin at load, naming the file (v3: no reply at each use).
- The commands always answer (v3 needed the core's auto-defer switch).
- An `economy@` button whose ID is not in v3's field format is logged as malformed instead of showing the wallet; no v3 template or production message has one.
### Choices made without the owner
- `admin_id` in the bundled file: implemented an empty list with v3's at-least-one rule, so the plugin waits for the operator; alternative: load with a warning and answer `no-permission` to every administrator command.
- Amount range: implemented exact Python integers without a bound (Discord sends at most 2^53 per change); alternative: keep v3's 32-bit range and refuse results outside it.
- Negative amounts: kept v3's `Bad Value`, English in every locale, after the command runs; alternative: `min_value=0` on the option so that Discord's client refuses them, or a localized template.
- `/balance member:` from a non-administrator: implemented `no-permission` when the member is someone else; alternative: v3's silent fallback to their own wallet.
- Board ties: implemented the lowest user ID first; alternative: the order in which the wallets were first changed.
- Reads: implemented no write for `/balance`, the button and the boards; alternative: v3's zero wallet on the first read, which put the member on the boards.
- Before values: implemented both in every change reply; alternative: only those of the amounts the command changes, as v3 set them.
- Wallets of guilds the bot left: kept, as v3 did; alternative: delete them on leave and at startup, as WelcomeByeGuild does.
- Unreadable stored entries: implemented a logged error, the command left "thinking" and nothing overwritten; alternative: read them as 0, which the next change would write over.
- The `economy@` button (no producer in v3's templates or the production copy): kept for IDs the core's v3 decoder reads, any fields ignored; alternative: drop it.
- Core: `global_values(client)` in `xincord.core.placeholders`, now used by BotInfo, SimpleCommand and Economy's `no-permission` (v3 rendered it with its global keys only); alternative: render `no-permission` with the user's values, without a core change.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-economy/design.md` (needs a token, a test guild and a second account).
- At cutover, keep the existing `plugins/Economy/config.yaml` (it lists the administrators); its `enabled` and Google Sheets keys can be deleted to silence the warnings.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `Economy` enabled, with the bundled, an operator's and v3's config); an image build with the plugin enabled is still open.

## DynamicVoiceChannel (`port-dynamic-voice-channel`)

### User-visible changes
- `/dynamic-voice-channel bind` and `unbind` work: since 2026-01-13 (v3 commit `ea14fbf`) they never answered, so bindings could only be added by editing `plugins/DynamicVoiceChannel/data/*.json`.
- The `channel` options list voice channels only (v3 offered every channel and gave no reply for the others).
- Binding a lobby again replaces its formats (v3 added a duplicate that won until the next restart).
- A lobby whose copy Discord refuses stays a lobby, and the log says why (v3 deleted the lobby once it emptied and dropped its binding at the next start).
- A member who leaves a new room at once no longer leaves an orphan room; rooms that emptied while the bot was offline are deleted when it is ready.
- A refused step no longer skips the others: without Manage Roles the room is still renamed and moved (with a warning), and a format that renders blank or over 100 characters keeps the room's old name but still moves it and gives the member their permissions.
- The new lobby keeps the lobby's NSFW flag, video quality and slowmode (v3's copy lost them).
- A room costs four requests instead of three: the member's permissions are a separate `PUT`.
- Stage channels named like a lobby are ignored (v3 threw); a room that kept the lobby's name is never copied as a lobby.
- Leaving a guild also deletes its rooms' records, and a guild unavailable at startup keeps its bindings (v3 deleted them).
- The en-US `unbind-fail` title reads `Unbind fail, the channel was not found in settings` (v3: `is not be found`); existing `plugins/DynamicVoiceChannel/lang/` files keep v3's text.
- No `plugins/DynamicVoiceChannel/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list; the plugin no longer needs SQLiteAPI.
### Choices made without the owner
- Where the rooms live: implemented one document per guild, `{"<room ID>": <owner ID>}` under `DynamicVoiceChannel.rooms`; alternative: one entry per room keyed by its ID, like v3's MongoDB documents (which hold no guild), or a plugin table.
- When a room is tracked: implemented once the lobby's copy exists; alternative: only after every step succeeded (a failed rename would then leave a second lobby for good).
- Positions: implemented JDA's raw `PATCH /channels/<id>` with positions 0 and 1 through discord.py's internal `HTTPClient.request`; alternative: discord.py's `edit(position=...)`, which renumbers every voice channel of the guild in one bulk request.
- The member's permissions: implemented a separate `PUT` of their overwrite, which keeps the others; alternative: v3's single PATCH with the whole overwrite list and the name.
- Unusable room names: implemented keeping the old name with a warning; alternative: cut the name to 100 characters.
- `format-name-2`: kept required, stored and unused, as in v3; alternative: make it optional or drop it.
- Stale bindings: kept v3's removal at startup (category gone, or no voice channel with the lobby's exact name), now also on a load into a ready bot; alternative: keep them until unbound.
- A guild's voice changes: implemented one after another under a per-guild lock, so a room's creation that Discord rate-limits delays the guild's other joins and leaves; alternative: no lock, with v3's orphan rooms.
- A join handled after the member already left the lobby creates no room; alternative: v3's room regardless, deleted right after.
- Copy: implemented the grammar fix above; alternative: keep v3's text.
- `VoiceChannelOption`: a third copy of the channel transformer (WelcomeByeGuild and Feedbacker have text ones); alternative: a core `ChannelOption(types)`.
- Unreadable stored documents: implemented an error without overwriting them (the commands stay "thinking", READY skips the guild); alternative: read them as empty, which the next change would overwrite.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-dynamic-voice-channel/design.md` (needs a token, a test guild and a second account).
- The bot needs Manage Channels and Manage Roles (or Administrator) in the bound categories.
- Check that positions 0 and 1 put the new lobby at the top of its category and the room right below, as in v3 (the raw PATCHes are v3's requests; Discord's ordering of equal positions was not observed).
- At cutover, delete v3's leftover rooms by hand (only v3's MongoDB knows them).
- Two members who join an empty lobby at the same instant may both stay in the lobby without a room (discord.py may parse both joins before the plugin sees the first); watch whether it happens.
- After a discord.py upgrade, check the room requests: the positions use discord.py's undocumented `HTTPClient.request` and `Route`.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `DynamicVoiceChannel` enabled); an image build with the plugin enabled is still open.

## VoiceLogger (`port-voice-logger`)

### User-visible changes
- `/voice-logger setting` answers in every channel (voice and stage chats, threads, announcement channels), which can then be listen channels (v3: no reply outside plain text channels).
- A listen channel's first allow or block selection keeps the allow mode after a restart (v3 switched it to the block mode, which logs every voice channel); "Delete" deletes only that channel's settings (v3: the guild's whole file, so the guild's other listen channels lost theirs at the next restart).
- The switch embed's `Channel Join` shows the joined channel (v3: an earlier join's channel or the placeholder); a channel outside categories shows `-` in the category fields (v3: an earlier event's category or the placeholder).
- A status change names the member of its own audit log entry (type 192 for a set or changed status, 193 for a cleared one, same channel, within 30 seconds, not an entry of an earlier status); without one (a status that Discord clears by itself, no View Audit Log, a member who left) the log shows `-` and no thumbnail (v3: whoever last set any status in the guild, or no log at all).
- As in v3, statuses set before the bot's session started (or the plugin reloaded) are unknown: their first change is logged as a new status, and their clear is not logged.
- A channel's status logs keep their order, even when one waits 2 seconds for its audit log entry.
- A listen channel that refuses a log no longer stops the others (a warning in the bot's log); a deleted listen channel is forgotten at its next log.
- A list longer than 1024 characters ends with `...` instead of breaking that channel's menu for good.
- Channel names and statuses are shown as written (v3 expanded `%...%` in them).
- Settings of a guild the bot leaves are deleted at once, and deleted channels are dropped from the lists when the bot is ready (v3 did both at its next start).
- No `plugins/VoiceLogger/config.yaml`.
### Choices made without the owner
- Status events, which discord.py 2.7.1 drops: implemented a core method, `Bot.relay_gateway_event(name)`, that adds a parser to discord.py's internal parser table and dispatches `gateway_voice_channel_status_update`; alternative: `enable_debug_events=True` with discord.py's public `on_socket_raw_receive` (every gateway message parsed twice), or `on_audit_log_entry_create` with the moderation intent (discord.py drops the channel and the status of types 192 and 193).
- Earlier statuses: implemented tracking them in memory from the events, unknown ones empty, forgotten at each READY and when a guild becomes unavailable or is left, as JDA's cache; alternative: Discord's Request Channel Info (gateway opcode 43) for each guild at READY.
- Attribution: implemented the newest audit log entry of the change's type and channel within 30 seconds, leaving out type-192 entries of another status, the same status first, read again once after 2 seconds; alternative: v3's newest type-192 entry of the guild, a longer wait, or also bounding the entries by the channel's previous event.
- A change without an entry: implemented the log with `-` as the member; alternative: no log, as v3 when the audit log had no type-192 entry.
- A channel without a category: implemented `-`; alternative: an empty field.
- Long lists: implemented the lines that fit and `...`; alternative: refusing additions past the limit (new copy).
- Listen channels: implemented any channel where the command runs; alternative: text and voice channels only, as v3's code intended, with a new refusal message.
- Posting: implemented partial messageables (no cache), a 404 forgetting the listen channel; alternative: v3's cache lookup, skipping missing channels.
- Checks at READY: kept v3's pruning of left guilds and of deleted list entries; deleted listen channels are forgotten at their next log instead (an archived thread is not cached at READY); alternative: v3's start-up pruning of missing listen channels.
- Leaving a guild: implemented deleting its settings at once; alternative: v3's deletion at the next start.
- Core API: `Bot.relay_gateway_event` (spec delta on `core-plugins`, tested in `tests/core/test_gateway.py`); alternative: a VoiceLogger-only hook into discord.py.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-voice-logger/design.md` (needs a token, a test guild and a second account).
- The bot needs View Audit Log for the members of status changes, and View Channel, Send Messages and Embed Links in the listen channels.
- Unverified without a real guild: Discord's `VOICE_CHANNEL_STATUS_UPDATE` payload (null or empty for a cleared status), whether Discord sends it when it clears a status by itself, whether type-192 and 193 entries carry `options.channel_id` and `options.status` as documented (or the channel in `target_id`), whether `options.status` is exactly the gateway's text (if not, set statuses show `-`), and how soon after the gateway event the entries exist.
- After a discord.py upgrade, check the relay (discord.py's internal `ConnectionState.parsers`) and the audit log request (`HTTPClient.request` and `Route`); if discord.py starts parsing the event, the relay still runs after its parser.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `VoiceLogger` enabled); an image build with the plugin enabled is still open.

## ChatLogger (`port-chat-logger`)

### User-visible changes
- A deleted message's text leaves the store once its deletion is handled (v3 kept it).
- `log_all: false` stores the messages of the channels that a listen channel detects (v3: only the channels that had a table already, a set no setting changed); with it, a guild's stored messages are deleted when the bot leaves the guild.
- Edits and deletions in threads are logged (v3: never); a thread is detected through its parent channel and that channel's category, or by its own ID, in both modes (v3's block mode never detected threads). Archived threads stay in the lists after a restart.
- Bulk deletions (purges) are logged, one embed per stored message, oldest first (v3: not at all); a listen channel that is gone or refuses is tried once per purge.
- Deletions of messages whose author left, and of webhooks' messages, are logged with the stored author's mention, `-` and no thumbnail (v3: not logged).
- Updates that keep the text (a pin, a link preview, rich previews of members' links included, suppressed embeds) are no longer logged or counted as edits; an edit that arrives together with its message is logged with the text the message was sent with.
- A message's text keeps its content when it has embeds and no longer holds `null`; a member's message is its content only (its embeds are link previews), a bot's or a webhook's adds its rich embeds.
- Texts longer than 1024 characters are cut with `...` (v3 lost the log); texts are shown as written (v3 expanded `%...%`, and `%cl_msg_after%` in a message made its log fail).
- A webhook's edit shows the webhook's mention (v3: the placeholders themselves); a channel without a category shows `-`.
- As in VoiceLogger: the menu answers in every channel, and logs reach listen channels of every kind; a deleted listen channel is forgotten and a refusing one no longer stops the others; a first selection keeps the allow mode; "Delete" deletes only that channel's settings; long lists end with `...`; settings of a guild the bot leaves are deleted at once.
- The bundled `config.yaml` explains both keys and the Message Content intent (English comments).
### Choices made without the owner
- Deleted messages: implemented removing their text once the deletion is handled; alternative: keeping it until the retention, as v3 kept it.
- Threads: implemented detection through the parent channel and its category, or the thread's own ID; alternative: the thread's own ID only, as v3's allow mode.
- Bulk deletions: implemented one embed per stored message; alternative: one summary embed per purge (a new template and new copy).
- Edits: implemented logging only a change of the text, a member's text being its content; alternative: every update, as v3, or telling previews apart by `edited_timestamp`.
- Reading new messages: implemented the relayed `MESSAGE_CREATE` payload (`bot.relay_gateway_event`), because discord.py's `on_message` object takes an edit parsed together with it in place, and the edit's log was lost; alternative: `on_message`, losing such edits.
- Authors who are no members: implemented the stored ID's mention, `-` and no thumbnail; alternative: fetching the user (`fetch_user`) for the name and the avatar, one more request.
- Left guilds with `log_all: true`: implemented keeping their messages until the retention, as v3 kept them; alternative: deleting them at the leave whatever `log_all` says.
- Shared code: implemented `xincord.plugins.listen_channels` (settings, store, menu, posts, checks) for VoiceLogger and ChatLogger; alternative: two copies, as v3 had.
- The READY check of the lists (both plugins): implemented asking Discord about each listed ID that discord.py has not cached and dropping it only on a 404, so archived threads stay; alternative: v3's dropping of every uncached ID, which unblocks a blocked thread after a restart.
- Operator templates that put text around `%cl_msg_before%` or `%cl_msg_after%` (or move them into a title or the content) can exceed Discord's limits, and the log is then refused with a warning: implemented fitting the bare values only, as the shipped templates show them; alternative: clamping every rendered text in the core's renderer, for every plugin.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-chat-logger/design.md` (needs a token, a test guild and a second account).
- Turn the Message Content intent on for the bot in the Discord developer portal (Bot, Privileged Gateway Intents) before enabling ChatLogger: without it, Discord refuses the bot's connection.
- The bot needs View Channel and Read Message History in the logged channels, and View Channel, Send Messages and Embed Links in the listen channels.
- Unverified without a real guild: whether Discord sends `MESSAGE_UPDATE` for pins and link previews and which previews it types `rich` (members' are never logged either way; a bot's rich preview would log an edit), and how long a large purge takes to post.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `ChatLogger` and `VoiceLogger` enabled); an image build with the plugin enabled is still open.

## Giveaway (`port-giveaway`)

### User-visible changes
- The builder keeps working after 15 minutes: each press and submission updates it (v3 edited through the command's token and silently stopped after 15 minutes).
- Only the newest builder message of a draft works; an older one, or any after a reload or a restart, answers the session-expired text.
- A second Confirm Create press while the giveaway is being posted answers the session-expired text (v3 posted two giveaways).
- A post that cannot be made (a refusing channel, a channel without messages, a store failure) keeps the builder and the draft and sends `create-failed` with the error as an ephemeral message (v3 turned the builder into it, without buttons).
- Long descriptions and prize lists end with `...` in the preview and the post, and the post's description shortens so that the embed fits Discord's 6000 characters (v3: the preview froze, or the post or its refresh failed).
- Join / Leave, Draw Winners and Reroll are acknowledged at once, then update the post through the press; the joined, left, draw-result and refusal replies are ephemeral follow-ups, and any press repairs a post that shows an outdated state (v3 left a post whose refresh failed with Reroll disabled for good).
- The automatic draw refreshes and announces giveaways in threads, announcement channels and voice channel chats too (v3 drew them silently).
- The announcement pings the winners but no roles or @everyone named in a title (B19).
- An uppercase `HTTPS://` thumbnail is shown (v3 accepted it but never showed it).
- A user whose locale has no lang files (en-GB, ja) sees English texts and buttons, a zh-CN user zh-TW ones (v3 mixed English texts with zh-TW buttons).
- Typed `%...%` in titles, descriptions and sponsors is shown as written (v3 expanded it).
- Giveaways stay when the bot leaves a guild (v3 deleted them); due giveaways of a guild that the bot left wait until it is back.
- New config key `timeZone` (an IANA zone, empty for the host's); an invalid `defaultLocale` stops only this plugin, with the key named (v3 aborted the bot).
- New lang files `plugins/Giveaway/lang/<locale>/text.yaml` hold the texts that v3 wrote in code (field names, statuses, replies, errors); operators can edit them.
- A post button without a giveaway ID answers `Giveaway not found.` in the user's language (v3: `Invalid giveaway id.` in English); a modal with an unknown sub-action gets no response.
- End times after 9999 (`+12026-01-05 10:00`) and `9999-12-31 24:00` get the format error.
### Choices made without the owner
- Builder updates: implemented answering each press and submission with `response.edit_message`; alternative: v3's edits through the command's hook (15-minute limit).
- Joins and draws: implemented deferring at once, then editing the post through the press's webhook and replying with ephemeral follow-ups, the post re-rendered on every press; alternative: v3's REST edit of the post and an ephemeral reply, which a burst of joins queues behind the channel's rate limit.
- Drafts: implemented no time limit (one per member and guild, gone at confirmation, cancel, a new command, the guild's leave, a reload or a restart); alternative: drop drafts idle for a day.
- Leaving a guild: implemented keeping its giveaways (rerolls after a re-invite); alternative: v3's deletion.
- Guilds left while offline: implemented drawing their due giveaways when the bot is back; alternative: v3's silent draw without posting.
- Time zone: implemented `timeZone`, empty by default for the host's zone as in v3, which is UTC in the container; alternative: ship `timeZone: "Asia/Taipei"`, or set `TZ` in `compose.yaml`.
- Invalid `defaultLocale`: implemented failing this plugin's load with the key named; alternative: fall back to zh-TW, as v3's code intended.
- Language: implemented one locale per message (the locale's files, else zh-TW for Chinese locales, else en-US); alternative: the configured default locale for every missing locale.
- Hard-coded texts: implemented a new `text.yaml` per locale; alternative: English texts in code for every locale (Python files cannot hold the zh-TW texts).
- Winners: implemented `random.SystemRandom` and `sample`, v3's distribution; alternative: `secrets.SystemRandom` (the same generator).
- Thumbnails: implemented showing any-case http(s) URLs with the scheme in lower case; alternative: refuse uppercase schemes at input.
- End times: implemented years 0001 to 9999; alternative: compute later years by hand.
- The automatic draw's period: implemented counting from the end of each pass; alternative: v3's fixed rate from each start.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-giveaway/design.md` (needs a token, a test guild and a second account).
- Before cutover, set `timeZone: "Asia/Taipei"` in `plugins/Giveaway/config.yaml` (or `TZ` in `compose.yaml`): the container's zone is UTC, so typed end times would be read 8 hours off.
- The bot needs View Channel, Send Messages (in threads too) and Embed Links in giveaway channels; Read Message History only for the core's upgrade of v3 posts.
- Unverified without Discord: that a type-7 response to a modal submission updates the ephemeral builder, and how a burst of joins looks (a response may show a count one behind until the next press).
- Packaging was checked: the wheel's files, `xincord --no-online` from the built wheels, and the compose image (`docker compose run --rm -T bot --no-online` with `Giveaway` enabled), whose Python resolves `Asia/Taipei`.
- After the deferred migration (B11), the core upgrades v3 posts' IDs with a fetch and an edit, which can briefly revert a concurrent edit of the post's buttons; the next press repairs it.
