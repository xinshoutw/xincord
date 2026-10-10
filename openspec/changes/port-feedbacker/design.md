## Context

v3's Feedbacker (`Plugins/Feedbacker`, 5 Kotlin files, 314 lines) has one guild command, five star
buttons and a modal, and keeps no data. `Event` (`PluginEventConfigure`, `Event.kt:15-75`) exports
the en-US and zh-TW lang files, reads `config.yaml` (`enabled` and three required replies,
`ConfigSerializer.kt:6-18`) and, when enabled, registers `/feedbacker` (`Register.kt:22-35`) and
forwards the command, the buttons and the modals whose IDs start with `feedbacker@` to
`Feedbacker` (`Feedbacker.kt:23-161`). The command checks Administrator and posts `ask-message` in
its channel (`:59-84`); a star press by the rated member opens `fill-form` and restyles the stars
(`:100-137`); the submission posts `print-result` to the submit channel and deletes the prompt
(`:139-160`). All flow state lives in the component IDs. The inventory is
`docs/porting/analysis/inventory/Feedbacker.md`; its section 12 lists seven probable bugs and the
behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's command, prompt, modal, review and replies; v3's prompts keep working through the
legacy ID decoder; no feedback is lost when the review cannot be posted; every failure answers the
user who caused it.

**Non-Goals:** forms made before v3's commit `ac6e90d`; double-submission locks; a bind-time check of
the bot's permissions in the submit channel; localized config replies; new commands.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/feedbacker/`: `__init__.py` (metadata and
  `setup`), `config.py` (the replies), `form.py` (the star text, the star count and the highlight
  of the pressed star), `cog.py` (`IDS`, the command, the press and the submission handlers),
  `config.yaml` and `lang/`. Entry point `Feedbacker = "xincord.plugins.feedbacker"`.
- `INTENTS = discord.Intents.none()`: the `member` option is resolved from the interaction payload,
  the submitter is the interaction's member and the submit channel comes from the guild's channel
  cache, which discord.py's default guilds intent fills. v3 declared no intents (its core always
  requested the members intent). `DEPENDS` and `SOFT_DEPENDS` are empty; `DEFAULT_LOCALE = "zh-TW"`.
- `lang/` holds v3's eight files: `register.yaml`, `message/ask-message.yaml`,
  `message/print-result.yaml` and `modal/fill-form.yaml` per locale, with LF line endings (both
  `register.yaml` files had CRLF lines).
- `config.yaml` holds v3's three replies without `enabled` and the two new failure replies, in
  zh-TW, with comments that say who sees each one.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists the four modules, `config.yaml`, the eight lang files
  and the `Feedbacker` entry point, and `xincord --no-online`, run from a scratch virtual
  environment with both wheels and `plugins: [Feedbacker]`, loads the plugin, writes
  `plugins/Feedbacker/config.yaml` (the bundled file) and the eight lang files, and exits with 0;
  with v3's `config.yaml` it warns `unknown key enabled` and exits with 0; with a blank
  `form_success` it exits with 1 and names the key.
- A scratch probe drove the plugin through discord.py's own objects (`discord.Interaction` built
  from gateway payloads, the tree's `_call` and `Bot.on_interaction`), with
  `HTTPClient.request` and the webhook adapter's `request` recorded: the command deferred,
  posted the prompt with the five star IDs and answered `form_success`; a user option that
  Discord resolved without a member answered `form_failure`; a press by someone else got the
  ephemeral `form_not_you`; the member's press sent the modal (a type 18 label around the type 4
  input `form`) and then patched the form with the pressed star primary; the submission deferred
  with type 6, posted the review (U+200E for an empty feedback) in channel 6 and deleted the form;
  a refused review sent the ephemeral follow-up `form_submit_failure`; a v3 form's press opened
  the modal, highlighted the star and was upgraded by the core to new IDs, styles kept.

### Config

`Config(Model)` keeps v3's keys. `form_no_permission`, `form_not_you` and `form_success` are
required, as in v3, where kaml refused a file without them; `form_failure` (default
`Failed to create the form`) and `form_submit_failure` (default `Failed to submit the feedback`)
are new and optional, so that a v3 file loads and shows English for them, as v3 showed its
hard-coded English errors. Every reply is `Annotated[str, StringConstraints(pattern=r"\S",
max_length=2000)]`: Discord refuses an empty message or one over 2000 characters, so a typo now
disables the plugin at load with the key named. The replies are sent as written, without
placeholders, as in v3.

### Component IDs

