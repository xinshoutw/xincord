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
- A minus after an operator negates: `2*-3` is `-6`, `2--3` is `5`, `2^-1` is `0.5`, `1/-2` is `-0.5` (v3: `-3`, `-1`, `0`, no reply).
- `^` groups from the right: `2^3^2` is `512` (v3: `64`).
- Fractional exponents fail with `Exponent must be an integer` (v3 truncated them: `2^0.5` was `1`); huge ones fail with `Too many digits` (v3: `2^4294967297` was `2`, `10^999999999` stalled the bot).
- Division by zero answers `Division by zero`, and negative exponents divide (v3: no reply, "thinking..." forever).
- `formula` takes at most 1018 characters; values over 50,000 digits and results over 1018 characters fail with `Too many digits` (v3: no reply).
- New error messages, English in every locale like v3's: `Division by zero`, `Exponent must be an integer`, `Too many digits`, `Formula too long`.
- `%...%` in a failing formula is shown as typed (v3 expanded it, and `%bc_question%` gave no reply).
- When the bot cannot post in the channel, the answer replaces the ephemeral "thinking" response (v3: "thinking..." forever).
- `%bc_answer_round%` is the part before the decimal point (v3: the whole answer); the shipped templates do not use it.
- The en-US `formula` description says the multiplication sign can be omitted (v3: "bracket is ignorable"); existing `plugins/BasicCalculator/lang/` files keep v3's text unless renewed with `--force-renew-lang-resources`.
- No `plugins/BasicCalculator/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
### Choices made without the owner
- Minus after an operator: implemented negation, tighter than `* /` and looser than `^`; alternative: keep v3's answers.
- `^` grouping: implemented right to left, as in mathematics and Python; alternative: v3's left to right, as Excel does.
- Negative exponents: implemented `1 / a^n` with a division's rounding; alternative: refuse them, as v3's `BigDecimal.pow` did (with no reply).
- Fractional exponents: implemented an error; alternative: approximate roots.
- Size limit: implemented 50,000 digits per value (admits `(1+1/1000)^1000`, refuses `(1+1/10000)^10000`) and a worker thread; alternative: a larger limit or a timeout.
- Error messages: kept English in every locale, as v3's; alternative: localized texts in the lang files.
- A channel that refuses the message: implemented the answer in the deferred ephemeral response; alternative: an error message, or a public interaction reply instead of a channel message.
- `%bc_answer_round%`: implemented the part before the decimal point, which v3's `split('.')` meant; alternative: round half up, or drop the key.
- `formula` length: implemented 1018 characters, which fit the code fence in a 1024-character embed field; alternative: Discord's 6000 with an error above 1018.
- Non-ASCII digits (`３`, `١٢`): kept v3's `Unknown Token` error; alternative: read them as digits.
- Golden tests: v3's 3155 recorded answers are copied unchanged to `tests/fixtures/plugins/basic_calculator/`, and the 541 that the fixes change are checked against an independent evaluator over Python's grammar; alternative: a reviewed list of new answers.
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
- The bot's application must allow the Server Members intent in the developer portal (v3 always requested it, so it is probably on); without it, startup stops with a privileged-intents error.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `AutoRole` enabled); an image build with the plugin enabled is still open.

## BotInfo (`port-bot-info`)

### User-visible changes
- `/bot-info` shows a third embed field, `Source Code`, with `source_url` from `plugins/BotInfo/config.yaml` (decision C3; zh-TW name in the plugin's `lang/zh-TW/message/bot-info.yaml`).
- `source_url` defaults to `https://github.com/xinshoutw/xincord`, which is private today: the link gives a 404 until the repository is public or `source_url` points elsewhere.
- An invalid `source_url` (not http or https, spaces, over 512 characters) disables BotInfo with an error that names the key; a v3 `config.yaml` (`enabled` only) loads with the default URL and warns `unknown key enabled`.
- v3 lang files kept in `plugins/BotInfo/lang/` show v3's embed without the source field until renewed with `--force-renew-lang-resources` (which renews every enabled plugin's lang files) or edited.
- The command always answers (v3 needed the core's auto-defer switch), and guilds that are unavailable during a Discord outage still count as guilds (JDA left them out).
### Choices made without the owner
- Default source URL: implemented the xincord repository, as nothing in the decisions or the analysis names one; alternative: no default, so that the operator must set it.
- Where the link shows: implemented a third embed field in both locales; alternative: a link button under the embed, or a link on the embed title.
- URL check: implemented http or https without spaces and at most 512 characters (Discord's link-button limit), checked at load; alternative: any text, unchecked.
- Current member counts: implemented the privileged members intent, so the counts follow joins and leaves as in v3; alternative: no privileged intent, with counts as of the last connection.
- Member count: kept v3's per-guild sum (users in several guilds counted once per guild, bots included); alternative: unique users from the member cache.
- Unavailable guilds: counted, with the members discord.py knew (none if unknown); alternative: left out of both counts, as JDA did.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-bot-info/design.md` (needs a token and a test guild).
- The bot's application must allow the Server Members intent in the developer portal (v3 always requested it); without it, startup stops with a privileged-intents error.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `BotInfo` enabled); an image build with the plugin enabled is still open.

## SimpleCommand (`port-simple-command`)

### User-visible changes
- When the bot cannot post in the channel (missing permissions, or a channel that takes no messages), the administrator gets the message as the ephemeral response and the log has a warning (v3: the "thinking" message vanished and nothing was posted).
- The bundled templates show the example account number `000000000000` under a comment (v3 shipped the real numbers); existing `plugins/SimpleCommand/lang/` files keep theirs, because only missing lang files are exported.
- The commands always answer (v3 needed the core's auto-defer switch).
- No `plugins/SimpleCommand/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
- Placeholders that other plugins left in v3's shared global substitutor no longer expand in these templates; `%bot_id%` and `%bot_name%` still do.
### Choices made without the owner
- Command set: kept v3's five fixed commands (one table in the code, one shared handler); alternative: commands defined in a config file (name to template), so operators add or remove them without a code change (inventory B3).
- A channel that refuses the message: implemented the message in the deferred ephemeral response, as BasicCalculator; alternative: an error text telling the administrator that the bot cannot post there.
- Example account number: implemented `000000000000`, which no real account has, under a comment in each template; alternative: a placeholder text such as `<account number>`.
- What is posted: implemented the whole template, as v3 posted the built message (an operator's link buttons, Components V2 layouts and their uploaded files too); alternative: content and embeds only, as BasicCalculator posts.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-simple-command/design.md` (needs a token, a test guild and a member without Administrator).
- At cutover, copy v3's `plugins/SimpleCommand/lang/` (with the real account numbers) into the bot's `plugins/SimpleCommand/lang/`; otherwise the commands post the example number.
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `SimpleCommand` enabled); an image build with the plugin enabled is still open.

## WelcomeByeGuild (`port-welcome-bye-guild`)

### User-visible changes
- The four commands answer in threads, voice channel chats, stage and announcement channels (v3: no reply, and a bind chosen with the `channel` option there was saved silently); without the option there, the reply is `invalid-channel`.
- `%...%` in member, guild and channel names is shown as written in replies and in the welcome and bye messages (v3 expanded it, and a self-reference stopped the message).
- The bye message can use the `wbg@member_*` keys and v3's unprefixed member keys when discord.py still knew the member (v3: never; they stayed as written).
- v3's bindings in `plugins/WelcomeByeGuild/data/*.json` are not read: after moving from v3 the channels must be bound again (data migration is deferred, B11).
- Bindings of guilds the bot left while it was offline or while the plugin was off are deleted when the bot is ready, with one log line per guild (v3 kept their files).
- A welcome or bye message that Discord refuses logs a warning that names the guild and the channel (v3: JDA's exception log).
- `invalid-channel`, `*-bind-already` and `*-unbind-empty` no longer create data; the commands always answer (v3 needed the core's auto-defer switch).
- No `plugins/WelcomeByeGuild/config.yaml`: v3's only key, `enabled`, is the core's `plugins` list.
- zh-TW copy in the bundled files (existing `plugins/WelcomeByeGuild/lang/` files keep v3's text): `welcome`'s last line 也不坊到處看看喔！ becomes 也不妨到處看看喔！, and `bye`'s description 但願我們會能未來的道路相見... becomes 但願我們能在未來的道路上相見...
### Choices made without the owner
- Where the bindings live: implemented v3's document per guild in the store's key-value table (namespace `WelcomeByeGuild`, key = guild ID), so that a later migration can copy v3's files; alternative: a plugin table with one column per channel.
- Bye message keys: implemented the member keys when discord.py still knew the member; alternative: v3's user-only keys.
- Bindings of guilds left while offline or disabled: implemented their deletion when the bot is ready; alternative: keep them until the bot leaves that guild again, as v3.
- A channel where the bot cannot post: implemented v3's unchecked bind, with a log warning at each refused message; alternative: check View Channel, Send Messages and Embed Links when binding and tell the administrator (new copy).
- zh-TW typos: implemented the two corrections above; alternative: keep v3's text.
- `guild-only`: kept as a guard that guild commands never reach, rendered with the interaction's placeholders like `no-permission` (v3: global ones only); alternative: drop the check and its two templates.
- Core API: implemented `placeholder_values(interaction)` (Protocols `EventLike`, `ClientLike`) in `xincord.core.placeholders`, moved from _Example, which now imports it; alternative: a copy per plugin.
- Core fix: `interaction_values` gives no `channel_category_name` for a thread whose parent channel discord.py has not cached, where it raised and left the command unanswered (found by a probe through discord.py's own objects); alternative: none.
- Core gap found in the audit, unchanged: v3's commons-text read `%key:-fallback%` as a fallback for a missing key, while the core's `render` leaves it as written (no shipped template uses it); alternative: support the syntax in `render`.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-welcome-bye-guild/design.md` (needs a token, a test guild and a second account).
- The bot's application must allow the Server Members intent in the developer portal (v3 always requested it); without it, startup stops with a privileged-intents error.
- At cutover, bind the welcome and bye channels again in each guild listed in v3's `plugins/WelcomeByeGuild/data/`, or build the deferred migration first.
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
- Failure logs: kept v3's full URL, push token included; alternative: only the host.
- When pushing starts: implemented at READY (at once when the plugin loads into a ready bot), so that the monitor shows the bot as up only once it is connected; alternative: at load, before the gateway connects.
- Redirects: kept v3's behavior of not following them (a 3xx logs an error); alternative: follow them, so that an `http://` URL redirected to `https://` works.
### Manual checks
- Smoke checklist in `openspec/changes/archive/2026-10-10-port-interval-pusher/design.md` (needs a token and an Uptime Kuma push monitor or another endpoint that shows its requests).
- Packaging was checked without Docker (wheel contents, and `xincord --no-online` from the built wheels with `IntervalPusher` enabled, with and without a listener); an image build with the plugin enabled is still open.
- After a discord.py upgrade, check that pushes carry a real ping and not `-1`: the ping uses discord.py's undocumented `HTTPClient.request` and `Route`.

## Feedbacker (`port-feedbacker`)

### User-visible changes
- New reply `form_failure` (bundled `建立失敗`): the administrator gets it when the form cannot be created (a `member` who is not in the server, a channel where the bot cannot post, a non-text submit channel), and the log says why (v3: "thinking" forever, or the hard-coded `SubmitChannel must be TextChannel`).
- New reply `form_submit_failure` (bundled `送出失敗`): the member gets it, ephemerally, when the review cannot be posted (submit channel deleted or refusing the bot); the form stays for another try and the log says why (v3: a failed modal, or the feedback lost with the form deleted).
- The form is deleted only after its review is posted.
- The pressed star turns blue through an edit of the bot's own message after the modal opens (v3 queued it on the interaction hook before acknowledging the press).
- Feedback text is shown as typed (v3 expanded `%...%` in it, and `%fb_content%` made the modal fail).
- A star count outside 0 to 5 in an operator's template fails the press at once (v3: after the member typed a feedback).
- A v3 `config.yaml` loads unchanged and warns `unknown key enabled`; there the two new replies are English (`Failed to create the form`, `Failed to submit the feedback`) until added; a blank reply or one over 2000 characters disables the plugin with the key named.
- The command always answers (v3 needed the core's auto-defer switch).
- Core, every plugin: embed field names and values are trimmed and an empty one becomes U+200E, as v3 did through JDA (xincord sent them as rendered, and Discord refuses an empty field).
### Choices made without the owner
- New failure replies: implemented two generic config keys per audience next to v3's three (the log names the cause); alternative: one specific text per cause, or localized message templates in `lang/`.
- Their copy: implemented `建立失敗` and `送出失敗` in the bundled file (mirroring `建立成功`) and English defaults for v3 files; alternative: other wording, or zh-TW defaults through the migration script.
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
