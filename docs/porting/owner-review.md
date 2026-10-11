# Owner review queue

Changes pushed while the owner was away, for review afterwards. Each plugin port adds one section
with what the owner has not seen yet:

- **User-visible changes:** copy, commands, options, permissions and interaction flows that differ
  from v3 or are new.
- **Choices made without the owner:** questions the inventory and `decisions.md` did not settle,
  the option implemented, and the alternative. Every choice listed up to `release-pipeline` was
  answered on 2026-10-11 (`HANDOFF.md`, section 6) and deleted.
- **Manual checks:** what needs a real guild, a token or Docker (the smoke checklist lives in the
  archived change's `design.md`).

When the owner answers an item, record the answer in `HANDOFF.md` section 6 and delete the item
here; delete a section once it is empty.

## Example (v3 _Example, `port-example`)

### User-visible changes
- `/example-command` replies with a third embed field, `Config value`, showing `example_key` from `plugins/Example/config.yaml` (zh-TW name in the plugin's `lang/zh-TW/message/example.yaml`).
- A new `Count: 0` button under the reply counts presses (zh-TW label in `lang/zh-TW/message/counter.yaml`).
- `option1` accepts at most 1024 characters; v3 gave no reply above that.
- Option text is shown as typed (v3 expanded `%...%`), and the command answers in threads, voice channel chats and announcement channels (v3 gave no reply there).
- `example_key` is optional (default `example_value`); a v3 config's `enabled` key now logs an unknown-key warning.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-example/design.md` (needs a token and a test guild).

## Calculator (v3 BasicCalculator, `port-basic-calculator`)

### User-visible changes
- `formula` takes at most 1018 characters; values over 50,000 digits and results over 1018 characters fail with `Too many digits` (v3: no reply).
- New error messages, English in every locale like v3's: `Division by zero`, `Exponent must be an integer`, `Too many digits`, `Formula too long`.
- `%...%` in a failing formula is shown as typed (v3 expanded it, and `%bc_question%` gave no reply).
- When the bot cannot post in the channel, the answer replaces the ephemeral "thinking" response (v3: "thinking..." forever).
- `%bc_answer_round%` is the part before the decimal point (v3: the whole answer); the shipped templates do not use it.
- The en-US `formula` description says the multiplication sign can be omitted (v3: "bracket is ignorable"); existing `plugins/Calculator/lang/` files keep v3's text unless renewed with `--force-renew-lang-resources`.
- No `plugins/Calculator/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-basic-calculator/design.md` (needs a token and a test guild).

## AutoRole (`port-auto-role`)

### User-visible changes
- Roles are added one by one to the member's roles instead of replacing them all (v3 removed a role that another bot gave at the join if it landed first).
- A role that cannot be given (missing, another guild's, managed, `@everyone`, not below the bot's highest role) is skipped with a log warning and the others are given (v3 gave none); without Manage Roles, one warning names the guild.
- Roles created and guilds joined after startup work without a reload (v3 resolved the roles once, at the first join).
- When the bot is ready, and after a reload, warnings name configured guilds the bot is not in, a missing Manage Roles and roles it cannot give (v3 logged nothing for unknown role IDs).
- The bundled `plugins/AutoRole/config.yaml` lists no guilds and shows placeholder IDs in a comment (v3 shipped real guild and role IDs, disabled); a v3 file loads unchanged and warns `unknown key enabled`.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-auto-role/design.md` (needs a token, a test guild and a second account).

## BotInfo (`port-bot-info`)

### User-visible changes
- `/bot-info` shows a third embed field, `Source Code`, with `source_url` from `plugins/BotInfo/config.yaml` (decision C3; zh-TW name in the plugin's `lang/zh-TW/message/bot-info.yaml`).
- An invalid `source_url` (not http or https, spaces, over 512 characters) disables BotInfo with an error that names the key; a v3 `config.yaml` (`enabled` only) loads with the default URL and warns `unknown key enabled`.
- v3 lang files kept in `plugins/BotInfo/lang/` show v3's embed without the source field until renewed with `--force-renew-lang-resources` (which renews every enabled plugin's lang files) or edited.
- The command always answers (v3 needed the core's auto-defer switch), and guilds that are unavailable during a Discord outage still count as guilds (JDA left them out).
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-bot-info/design.md` (needs a token and a test guild).

## CustomCommands (v3 SimpleCommand, `port-simple-command`, `custom-commands-from-config`)

### User-visible changes
- When the bot cannot post in the channel (missing permissions, or a channel that takes no messages), the administrator gets the message as the ephemeral response and the log has a warning (v3: the "thinking" message vanished and nothing was posted).
- The commands always answer (v3 needed the core's auto-defer switch).
- Placeholders that other plugins left in v3's shared global substitutor no longer expand in these templates; `%bot_id%` and `%bot_name%` still do.
- `custom-commands-from-config`: the commands are defined in `plugins/CustomCommands/config.yaml`; the bundled file lists v3's five (names, `generate message`, zh-TW names and descriptions, Administrator), so a fresh install and a migrated v3 install behave as before. Its comments, which explain every key, are new copy.
- `custom-commands-from-config`: per command, `localizations` (name and description per Discord locale), `template` (default: the command's name), `permissions` (discord.py's names; default `[administrator]`, `[]` for every member), `reply` (`channel`, v3's post; `public`; `ephemeral`) and `guilds` (default: every guild); `/xincord reload CustomCommands` applies an edit and uploads the commands.
- `custom-commands-from-config`: ephemeral replies use the user's locale, else zh-TW; posts and public replies stay zh-TW for everyone.
- `custom-commands-from-config`: templates may use the user's and the channel's placeholders (`%user_mention%`, `%user_name%`, `%channel_name%`, ...), not only `%bot_id%` and `%bot_name%`; a mention in a post pings that member.
- `custom-commands-from-config`: `lang/zh-TW/register.yaml` is no longer bundled or read; a v3 copy is ignored (the local v3 copy's equals v3's bundled file, so nothing is lost).
- `custom-commands-from-config`: a config mistake disables the plugin with the file and the key in the log: Discord's name rules, description lengths, locales, permissions, guild IDs, names unique in every locale, the room left of Discord's 100 commands, a template missing from zh-TW or one that cannot render (a `uid` button or select, a `model_key`, a missing file, six rows).
- `custom-commands-from-config`: a response that Discord refuses is deleted with a warning, so that no public "thinking" message stays in the channel.
- `custom-commands-from-config`: an en-US template for some commands only logs the core's warning at each load that en-US lacks the others; they fall back to zh-TW.
- `custom-commands-from-config`: `python -m xincord.core.migrate_v3` renames v3's `plugins/CustomCommands/config.yaml` (moved from SimpleCommand; only `enabled`) to `config.v3.yaml`, with a report line, so that the bundled commands are written.
- `custom-commands-from-config`: every plugin: a reload whose `config.yaml`, lang files or templates are broken keeps the previous version running, and the summary names the file and the key (before: the plugin vanished while still listed as loaded, and only a restart brought it back); when even the previous version fails, the plugin and the plugins that depend on it are unloaded, the commands are uploaded without theirs, and the summary says to run a full reload.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-simple-command/design.md` (needs a token, a test guild and a member without Administrator).
- Smoke checklist in `openspec/changes/archive/2026-10-11-custom-commands-from-config/design.md` (needs a token, a test guild and a second guild, a member without Administrator, and zh-TW, en-US and Japanese clients).

## WelcomeGoodbye (v3 WelcomeByeGuild, `port-welcome-bye-guild`)

### User-visible changes
- The four commands answer in threads, voice channel chats, stage and announcement channels (v3: no reply, and a bind chosen with the `channel` option there was saved silently); without the option there, the reply is `invalid-channel`.
- `%...%` in member, guild and channel names is shown as written in replies and in the welcome and bye messages (v3 expanded it, and a self-reference stopped the message).
- The bye message can use the `wbg@member_*` keys and v3's unprefixed member keys when discord.py still knew the member (v3: never; they stayed as written).
- Bindings of guilds the bot left while it was offline or while the plugin was off are deleted when the bot is ready, with one log line per guild (v3 kept their files).
- A welcome or bye message that Discord refuses logs a warning that names the guild and the channel (v3: JDA's exception log).
- `invalid-channel`, `*-bind-already` and `*-unbind-empty` no longer create data; the commands always answer (v3 needed the core's auto-defer switch).
- No `plugins/WelcomeGoodbye/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-welcome-bye-guild/design.md` (needs a token, a test guild and a second account).

## Feedback (v3 Feedbacker, `port-feedbacker`)

### User-visible changes
- The form is deleted only after its review is posted.
- The pressed star turns blue through an edit of the bot's own message after the modal opens (v3 queued it on the interaction hook before acknowledging the press).
- Feedback text is shown as typed (v3 expanded `%...%` in it, and `%fb_content%` made the modal fail).
- A star count outside 0 to 5 in an operator's template fails the press at once (v3: after the member typed a feedback).
- A v3 `config.yaml` loads unchanged and warns `unknown key enabled`; there the two new replies are English (`Failed to create the form`, `Failed to submit the feedback`) until added; a blank reply or one over 2000 characters disables the plugin with the key named.
- The command always answers (v3 needed the core's auto-defer switch).
- Core, every plugin: embed field names and values are trimmed and an empty one becomes U+200E, as v3 did through JDA (xincord sent them as rendered, and Discord refuses an empty field).
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-feedbacker/design.md` (needs a token, a test guild and a second account).
- This is the first modal xincord sends (a label around the text input, as discord.py builds it): check that it opens in both languages.
- At cutover, add `form_failure` and `form_submit_failure` to the existing `plugins/Feedback/config.yaml` for zh-TW texts, and press one star of a v3 form if any remains.

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
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-economy/design.md` (needs a token, a test guild and a second account).
- At cutover, keep the existing `plugins/Economy/config.yaml` (it lists the administrators); its `enabled` and Google Sheets keys can be deleted to silence the warnings.

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
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-dynamic-voice-channel/design.md` (needs a token, a test guild and a second account).
- The bot needs Manage Channels and Manage Roles (or Administrator) in the bound categories.
- Check that positions 0 and 1 put the new lobby at the top of its category and the room right below, as in v3 (the raw PATCHes are v3's requests; Discord's ordering of equal positions was not observed).
- At cutover, delete v3's leftover rooms by hand (only v3's MongoDB knows them).
- Two members who join an empty lobby at the same instant may both stay in the lobby without a room (discord.py may parse both joins before the plugin sees the first); watch whether it happens.
- After a discord.py upgrade, check the room requests: the positions use discord.py's undocumented `HTTPClient.request` and `Route`.

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
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-voice-logger/design.md` (needs a token, a test guild and a second account).
- The bot needs View Audit Log for the members of status changes, and View Channel, Send Messages and Embed Links in the listen channels.
- Unverified without a real guild: Discord's `VOICE_CHANNEL_STATUS_UPDATE` payload (null or empty for a cleared status), whether Discord sends it when it clears a status by itself, whether type-192 and 193 entries carry `options.channel_id` and `options.status` as documented (or the channel in `target_id`), whether `options.status` is exactly the gateway's text (if not, set statuses show `-`), and how soon after the gateway event the entries exist.
- After a discord.py upgrade, check the relay (discord.py's internal `ConnectionState.parsers`) and the audit log request (`HTTPClient.request` and `Route`); if discord.py starts parsing the event, the relay still runs after its parser.

## ChatLogger (`port-chat-logger`, `chat-logger-split-storage`)

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
`chat-logger-split-storage`: messages are kept 5 years by default: the bundled `config.yaml` says `retention_days: 1826` (was 30), as the owner decided on 2026-10-10.
`chat-logger-keep-deleted` (the owner's request of 2026-10-11): new config key `keep_deleted`, false by default; with it true, a deleted message stays stored after its deletion is logged, until `retention_days` removes it, as v3 kept it. The bundled `config.yaml` explains it in a new comment; existing operator files run with the default until the key is added.
`chat-logger-split-storage`: new config key `max_file_size_mb` (256 by default, 1 to 65536, with a comment): once the newest message file reaches that size, a new file starts.
`chat-logger-split-storage`: the message log moved from `data/xincord.db` to `data/ChatLogger/messages-<UTC second>.db` in the `data` volume: no file before the first stored message, a new file at the size limit, and a file whose messages all expired is deleted whole. Backups must copy `data/ChatLogger/` too, best with the bot stopped.
`chat-logger-split-storage`: with `log_all: true`, the messages of a guild the bot left now stay up to 5 years (the retention; see the choice on left guilds below).
`chat-logger-split-storage`: new log lines: `ChatLogger started the message file ...` and `ChatLogger deleted the message file ..., whose messages all expired` (info); an error, once per episode, when a new file cannot be created; an error when an expired file cannot be deleted (it goes at the next start); a corrupt message file stops the plugin with an error that names it.
`chat-logger-split-storage`: the `ChatLogger_messages` table of earlier xincord builds is dropped from `data/xincord.db` when the plugin loads, without its rows.
`chat-logger-split-storage`: a message file that another program keeps locked for more than 5 seconds (a database browser holding a read transaction open) makes that message's storing, edit or deletion fail with an error; inspect copies of the files.
`chat-logger-split-storage`: core: each plugin's context names a data directory, `data/<Name>/`, which the core never creates (`PluginContext.data_directory`; `Bot(...)` takes the required keyword `data`, and the program passes `data/`).
`chat-logger-split-storage`: core, every plugin: a store write whose commit fails (another program holding a lock on `data/xincord.db` past 5 seconds) is rolled back and raises; before, a later write committed it.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-chat-logger/design.md` (needs a token, a test guild and a second account); its steps 1 and 13, which look for `ChatLogger_messages` in `data/xincord.db`, are replaced by the checklist below.
- Smoke checklist in `openspec/changes/archive/2026-10-11-chat-logger-split-storage/design.md`: a split at `max_file_size_mb: 1`, edits and deletions on both sides of it, a restart, the expiry of a whole file (needs a token, a test guild and a day).
- Turn the Message Content intent on for the bot in the Discord developer portal (Bot, Privileged Gateway Intents) before enabling ChatLogger: without it, Discord refuses the bot's connection.
- The bot needs View Channel and Read Message History in the logged channels, and View Channel, Send Messages and Embed Links in the listen channels.
- Unverified without a real guild: whether Discord sends `MESSAGE_UPDATE` for pins and link previews and which previews it types `rich` (members' are never logged either way; a bot's rich preview would log an edit), and how long a large purge takes to post.

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
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-giveaway/design.md` (needs a token, a test guild and a second account).
- Before cutover, set `TZ=Asia/Taipei` in the production host's `.env` (`timezone-from-env`; or `timeZone` in `plugins/Giveaway/config.yaml`): without it the container's zone is UTC, so typed end times would be read 8 hours off.
- The bot needs View Channel, Send Messages (in threads too) and Embed Links in giveaway channels; Read Message History only for the core's upgrade of v3 posts.
- Unverified without Discord: that a type-7 response to a modal submission updates the ephemeral builder, and how a burst of joins looks (a response may show a count one behind until the next press).
- Packaging was checked: the wheel's files, `xincord --no-online` from the built wheels, and the compose image (`docker compose run --rm -T bot --no-online` with `Giveaway` enabled), whose Python resolves `Asia/Taipei`.
- After the one-off migration at cutover (B11), the core upgrades v3 posts' IDs with a fetch and an edit, which can briefly revert a concurrent edit of the post's buttons; the next press repairs it.

## Plugin renames (`rename-plugins`)

### User-visible changes
- The core config's `plugins:` names Example, Calculator, CustomCommands, WelcomeGoodbye, UptimeHeartbeat and Feedback (v3: _Example, BasicCalculator, SimpleCommand, WelcomeByeGuild, IntervalPusher, Feedbacker); the other plugins keep their names.
- Their files live in `plugins/Example/`, `plugins/Calculator/`, `plugins/CustomCommands/`, `plugins/WelcomeGoodbye/`, `plugins/UptimeHeartbeat/` and `plugins/Feedback/`.
- `/feedbacker` is `/feedback` (the base and en-US name; zh-TW clients still see 評價表單); its `register.yaml` key is `feedback` in both locales.
- Log lines use the new names (`Calculator cannot post ...`, `CustomCommands cannot post ...`, `WelcomeGoodbye deleted the channels of guild ...`, `UptimeHeartbeat listener 1 started (every 60 s)`, `Feedback cannot post a form in ...`), and so do the logger names (`xincord.plugins.uptime_heartbeat.pusher`).
- `python -m xincord.core.migrate_v3 <dir>` writes the new names under `plugins:` and moves each renamed plugin's v3 directory to its new name, with a report line each.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-rename-plugins/design.md`.
- Done: `docker compose build`, then `docker compose run --rm -T bot --no-online` with all thirteen ported plugins enabled, exited 0 with every one loaded; this settles the image checks of the earlier sections.
- At cutover, after `migrate_v3`, delete `plugins/Feedback/lang/*/register.yaml` (v3's, with the `feedbacker` key) so that the bundled files with `/feedback` are exported; until then `/feedback` shows English descriptions to zh-TW users too.
- The archived smoke checklists, and the earlier sections' links to them, use the v3 names: follow them with the new ones (`plugins: [Feedback]`, `/feedback`), as mapped in `docs/porting-guide.md`, "Plugin names".
- Migrate a copy of the stopped v3 directory: `migrate_v3` now moves the renamed plugins' directories, so restoring `config.v3.yaml` alone no longer brings v3 back (the report lists the moves to reverse), and a running v3 would recreate the old directories.
- A guild's permission overrides for `/feedbacker` (Server Settings, Integrations) do not carry over to `/feedback`, which gets a new command ID: set them again where they were used.
- Found in this change's review, unchanged: `migrate_v3` counts a plugin as enabled only with `enabled: true`, a key v3 added in 3.3.0 (`ea14fbf`); on a 3.2.x directory, as the local copy in `XsDiscordBotKt/Server/` may be, it lists almost nothing, so check the `plugins` list after migrating.

## Ticket (`port-ticket`)

### User-visible changes
- en-US users get English replies, errors and builder defaults; zh-TW users get v3's four English errors in Chinese (message not found, message full, category not found, button empty). The texts live in the new `plugins/Ticket/lang/<locale>/text.yaml`, which operators can edit.
- New texts: session expired, invalid message ID, not the bot's message, no embed, invalid color, refused change, create failed, ticket failed, lock failed, delete failed.
- The builder's preview button opens the reason modal (v3: the press failed); the builder keeps working after 15 minutes; an older builder message answers that the session expired (v3: nothing happened).
- zh-TW administrators can change the button's text and emoji (v3's zh-TW modal could not); the reason modal's title is in the user's own language (v3 swapped them).
- Colors accept `#RRGGBB`, `0xRRGGBB` and `RRGGBB`; a bad color, an empty button, or a value that Discord refuses (an invalid emoji, a bad icon URL) answers an error and keeps the draft; custom emojis work on buttons; clearing the title, description or author removes it.
- `/add-ticket` answers at once for a non-numeric ID, another user's message, a message without an embed, and a first row that is full or holds a select; an added button keeps the message's other rows and embeds.
- Confirming answers failures and keeps the builder (v3 deleted it first and failed silently).
- Ticket channels get an overwrite that lets the bot see them (v3 needed Administrator or a staff role); a reason too long for one message arrives in several (v3: the channel had no controls); a missing panel or category answers v3's error (v3: "thinking" forever).
- The opener pings the staff roles only: `@everyone` and other mentions typed in a reason no longer ping (v3 pinged them).
- Lock and unlock answer before any request to Discord and report failures (v3: the press failed when the member had left); since `ticket-staff-controls` they are for staff only (next section).
- The archive pings nobody, splits long messages, links files over the guild's upload limit, renames authors whose name Discord refuses for webhooks, deletes its empty thread when the webhook cannot be made, and reports every failure (v3 hung).
- Panels of guilds the bot left while offline are deleted at READY (v3 deleted them only when it saw the leave).
- `/add-ticket` with a text that is no message ID shows at most 100 characters of it in the error.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-port-ticket/design.md`.
- The archive copies other members' messages only with the Message Content intent enabled in the developer portal (as in v3; the plugin does not request it, so the bot connects without it).
- The bot needs Manage Channels and Manage Roles where tickets open, and View Channel, Send Messages, Send Messages in Threads, Create Public Threads and Manage Webhooks in the archive channel; Read Message History in the ticket.
- Before cutover, set `TZ` in the production host's `.env` (for example `Asia/Taipei`, `timezone-from-env`) so that the archive's times match v3's host.
- After the one-off migration of v3's panels at cutover, press a v3 panel and a v3 control row: they work and their IDs are rewritten. Deleting a ticket from a v3 control row logs the core's failed upgrade once, since the message is gone.
- Migrate v3's panels (the one-off migration at cutover) before anyone uses `/add-ticket` on a v3 panel (see the choice above).
- Unverified without Discord: Discord's exact webhook username rules, and how a long archive behaves near Discord's rate limits.
- Packaging was checked: the wheel's lang files, `xincord --no-online` from the built wheels, and the compose image with the fourteen ported plugins; a discord.py probe walked every flow with HTTP recorded (archived design, "Checks").

## Ticket control row (`ticket-staff-controls`)

### User-visible changes
- Lock, unlock, save and delete work for the ticket's staff only: a member with one of the panel button's staff roles, or Administrator. Anyone else, the ticket's member included, gets the existing admin-only text (`error.admin-only`, en-US "Only administrators can use this.") as an ephemeral reply in their language, and nothing changes. Before, lock and unlock worked for anyone who saw the channel (the member could lock themselves out), and delete did nothing without a word; save already answered so.
- Lock and unlock on a row whose panel button is no longer stored answer the not-found text, as save and delete already did; before, they worked without it. This covers v3's ticket channels until the one-off migration at cutover stores v3's panels, and tickets whose panels were deleted when the bot left their guild.
- New labels (`control.*` in both `text.yaml` files): `Click to lock`, `Click to unlock`, `Save conversation` and `Delete` in en-US, and the zh-TW words the owner gave. The row is a public message in the default locale (zh-TW), so every reader sees the zh-TW labels; the en-US ones show nowhere today.
- Rows already posted keep their labels until they are rebuilt, which the next lock or unlock does; save and delete leave the row as it is, and the core's upgrade of v3's IDs keeps a v3 row's labels.
- Exported lang files (`plugins/Ticket/lang/<locale>/text.yaml`) keep the old labels until renewed with `--force-renew-lang-resources` (which renews every enabled plugin's lang files, edits included) or edited by hand (the four `control.*` lines).
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-ticket-staff-controls/design.md`: the ticket's member presses each button (the admin-only text, nothing changes); a member with the staff role and an Administrator lock, unlock, save and delete; a row posted before the change takes the new labels at its next lock or unlock.
- After the one-off migration at cutover, staff lock and unlock a v3 ticket (until then they answer the not-found text).
- Done: the wheel holds both `text.yaml` files with the new labels; the tests press every button as staff, as the ticket's member, as another member, on a row without its entry and with @everyone among the staff roles, and a v3 row as the ticket's member; a cross-review found no high or medium defect, and its three low findings are fixed (archived design, "Cross-review").

## TicketAwayNotice (v3 TicketAddons, `port-ticket-away-notice`)

### User-visible changes
- The plugin is `TicketAwayNotice` under `plugins:` and in `plugins/TicketAwayNotice/`; `migrate_v3` moves v3's `plugins/TicketAddons/` there with its config and template.
- Enabling it makes the bot request the privileged Presence and Server Members intents; without the Presence intent in the developer portal, Discord refuses the bot's connection (4014).
- The notice is posted only in `guild_id` (v3: in every guild where the owner was a member and offline).
- Threads, forum posts, announcement channels and voice and stage channels' chats with a matching name get the notice (v3 posted in text channels only and threw for the others); categories and forums are skipped quietly, and so are threads that the bot starts itself, such as Ticket's archives.
- The notice appears only while the owner is offline as Discord reports it (v3 posted almost always, since it cached no members), and not when the owner comes online or the channel is deleted during the wait.
- The bundled `config.yaml` holds 0 for `guild_id` and `user_id`, so the plugin does not load until both are set (v3 shipped the shop's real IDs); v3's file loads unchanged and warns `unknown key enabled`.
- The bundled `not-online.yaml` holds an example shop name (範例商店) and example channel IDs, with the text in the embed's description, where channel mentions show as links (v3: in the title, shown as raw `<#...>` text); v3's footer `❖ ORDERLY SERVER ❖` is kept, and operators' files keep their own text.
- New log lines: warnings for a guild the bot is not in and an owner who is not a member (at READY and per channel), a refused member lookup and a refused notice; a template that can never be posted (a component ID, more than ten embeds, an empty message) keeps the plugin from loading, with the file named.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-port-ticket-away-notice/design.md`.
- Allow the Presence intent in the developer portal before enabling TicketAwayNotice (the Server Members intent is already on), or the bot does not connect.
- At cutover, after `migrate_v3` moved `plugins/TicketAddons/`, check that `guild_id` is the shop's guild: the guild filter now applies, so a wrong value stops the notices (the READY check names it).
- The bot needs View Channel, Send Messages and Embed Links in the new channels.
- An image check with every plugin enabled needs example IDs in `plugins/TicketAwayNotice/config.yaml`, as Economy's `admin_id`.
- Done: the wheel, `xincord --no-online`, the compose image with the fifteen ported plugins, and a probe through discord.py's gateway code, again after the cross-review's fixes (archived design, "Checks" and "Cross-review").

## NtustAnnouncements (v3 NtustManager, `port-ntust-announcements`)

### User-visible changes
- The plugin is `NtustAnnouncements` under `plugins:` and in `plugins/NtustAnnouncements/`; `migrate_v3` moves v3's `plugins/NtustManager/` there with its keys and prompt, and that file needs `boards` added (copy them from the bundled file and set each `channel-id`).
- The bundled `config.yaml` keeps v3's interval, prompt and example key and lists v3's 18 boards with 0 for every channel, so the plugin does not load until the keys and channels are set; new keys `boards` (`name`, `url`, `layout`, `channel-id`, `title-prefix`) and `model` (`gemini-2.5-flash`), with new comments.
- An announcement whose article page failed or whose post Discord refused is posted at a later pass (v3 lost it); an article that Gemini fails to convert in ten attempts, or whose page has no content container, is posted as its `# [title](url)` link (v3 posted nothing).
- An announcement that left a board's first page and came back is not posted again (up to 100 remembered per board); a link listed twice on a page is posted once.
- Boards run on their own schedules: a board waiting hours for Gemini's retries no longer delays the others (still five page fetches at a time).
- Title links escape `\`, `[` and `]`, percent-encode `(`, `)`, `<`, `>`, `\` and spaces in the URL, and cut a title too long for Discord with an ellipsis; posts never ping, even when Gemini's text holds `@everyone` or a role.
- The prompt's tokens are replaced in one pass: a title that holds `{{html}}` stays as written.
- Board pages that redirect are followed (v3: such a board was empty at every cycle).
- Log lines (English) name the board; each kind of failure is logged once per episode, with a line when it works again; keys are named by their position (`key 2`), never by their last four characters; a warning at READY names a board whose channel the bot cannot see or that takes no messages; blank entries are a debug line instead of v3's "empty content" warning at every cycle.
- Core, for every plugin and the core config: a YAML syntax error now gives the file, the line and the column without quoting the faulty line, which could hold an API key or a push token (found in the cross-review).
- A board's page is parsed in a worker thread; an announcement that raises is logged once per kind and episode and tried again at the next pass, while the board's later entries are posted; a message part of only whitespace is left out; only NTUST's hosts' `/p/<n>.php` pages count as articles (v3's pattern took any host).
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-port-ntust-announcements/design.md` (a Gemini API key and a test guild).
- At cutover: migrate v3's stored lists (a one-off script) before enabling the plugin, or the first pass posts every board's first page; add `boards` with the 18 channel IDs to the migrated `plugins/NtustAnnouncements/config.yaml`.
- The bot needs View Channel and Send Messages in each board's channel.
- An image check with every plugin enabled needs example values in `plugins/NtustAnnouncements/config.yaml` (keys other than v3's example, channel IDs), as Economy's and TicketAwayNotice's.
- If Google retires `gemini-2.5-flash`, set `model`.
- Done: the wheel, `xincord --no-online`, the image with the sixteen ported plugins, NTUST's TLS from the image and a probe through discord.py's own objects (archived design, "Checks").
- TWCA's intermediate certificate in the package expires on 2030-10-16; if NTUST changes its certificates, check the log for TLS failures on the boards.

## NtustAnnouncements model settings (`ntust-announcements-model-config`)

### User-visible changes
- `plugins/NtustAnnouncements/config.yaml` takes ten new keys, each optional with v3's value as default: `api-format` (`gemini`, or `openai` for OpenAI-compatible APIs), `endpoint` (`https://generativelanguage.googleapis.com/v1beta`), `temperature` (0.1; `null` sends none), `max-output-tokens` (`null`: none sent), `request-timeout` (300 s), `connect-timeout` (30 s), `rate-limit` (10 attempts per key) in any `rate-window` (60 s), `max-attempts` (10) and `retry-waits` (`[60, 300, 900, 1800]`, the last repeating); `model` stays. The bundled file lists them with comments (new copy), and its header, `api-keys`, `model` and `prompt` comments no longer present Gemini as the only API. An existing operator file keeps its text and runs with the defaults; copy the keys from the bundled file to change them.
- `api-format: openai` sends each article to `<endpoint>/chat/completions` with the key as a bearer token and reads the first choice's content: OpenAI, OpenRouter, Ollama, a proxy, or Gemini's own `https://generativelanguage.googleapis.com/v1beta/openai`.
- A reload (`/xincord reload NtustAnnouncements`, the console or SIGHUP) applies changed settings to the next passes; an invalid value fails the reload with `config.yaml: <key>: ...` and the previous settings keep running.
- New info line when the boards start (READY or a reload): `NtustAnnouncements: converting articles with gemini-2.5-flash at https://generativelanguage.googleapis.com (api-format gemini)`; the endpoint shows only as its scheme, host and port.
- Reworded lines, with either format: `Gemini attempt 3 of 10 at <article> failed with key 1: ...` is `conversion attempt 3 of 10 at <article> failed with key 1: ...`; `Gemini gave no text` is `the model gave no text`; `Gemini works again after 3 failed attempts` is `conversions work again after 3 failed attempts`; `Gemini failed 10 attempts at <article>` is `gave up converting <article> after 10 attempts`; the board's `since Gemini could not convert it` is `since the model could not convert it`; at debug level, `every Gemini key is at its limit` is `every key is at its rate limit` and `Gemini converted ...` is `converted ...`; a count of one reads `1 attempt`. The logger name is `xincord.plugins.ntust_announcements.conversion` (was `...gemini`).
- Error texts in those lines have every URL cut to its scheme, host and port and the endpoint's path removed, so an API's help link shows only its origin; an error answer as a list of one error (Gemini's OpenAI-compatible endpoint) or as a text gives its message.
- Config errors: v3's example key reads `replace the example key with your API key` (was `... with a Gemini API key`); with `gemini`, a model with characters other than letters, digits, `.`, `-` and `_` reads `the gemini format takes letters, digits, '.', '-' and '_'` (was pydantic's pattern message); each new key has its own messages, none quoting the endpoint.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-ntust-announcements-model-config/design.md` (a token, a test guild and API keys): the READY line, Gemini's OpenAI-compatible endpoint with the same key, OpenAI or OpenRouter, Ollama, a wrong key, the retries, an invalid value on reload.
- Ollama on the Mac from the compose container: `endpoint: "http://host.docker.internal:11434/v1"` (the container's `localhost` is the container).
- Before switching provider, compare its limits with `rate-limit` and `rate-window`; Gemini's free tier also limits requests per day, which one window does not express.
- Done: the wheel, `xincord --no-online` with the bundled file, example values, an invalid temperature and an endpoint with secrets, a probe of both formats and of aiohttp's own error texts through the installed plugin (archived design, "Checks"), and a cross-review whose findings are fixed or listed above (archived design, "Cross-review").

## NtustCourseWatch (v3 NtustCourse, `port-ntust-course-watch`)

### User-visible changes
- The plugin is `NtustCourseWatch` under `plugins:` and in `plugins/NtustCourseWatch/`; `migrate_v3` moves v3's `plugins/NtustCourse/` there, and v3's file (`enabled` only) loads with v3's values.
- `config.yaml` has `semester` (v3's `1142`), `start` (v3's 2025-12-26 09:00, written with `+08:00`), `interval` (v3's 1.5 seconds, at least 1) and `alert-interval` (60 seconds, at least 10), with comments that ask for the semester and the start of each course selection.
- The plugin asks NTUST about the registered courses only, one per request every `interval` seconds, in turn (five registered courses: each checked every 7.5 seconds), and nothing before `start` or while nothing is registered (v3 asked for the whole catalogue every 1.5 seconds, all the time).
- A channel hears about a course with seats at most once per `alert-interval` (v3: at every poll, about every 1.5 seconds), and gets the full alert only after an available alert; mention lists too long for one message come in several posts.
- Registrations survive restarts; `/course-remove` removes only the member (v3: every member of the channel); codes are read loosely (case, spaces, full width), and anything other than 9 to 20 letters and digits (NTUST's codes have nine; it matches codes as prefixes) gets the new reply `invalid-code`; `/course-list` compares IDs exactly and lists each course once, sorted.
- zh-TW clients see new Chinese command descriptions and replies; the alerts stay in English, as v3's.
- A channel that Discord no longer knows (404) loses its registrations at its next alert; `[`, `]` and `\` in a course's name are escaped in the alert's link.
- English log lines, once per kind of failure and episode (v3 printed every failure to stdout).
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-port-ntust-course-watch/design.md`.
- Before each course selection: set `semester` and `start` in `plugins/NtustCourseWatch/config.yaml`; during the first selection, check in the log that NTUST answers the per-code requests under load.
- At cutover: v3 lost its registrations at each restart; the one-off migration at cutover can bring back those of v3's MongoDB document (archived design, "Registrations and the v3 data import").
- The bot needs View Channel and Send Messages where members register.
- Done: the wheel, `xincord --no-online`, the image with the seventeen ported plugins, NTUST's TLS and one course request from the image, and a probe through discord.py's own objects, again after the cross-review's fixes (archived design, "Checks" and "Cross-review").

## MusicPlayer (`port-music-player`)

### User-visible changes
- The audio plays on a Lavalink 4.2.2 node, compose's new `lavalink` service: `cp .env.example .env` and set `LAVALINK_PASSWORD`; `lavalink.password` in `bot/plugins/MusicPlayer/config.yaml` must be the same, and the plugin does not load until it is set (the bundled file leaves it empty).
- Every `docker compose` command now needs `LAVALINK_PASSWORD` (in `.env` or the environment), also when MusicPlayer is not enabled; the node always runs beside the bot (about 10 seconds to start, downloading its plugins at each container creation).
- Spotify moves to the node: `SPOTIFY_ENABLED`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_COUNTRY_CODE` in `.env` replace v3's `engines.spotify`, which now only warns; arbitrary `http(s)` links and local files no longer load; Yandex Music, Beam and Getyarn are gone.
- v3's file loads once it has a `lavalink` section, with a warning for each of its 14 keys that never had an effect (`enabled`, `command_message_acknowledges`, `engines`, the cache, lyrics, performance and developer settings...).
- en-US members get English replies (`text.yaml`); zh-TW members and every other locale keep v3's zh-TW texts. New texts: `node-unavailable`, `queue-full`, `queue-truncated` and the queue's last line `queue-more`.
- The four button emojis that v3's templates named by the author's application IDs come from four new `emojis` names (v3's names by default); an emoji the application lacks shows as a Unicode one (v3 broke every panel).
- Button refusals now show in the panel (v3's "This interaction failed"); a press keeps the panel alive another 60 seconds; the queue panel refreshes; a song added after the end of the list plays (v3 queued it forever); `/skip` past the last song ends the list with v3's `skipped-to-end`; every song starts unpaused; a failed or stuck song moves on.
- The bot leaves voice after `player.auto_leave_timeout` (v3's 10 minutes) with nothing playing; a reload or an unload stops the music and leaves voice; panels are deleted when the bot leaves; a moderator's disconnection clears the songs.
- After a new gateway session (READY again, not a resume), the bot leaves the voice channels that discord.py forgot; members run `/play` again. A node that answers nothing for 15 seconds makes the command answer `node-unavailable`.
- Autocomplete suggestions answer within 2.5 seconds (or not at all) and leave other plugins' autocompletes alone.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-11-port-music-player/design.md`.
- A real voice test with a token: DAVE through Lavalink 4.2.2 is untested here (no token or guild); listen to a song, a move between channels and a moderator's disconnection.
- Upload v3's emoji images (`XsDiscordBotKt/Plugins/MusicPlayer/src/main/resources/images/`) as the application's emojis if the bot's application changed; otherwise check that the existing ones show.
- Done: the wheel, `xincord --no-online` (bundled, filled and v3 configs), the node healthy on this Mac with both plugins, the image with all eighteen plugins, the plugin's link from the image to the node (a YouTube search, the refused sources, a wrong password), a probe through discord.py's own objects, again after the cross-review's fixes (a moderator's disconnection and a second READY), and the node's logs without queries (archived design, "Checks" and "Cross-review").

## Dependency updates (`dependency-updates`)

### User-visible changes
- Renovate opens version-update PRs on Mondays (Asia/Taipei) and a Dependency Dashboard issue listing what waits; Dependabot opens security-update PRs as advisories appear.
- Patch updates and the monthly `uv.lock` maintenance merge themselves (squashed) once CI passes; minor and major updates wait for you.
### Manual checks
- After this change lands, Renovate's first run opens the Dependency Dashboard issue; check that its first patch PR merges itself after CI.
- GitHub documents Dependabot's uv support at uv 0.11, while `uv.lock` comes from uv 0.12: if a Dependabot uv security PR fails on the lock file, turn on Renovate's `vulnerabilityAlerts` instead.

## Releases (`release-pipeline`)

### User-visible changes
- Pushing a GPG-signed `v*` tag (README, "Releasing") releases xincord: the workflow checks the signature against your GitHub GPG keys and the versions, pushes `ghcr.io/xinshoutw/xincord:<version>` and `:latest` (amd64 and arm64), and creates the GitHub Release with both distributions attached.
### Manual checks
- Before the first 1.x tag: create the `pypi` environment with yourself as required reviewer (Settings, Environments), and add pending trusted publishers on PyPI for `xincord` and `xincord-plugins` (workflow `release.yml`, environment `pypi`).
- When the repository goes public: make the GHCR package `xincord` public too.
- Bumping a version needs `uv lock` before the commit, or CI's `uv sync --locked` fails.