`IDS = ComponentIds("feedbacker", ("action", "user_id", "star_count", "submit_channel_id"),
legacy_prefix="feedbacker@")`: v3's fields in v3's declaration order (letters a to d), all text
(v3 declared them `FieldType.STRING`, so no `legacy_hex`), and v3's `component_prefix`. The
templates keep v3's `uid` maps and their order, so a star button's ID is
`feedbacker:1:a=submit_star;b=<member>;d=<channel>;c=<stars>` (74 characters with 19-digit IDs)
and the modal's is `feedbacker:1:a=submit_form;c=<stars>;d=<channel>`. `setup` routes them to
`Feedbacker.handle`, which sends a component interaction with the action `submit_star` to
`press_star` and a modal submission with `submit_form` to `submit_form`; other actions get no
response, as v3 had no handler for them. A v3 ID is parsed by the core's legacy decoder, and the
core upgrades the form's buttons after the handler ran.

### Command

- `Feedbacker.command()` builds `feedbacker` with `app_commands.Command` and the cog's bound method
  `create_form`: v3's base name and description (`Register.kt:23`), `rename` and `describe` from
  `register.yaml` (`feedbacker.options.member.*` and `feedbacker.options.submit-channel.*`; v3's
  lookup key `submitChannel` is the YAML key `submit-channel`). A guild command without default
  permissions: as in v3, every member sees it and the callback checks Administrator.
- `member: discord.Member | discord.User`: discord.py sends a user option and passes the member
  that Discord resolved, or the user when it resolved none (a user outside the guild). A
  `discord.Member` annotation would make discord.py raise before the callback and leave the
  response "thinking", as v3's `asMember!!` did.
- `submit_channel: app_commands.Transform[app_commands.AppCommandChannel, TextChannelOption]`: a
  transformer with `channel_types` `[text]`, as v3's `setChannelTypes(ChannelType.TEXT)`, copied
  from WelcomeByeGuild (`discord.TextChannel` would also offer announcement channels). Feedbacker
  is its second user and no other v3 command restricts a channel option, so it stays in the plugins.
- The command tree defers the command ephemerally, as v3's core did, and every answer edits that
  response.

### Creating a form

`create_form(interaction, member, submit_channel)` follows v3's order:

1. Without Administrator (`interaction.permissions.administrator`, as WelcomeByeGuild reads v3's
   `member.hasPermission`), the response becomes `form_no_permission`. In a DM, where guild
   commands never run, the permissions have no Administrator either, so v3's silent
   `isFromGuild` guard needs no counterpart.
2. A submit channel whose type is not `ChannelType.text` (Discord offers none, as v3's check was
   defensive), or a `member` that is not a guild member (checked against the core's `MemberLike`
   Protocol), makes the response `form_failure` and logs a warning.
3. `ask-message` is rendered in `interaction.locale` (v3's `event.userLocale`) with
   `actor_values(member, bot)` (v3's `Placeholder.get(member)`) and `fb_submit_channel_id`, and the
   IDs from `IDS.build`. The whole message (content, embeds, view and files) is posted to
   `interaction.channel`, checked as `object` against a `Postable` Protocol (SimpleCommand's
   `_postable`); then the response becomes `form_success`. A channel without `send` or a
   `discord.HTTPException` makes the response `form_failure` and logs a warning.

### Pressing a star

`press_star(interaction, fields)`:

1. A user whose ID is not the button's `user_id` (compared as text, as v3) gets `form_not_you` in
   an ephemeral reply.
2. The star count is checked (see "Stars"); a bad one raises before anything is sent.
3. `fill-form` is rendered in `interaction.locale` with `placeholder_values(interaction)` (v3's
   `Placeholder.get(event)` for the button), `fb_star_count` and `fb_submit_channel_id` from the
   ID, and sent with `response.send_modal`.
4. Then `form.highlight(message, pressed)` rebuilds the message's components
   (`View.from_message`, or `LayoutView.from_message` for a Components V2 message, as the core's
   upgrade does), makes the pressed button primary and every other button with an ID secondary,
   stops the view, and `message.edit(view=...)` sends it with the bot's token. A
   `discord.HTTPException` there logs a warning; the modal is already open. Link and premium
   buttons keep their style, and the message's other components stay.

### Submitting the modal

`submit_form(interaction, fields)`:

1. The star count, the submit channel ID (`int`) and the input `form` (`modal_values`, empty when
   the member left it empty) are read; a bad star count or channel ID raises before any response.
2. `response.defer()`: for a modal submission discord.py sends a deferred message update, v3's
   `deferEdit`. The modal closes and nothing is shown.
3. The submit channel is `interaction.guild.get_channel(id)` if it is a text channel that takes
   messages (v3's `getTextChannelById`: the guild's cache, text channels only).
4. `print-result` is rendered in the guild's locale (`interaction.guild_locale`, else the user's,
   as WelcomeByeGuild), with `actor_values(interaction.user, bot)` (v3's
   `Placeholder.get(event.member)`), `fb_stars` and `fb_content`, and posted whole to the channel.
5. Only after the review is posted, `interaction.message.delete()` deletes the form with the bot's
   token, as v3's `event.message?.delete()`; a `discord.HTTPException` logs a warning (the second
   of two submissions from two clients finds the form gone).
