## Why

Decision C1 ports Feedbacker after IntervalPusher, and F3 lists it as in use. v3's Feedbacker
(`Plugins/Feedbacker`, 5 Kotlin files, 314 lines) is a customer-service review flow: an
administrator runs `/feedbacker member submit-channel`, the bot posts a public "please rate us" embed
with five star buttons that only that member can press, a press opens a feedback modal, and the
submission is posted as a review embed in the submit channel before the prompt is deleted. It is the
first port with v3 component IDs to decode and the first that reads a modal submission.

## What Changes

- New plugin package `xincord.plugins.feedbacker`, registered as `Feedbacker`, with no intents
  beyond discord.py's defaults, v3's en-US and zh-TW lang files (`register.yaml`, the
  `ask-message` and `print-result` messages and the `fill-form` modal) and a bundled `config.yaml`.
- `config.yaml` keeps v3's three required replies (`form_no_permission`, `form_not_you`,
  `form_success`), shown as written, and adds `form_failure` and `form_submit_failure` with English
  defaults, so v3 files load unchanged and v3's `enabled` key only warns. A blank reply, or one
  over 2000 characters, disables the plugin with the key named.
- The guild command `/feedbacker` keeps v3's name, description, localizations and options (`member`;
  `submit-channel`, text channels only), visible to everyone, with v3's runtime Administrator check.
  It posts `ask-message` in the command's channel in the administrator's locale and answers
  `form_success` in the ephemeral response.
- Star buttons and the modal keep v3's flow and IDs: only the rated member gets the modal (others
  get `form_not_you`); the pressed star turns blue; the submission posts `print-result` in the
  guild's locale and then deletes the prompt. v3's prompts keep working, and their IDs are upgraded
  to the new format after their first use.
- Core (`core-templates`): embed fields are trimmed and empty ones get U+200E, as JDA did (an empty
  feedback otherwise makes Discord refuse the review), and `modal_values(data)` reads the text
  inputs of a modal submission.
- v3's defects are fixed: a failed submission or a missing submit channel no longer leaves the
  member with a failed modal or a lost feedback (the prompt stays and the member gets
  `form_submit_failure`); a member option naming a user outside the guild, a non-text submit
  channel or a channel that refuses the prompt answers `form_failure` instead of hanging or
  showing hard-coded English; the star highlight uses the bot's message edit instead of an
  unacknowledged hook; the feedback text is no longer expanded as placeholders.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Event.kt:15-75`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:23-161`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/command/Register.kt:10-35`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/command/CmdFileSerializer.kt:7-25`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/config/ConfigSerializer.kt:6-18`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/config.yaml:1-5`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/info.yaml:1-10`
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml:1-10`, `message/ask-message.yaml:1-54`, `message/print-result.yaml:1-12`,
  `modal/fill-form.yaml:1-14`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:29-57`
  (`Placeholder.get` for users and members)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v1/builder/MessageBuilder.kt:185-205`
  (fields through JDA's `addField`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30` (the
  ephemeral auto-defer)

Out of scope: prompts made before v3's commit `ac6e90d` (their IDs lack the submit channel and
were already broken in v3); preventing a double submission from two clients (v3 posted both);
checking the bot's permissions in the submit channel when the form is created (a refusal is
handled when the feedback is posted); localizing the config replies (v3 used them as written); the
Web Dashboard's toggle and reload (B13).

## Capabilities

### New Capabilities

- `plugin-feedbacker`: the Feedbacker plugin.

### Modified Capabilities

- `core-templates`: embed fields follow JDA's trimming, and modal submissions can be read back.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/feedbacker/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/feedbacker/` and golden data
in `tests/fixtures/plugins/feedbacker/`; new fakes in `tests/support/discord_fakes.py` (messages,
modal responses and follow-ups). Core: `xincord.core.templates` trims embed fields as JDA did,
which every plugin's templates get, and exports `modal_values`. No new dependencies and no
storage. Operators who move from v3 keep their `plugins/Feedbacker/config.yaml` and `lang/` files.