6. When there is no such channel (step 3) or the channel refuses the review (step 4), the form
   stays, the member gets `form_submit_failure` through `followup.send(..., ephemeral=True)`, and a
   warning names the channel and the guild.

### Stars

`form.stars(count)` is v3's `"★ ".repeat(n) + "☆ ".repeat(5 - n)`, trailing space included.
`form.star_count(text)` reads a star count from an ID and accepts the whole numbers 0 to 5 (the
range in which v3's `repeat` did not throw); anything else raises `ValueError`, which the core logs
with the plugin's name. The press checks it before the modal opens, so a bad count in an operator's
template fails at once instead of after the member typed a feedback.

### Core: embed fields

`render_message` gives every embed field JDA's treatment (`MessageEmbed.Field`, through v3's
`addField`): the name and the value lose their leading and trailing characters up to U+0020 (Java's
`String.trim`, not Python's `str.strip`, which would also remove U+3000 and other spaces), and an
empty result becomes U+200E (JDA's `EmbedBuilder.ZERO_WIDTH_SPACE`). Fields from a `model_key` get
the same, as JDA's constructor checked them too. Without it, Discord refused a review with an empty
feedback (`embeds.0.fields.0.value` is required), and VoiceLogger's and ChatLogger's templates,
whose values end with newlines that JDA trimmed, would show them.

### Core: modal values

`xincord.core.templates.modal_values(data)` returns `{custom_id: value}` for the text inputs (type
4) of a modal submission's `components`: inside labels (type 18, `component`), as `render_modal`
sends them (JDA 6's `Label.of` in v3), and inside action rows (type 1, `components`), as older
modals sent them. Other components (text displays, selects) are skipped. discord.py parses
submissions only for the `Modal` objects it dispatches, and the core stops its modals and routes
the raw interaction instead.

### Tests

- `tests/plugins/feedbacker/`: `test_plugin.py`, `test_config.py`, `test_stars.py`,
  `test_create.py`, `test_press.py`, `test_submit.py`, `test_command.py` and `test_routes.py`;
  `conftest.py` loads the plugin through its entry point and finds the cog with `cast`, because
  `test_config.py` loads invalid configs. `tests/core/test_templates_render.py` and
  `tests/core/test_templates_submission.py` cover the core changes.
- `tests/fixtures/plugins/feedbacker/golden.yaml`: the bundled replies, v3's prompt, modal and
  review per locale, the star texts and the translated command payload.
- `discord_fakes` gains `FakeMessage` (components, flags, edits and deletion into `sent`, fetched
  by its channel until deleted), `FakeResponse.send_message` and `send_modal`,
  `FakeInteraction.followup` and `not_found()`.

### v3 behaved differently

- v3 behaved differently: a missing submit channel sent "Submit channel not found" through the
  interaction hook before anything acknowledged the submission, so the member saw a failed modal
  and never the text (inventory B1). The submission is acknowledged first; the member gets
  `form_submit_failure` and the form stays, as it stayed in v3.
- v3 behaved differently: a `member` option naming a user outside the guild threw in `asMember!!`
  and left the administrator's response "thinking" (B2); it answers `form_failure`.
- v3 behaved differently: the star restyle was queued on the interaction hook before the modal
  acknowledged the press, and Discord may refuse that edit silently (B3); the bot edits its own
  message after the modal opened, and a refusal is logged.
- v3 behaved differently: the form was deleted while the review was being posted, so a refused
  review lost the feedback (B4); the form is deleted only after the review is posted, and otherwise
  stays for another try while the member gets `form_submit_failure`.
- v3 behaved differently: without a member, the submission wrote its values into the global
  placeholders for good (B5); every render has its own values.
- v3 behaved differently: the feedback text went through recursive placeholder expansion, so
  `%user_id%` became an ID and a text containing `%fb_content%` made the modal fail (B6); it is
  shown as typed.
- v3 behaved differently: `SubmitChannel must be TextChannel` and `Submit channel not found` were
  hard-coded English next to the localized templates (B7); every reply is in `config.yaml`, with
  zh-TW texts in the bundled file.
- v3 behaved differently: a channel that refused the prompt left the administrator's response
  "thinking"; it answers `form_failure` and logs a warning.
- v3 behaved differently: a star count above 5 or below 0 threw in `repeat` after the member had
  typed a feedback; such a count fails the press before the modal opens.
- v3 behaved differently: the command needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers it.
- v3 behaved differently: a config without one of the three replies, or with an unknown key,
  stopped the whole bot even with the plugin disabled; only Feedbacker is disabled, unknown keys
  warn, and the file is read only when `plugins` lists the plugin.

Kept on purpose: the command visible to everyone with the runtime Administrator check; the replies
as written, not localized and without placeholders; the locale of each part (the administrator's
for the prompt, the member's for the modal, the guild's for the review); five gray buttons and the
blue pressed star; the star text with its trailing space; no timeouts (prompts stay valid until
deleted); unknown actions without a response; no check of the bot's permissions in the submit
channel when the form is created; a double submission from two clients posting two reviews (the
second deletion is a logged warning, as JDA logged it).

## Risks / Trade-offs

- A modal opened under v3 and submitted after the switch carries a v3 ID: the review is posted and
  the form deleted, then the core's legacy upgrade cannot fetch the deleted form and logs an error.
  Such a modal must stay open across the restart, so this is left as it is.
- The highlight is a second request after the modal opened; Discord's rate limits make it lag at
  worst, and the review flow does not depend on it.
- `TextChannelOption` now exists in WelcomeByeGuild and Feedbacker; no other v3 command restricts a
  channel option.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [Feedbacker]` in `config.yaml`, a second account and
two text channels, `#general` and `#reviews`:

1. Start the bot: the log lists `Feedbacker` as loaded; `plugins/Feedbacker/config.yaml` and the
   eight files under `plugins/Feedbacker/lang/` exist.
2. As an administrator with an en-US client, `/feedbacker` is listed with its en-US description;
   `submit-channel` lists text channels only.
3. As the second account (no Administrator), `/feedbacker` is listed; running it replies
   `form_no_permission` and posts nothing.
4. As the administrator in `#general`, run `/feedbacker member:<second> submit-channel:#reviews`:
   `#general` shows the en-US prompt over five gray star buttons, and the ephemeral response is
   `form_success`.
5. As the administrator, press a star: an ephemeral `form_not_you`, no modal.
6. As the second account, press the three-star button: the modal opens in that account's
   language, and the three-star button turns blue.
7. Close the modal and press the five-star button: it turns blue and the three-star one gray.
8. Submit a feedback: `#reviews` shows the review (the account's username in the title, five stars,
   the text, the avatar, color #60C0C0) in the guild's language, and the prompt is deleted.
9. Make a new form and submit an empty feedback: the review is posted with an empty-looking field.
10. Make a new form, deny the bot Send Messages in `#reviews` and submit: an ephemeral
    `form_submit_failure`, the prompt stays and the log has a warning; allow it again and submit
    again from the same prompt: the review is posted.
11. Make a new form, delete `#reviews` and submit: `form_submit_failure`, the prompt stays.
12. Deny the bot Send Messages in `#general` and run the command there: `form_failure` and a
    warning.
13. Run the command with the ID of a user who is not in the guild: `form_failure` and a warning.
14. Submit a feedback containing `%user_id%`: the review shows it as typed.
15. If a prompt posted by v3 still exists, press one of its stars: the modal opens, and the log
    shows no upgrade error; submit: the review is posted.

## User-visible changes

Copy: two new replies, `form_failure` (bundled `建立失敗`, default `Failed to create the form`) and
`form_submit_failure` (bundled `送出失敗`, default `Failed to submit the feedback`); v3's
hard-coded `SubmitChannel must be TextChannel` and `Submit channel not found` are gone.

1. When the form cannot be created (the `member` option names a user outside the guild, the bot
   cannot post in the channel, or the submit channel is not a text channel), the administrator gets
   `form_failure` and the log says why (v3: "thinking" forever, or the English text for the
   channel type).
2. When the review cannot be posted (the submit channel is gone or refuses the bot), the member gets
   `form_submit_failure`, the prompt stays for another try and the log says why (v3: a failed modal,
   or the feedback lost with the prompt deleted).
3. The prompt is deleted only after its review is posted.
4. The feedback text is shown as typed (v3 expanded `%...%` in it).
5. A star count outside 0 to 5 in an operator's template fails the press at once (v3: after the
   member typed a feedback).
6. A blank reply, or one longer than 2000 characters, in `config.yaml` disables the plugin with the
   key named; a v3 `config.yaml` loads unchanged and warns `unknown key enabled`.
7. The command always answers (v3 needed the core's auto-defer switch).
8. v3's prompts keep working; after the first press their buttons carry new-format IDs.
9. Core, for every plugin: embed field names and values are trimmed and empty ones show U+200E, as
   v3 did through JDA (xincord sent them as rendered until now).
