# Feedbacker: porting inventory (branch `main`)

Repo: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. JDA 6.4.1, kaml 0.104.0, commons-text 1.15.0, coreApi `3.4`.
Line references are relative to `Plugins/Feedbacker/src/main/kotlin/feedbacker/` unless prefixed with `Core:` (= `Core/src/main/kotlin/core/`) or `res:` (= `Plugins/Feedbacker/src/main/resources/`). JDA behaviours I quote were checked in JDA 6.4.1 bytecode; anything marked **(unverified)** was not.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/Feedbacker` |
| Kotlin files / LOC | 5 files, 314 physical lines (269 non-blank): `Feedbacker.kt` 161, `Event.kt` 75, `command/Register.kt` 35, `command/CmdFileSerializer.kt` 25, `config/ConfigSerializer.kt` 18 |
| Resources | `config.yaml`, `info.yaml`, `lang/{zh-TW,en-US}/register.yaml`, `lang/*/message/{ask-message,print-result}.yaml`, `lang/*/modal/fill-form.yaml` (10 files) |
| Tests | none |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:15). `listener = true` |
| Build | `plugins { id("xs-plugin") }` (Core compileOnly only); `version.patch=0` → `3.4.0-SNAPSHOT` |

**Purpose.** An administrator runs `/feedbacker member:<user> submit-channel:<text channel>` and the bot posts a public "please rate us" embed with five star buttons. Only the named member can press a star. Pressing one opens a feedback modal; on submit, the bot posts a review embed (stars plus text) to the submit channel and deletes the rating prompt. This is a customer-service review flow for the same "❖ ORDERLY SERVER ❖" community.

**info.yaml** (`res:info.yaml`, after Gradle expansion):
```yaml
author: xinshoutw
name: Feedbacker
coreApi: "3.4"
version: 3.4.0-SNAPSHOT
main: "tw.xinshou.discord.plugin.feedbacker.Event"
component_prefix: "feedbacker@"
```
It declares no intents, cache flags, member cache policies, dependencies, or description.

---

## 2. Lifecycle

- **load()** (Event.kt:18-31): `super.load()` exports `lang/` to `plugins/Feedbacker/lang/` (non-destructive) and reads `plugins/Feedbacker/config.yaml` (kaml strict mode; the three message keys are required).
  - If disabled: logs WARN `Feedbacker is disabled.` and returns.
  - Otherwise: builds `StringLocalizer<CmdFileSerializer>(plugins/Feedbacker, default zh-TW)`.
- **reload()** (Event.kt:33-48): re-reads the config. If disabled, it logs the WARN and returns. If enabled, it rebuilds the localizer and calls `Feedbacker.reload()`, which rebuilds the `MessageCreator` and `ModalCreator` (Feedbacker.kt:46-57).
- **unload()**: not overridden.
- **guildCommands()** (Event.kt:50-56): an empty array when disabled, otherwise `/feedbacker`.
- **Lazy initialization:** the `Feedbacker` object (Feedbacker.kt:23-44), which holds the `ComponentIdManager`, the v2 `MessageCreator`, and the `ModalCreator`, initializes on first access.
- **Background jobs:** none.
- **In-memory state:** none beyond the creators. All flow state lives in the custom IDs and in the prompt message, so prompts keep working across restarts.

---

## 3. Slash commands

### `/feedbacker`
- **Guild** command. Core registers it in every guild and again on guild join.
- Base name `feedbacker`, description `Create a feedback form for a member` (Register.kt:22-35).
- **No `default_member_permissions`**: every member sees the command, and the ADMINISTRATOR check happens at runtime. No `guild_only` or NSFW flags.
- Localizations come from `register.yaml` through `StringLocalizer`. Keys are Kotlin property paths: `feedbacker.name`, `feedbacker.options.member.name`, `feedbacker.options.submitChannel.name`, and the matching descriptions.
  - zh-TW: `評價表單` / `為使用者建立一個評價選單`.
  - en-US: `feedbacker` / `create a channel for member feedback`.
- Options:

  | name | type | required | description | localizations |
  |---|---|---|---|---|
  | `member` | USER | yes | `Specify the member` | zh-TW `member`/`誰`; en-US `member`/`who` |
  | `submit-channel` | CHANNEL, channel_types = [TEXT] | yes | `Specify the submit channel` | zh-TW `submit-channel`/`回饋結果要送到哪個頻道`; en-US `submit-channel`/`where to send the feedback result` |

  No choices, min/max, or autocomplete.

**Behavior** (Event.kt:58-62 → Feedbacker.kt:59-84). The interaction is already deferred as an ephemeral reply by Core's InteractionLogger (Core: logger/InteractionLogger.kt:25-30), so every answer edits that ephemeral original.
1. Routing requires `config.enabled` and `event.fullCommandName == "feedbacker"` (via `GlobalUtil.checkCommandString`).
2. `if (!event.isFromGuild) return`: no response. Unreachable for a guild command.
3. `member = event.member ?: return`.
4. If the invoker lacks guild **ADMINISTRATOR**, edit the original to `config.form_no_permission` (default `您沒有權限！`) and stop.
5. If `submit-channel` is not a TEXT channel, edit the original to `SubmitChannel must be TextChannel` (hard-coded English) and stop. This is defensive; the option is already restricted to TEXT.
6. Send **ask-message** publicly to `event.channel`, the channel where the command ran. It is rendered with the **invoker's** `userLocale` and with the substitutor `Placeholder.get(targetMember)` plus `fb_submit_channel_id = submitChannel.id`.
   - `getOption("member").asMember!!` throws an NPE if the selected user is not a guild member, and the ephemeral reply stays "thinking" (bug B2).
7. After the send succeeds, edit the ephemeral original to `config.form_success` (default `建立成功`). If the send fails, for example because of missing permissions, the reply is never edited.

**Ask-message** (`res:lang/*/message/ask-message.yaml`):
- Embed:
  - title: `請給予星等與評價` (zh-TW) / `Please provide a rating and review` (en-US)
  - footer: `❖ ORDERLY SERVER ❖`
  - no colour
- One row of five SECONDARY (gray) buttons labelled `★`, `★★`, `★★★`, `★★★★`, `★★★★★`. Custom IDs are listed in §4.

---

## 4. Components

`ComponentIdManager(prefix = "feedbacker@")` (Feedbacker.kt:24-32). Every field is a STRING. Short keys are assigned in this order:

| key | short |
|---|---|
| action | `a` |
| user_id | `b` |
| star_count | `c` |
| submit_channel_id | `d` |

Encoding follows the YAML map order. Parsing is order-independent. IDs are limited to 100 characters (checked after substitution).

| Component | custom_id (exact order as emitted) | Who can use | Behavior |
|---|---|---|---|
| Star button ×5 (persistent, public) | `feedbacker@a:submit_star;b:{targetUserId};d:{submitChannelId};c:{1..5}` | Only the user whose id is in `b`; anyone else gets an ephemeral `config.form_not_you` (default `這個表單不是為你建立的！`) | See below |
| Feedback modal | `feedbacker@a:submit_form;c:{1..5};d:{submitChannelId}`, text input `form` | The user the modal was shown to | See below |

There are no timeouts: prompts stay valid until deleted. Messages created before commit `ac6e90d` (2026-03-01) use IDs with no `d:` and a separate `fill_form` action, and are already broken on main. Clicking one throws an NPE on the missing `submit_channel_id` or matches no handler.

**Star button** (`handleStarBtn`, Feedbacker.kt:100-137):
1. If `b != event.user.id`, reply ephemerally with `form_not_you` and stop.
2. Rebuild the message's action rows. Every Button gets style **PRIMARY** if its custom_id equals the clicked one, otherwise **SECONDARY**. Non-button components are copied unchanged.
3. Queue `event.hook.editOriginalComponents(rows)` **before** acknowledging. JDA holds hook requests until the interaction is acknowledged (`InteractionHookImpl.readyCallbacks`, verified). It is unverified whether Discord accepts PATCH `@original` after a MODAL response (bug B3).
4. Reply with the modal (`res:lang/*/modal/fill-form.yaml`), rendered in the **clicker's** `userLocale`. The substitutor is `Placeholder.get(buttonEvent)` plus `fb_star_count` and `fb_submit_channel_id` taken from the button ID.
   - Title: `您覺得今天的服務怎麼樣呢？ :D` (zh-TW) / `How was today's service? :D` (en-US).
   - Input `form`: PARAGRAPH, label `請簡述評價內容` / `Please briefly describe your feedback`, placeholder `超讚` / `Awesome!`, `max_length` 1024, no min, **optional**.

**Modal submit** (`handleFormSubmit`, Feedbacker.kt:139-160):
1. `stars = c.toInt()`.
2. The substitutor is `Placeholder.get(event.member)` (the submitter). If `member` is null it falls back to the **global** substitutor, which permanently mutates it (bug B5). The handler then puts:
   - `fb_stars` = `"★ ".repeat(stars) + "☆ ".repeat(5 - stars)`. Example for 3 stars: `★ ★ ★ ☆ ☆ `, with a trailing space.
   - `fb_content` = the `form` value (may be `""`).
3. Look up `submitChannel = guild.getTextChannelById(d)` from cache. If it is missing, `event.hook.editOriginal("Submit channel not found")` is queued while the interaction is still unacknowledged and nothing ever acknowledges it. The hook request times out, the user sees a Discord modal error, and the text never shows (bug B1).
4. `event.deferEdit()` (DEFERRED_UPDATE_MESSAGE, valid for a modal opened from a component), then send **print-result** to the submit channel, rendered in `event.guildLocale`, the guild's preferred locale.
5. Concurrently, and regardless of whether step 4 succeeds, `event.message?.delete()` removes the star prompt (bug B4: if posting fails, the feedback is lost).

**Print-result** (`res:lang/*/message/print-result.yaml`):
- Embed:
  - title: `☛ 來自 %user_name% 的新評價` (zh-TW) / `☛ New Review from %user_name%` (en-US). `user_name` is the submitter's **username**, not their display name.
  - description: `%fb_stars%`
  - thumbnail: `%member_avatar_url%`, the submitter's effective (guild) avatar. It is dropped if the URL does not start with `http`.
  - colour: `#60C0C0`
  - footer: `❖ ORDERLY SERVER ❖`
  - one field: name `評價內容` / `Review Content`, value `%fb_content%`.
- JDA field handling (verified): the name and value are trimmed; an empty value becomes U+200E; a value longer than 1024 characters throws.

---

## 5. Events

| JDA event | Filter | Behavior |
|---|---|---|
| `SlashCommandInteractionEvent` | enabled and `fullCommandName == "feedbacker"` | §3 |
| `ButtonInteractionEvent` | enabled and custom_id starts with `feedbacker@` | Parse the ID. `action == "submit_star"` → star handler. Any other action: nothing (no ack) |
| `ModalInteractionEvent` | enabled and modal id starts with `feedbacker@` | `action == "submit_form"` → submit handler. Any other action: nothing |

A malformed ID that carries the prefix makes `parse` throw, so the interaction is never acknowledged.

---

## 6. Configuration

`plugins/Feedbacker/config.yaml` (default values from `res:config.yaml`):

| Key | Type | Required | Default | Use |
|---|---|---|---|---|
| `enabled` | Boolean | no (serializer default `false`) | `false` | When false: no command registered, every handler is a no-op |
| `form_no_permission` | String | **yes** | `您沒有權限！` | Ephemeral reply when the invoker lacks ADMINISTRATOR |
| `form_not_you` | String | **yes** | `這個表單不是為你建立的！` | Ephemeral reply when someone other than the target presses a star |
| `form_success` | String | **yes** | `建立成功` | Ephemeral confirmation after the prompt is posted |

- These strings are used verbatim. They are not localized and not substituted.
- kaml strict mode means a missing required key or an unknown key fails the plugin load, and Core then exits the application (Core: base/PluginLoader.kt:145-155, Main.kt:21-31). The required keys must exist even when the plugin is disabled.
- `enabled` can be toggled at runtime from the dashboard or via reload.

---

## 7. Localization and templates

- Locales: `zh-TW` (default) and `en-US`. Files are exported to `plugins/Feedbacker/lang/` and loaded from disk.
- **Locale used per artifact:**

  | Artifact | Locale source |
  |---|---|
  | ask-message | invoker's `userLocale` |
  | modal | clicker's (target's) `userLocale` |
  | print-result | the **guild's** locale |

  A locale with no directory falls back to zh-TW. A locale directory that exists but lacks the key throws (Core: builtin/messagecreator/v2/MessageCreator.kt:130-134).
- `register.yaml`: command and option localizations only (§3).
- Message templates are loaded by the MessageCreator v2 class using the legacy v1 schema with `!ButtonsComponent`: `ask-message`, `print-result`.
- Modal templates use ModalCreator: `fill-form`.
- **Placeholders**:

  | Placeholder | Defined by | Used in |
  |---|---|---|
  | `%fb_submit_channel_id%` | slash handler, then the star handler | star button uid, modal uid |
  | `%fb_star_count%` | star handler | modal uid |
  | `%fb_stars%` | submit handler | print-result description |
  | `%fb_content%` | submit handler | print-result field |
  | `%user_id%` | Core member substitutor (target member) | star button uid |
  | `%user_name%`, `%member_avatar_url%` | Core member substitutor (submitter) | print-result |

- Star buttons carry `star_count: 1..5` as YAML integers; they are decoded as strings.
- **Substitution semantics** (Core: builtin/placeholder/Substitutor.kt): Apache StringSubstitutor with `%` as both delimiters and `$` as the escape character. Unknown keys are left as they are, and **values are substituted recursively**. User feedback text is therefore expanded: `%user_id%` inside the text becomes an ID, `$%x%` loses the `$`, and text containing `%fb_content%` creates a cycle that throws `IllegalStateException`, so the modal fails (bug B6).
- Per-user substitutors are cached globally in Core and mutated by these `put` calls; the writes leak across plugins and are never evicted.

---

## 8. Persistence

None: no Mongo, JSON, SQLite, or other files. State lives in the custom IDs (target user, star count, submit channel) and in the prompt message itself.

Compatibility requirement: existing prompts in guilds use the custom-ID formats in §4, and the port must decode them.

---

## 9. External dependencies

- Gradle: nothing beyond Core.
- HTTP: Discord API only. No credentials.
- Plugin dependencies: none.

---

## 10. Discord requirements

- Intents: none declared. The command's `member` option is resolved from the interaction payload, so no cache is needed. Core always enables GUILD_MEMBERS.
- Caches: the submit channel is looked up through JDA's channel cache.
- Bot permissions:
  - Invocation channel: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS.
  - Submit channel: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS.
  - Deleting its own prompt needs nothing extra.
- Rate limits: negligible. A submit costs one message send and one delete.

---

## 11. Concurrency

- There is no shared mutable state besides Core's substitutor caches. They are plain `HashMap`s mutated from event and callback threads; races are possible but benign.
- Star handler ordering: the queued hook edit waits for the modal acknowledgement.
- Submit handler: the deferEdit/send chain and the prompt delete run concurrently.
- Nothing on the server side prevents a double submit. If the target opens modals from the same prompt in two clients (for example desktop and mobile) and submits both before the prompt is deleted, both results are posted. The second delete fails harmlessly (Unknown Message, logged). Within a single client, the prompt's deletion prevents this.

---

## 12. Bugs, quirks, hard-coded values

**Probable bugs to fix:**
- **B1** "Submit channel not found" is sent through the hook before any acknowledgement and nothing acknowledges the interaction (Feedbacker.kt:147-151). The user sees a generic modal failure. Fix: reply ephemerally.
- **B2** `asMember!!` NPEs for a non-member target, and the ephemeral reply stays "thinking" (Feedbacker.kt:77).
- **B3** The components edit is queued on the hook before the modal acknowledgement (Feedbacker.kt:124). Whether Discord accepts it after a MODAL response is unverified, so the restyle may silently fail. Port: use `interaction.message.edit(...)` (bot token).
- **B4** The prompt is deleted before the result is confirmed (Feedbacker.kt:153-159), so feedback is lost if the post fails.
- **B5** When `event.member` is null, the global substitutor is mutated (Feedbacker.kt:141).
- **B6** User content goes through recursive placeholder substitution. A cycle makes the handler throw and the modal fails. The trailing space in `fb_stars` is cosmetic.
- **B7** Hard-coded English errors (`SubmitChannel must be TextChannel`, `Submit channel not found`) next to localized templates.

**Behavior to preserve (or decide):**
- The command is visible to everyone; the runtime check requires ADMINISTRATOR.
- Only the target member can rate.
- The chosen star is highlighted (PRIMARY vs SECONDARY).
- Feedback text is optional (max 1024).
- One result per prompt; the prompt is deleted on submit.
- The locale choice for each artifact (§7).
- The star string format and all template text.

**Hard-coded values:** five stars, `#60C0C0`, footer `❖ ORDERLY SERVER ❖` (in templates).

---

## 13. Testability

Pure functions to extract:
- `stars_text(n)` → `"★ "*n + "☆ "*(5-n)` (cover 1..5; decide what out-of-range does);
- the custom-ID codec, with golden IDs from §4 and order-independent parsing;
- `restyle_rows(rows, clicked_id)`;
- `can_rate(id_user, clicker_id)`;
- the permission gate (`is_admin`);
- template rendering for the ask, result, and modal dicts, including placeholder semantics such as recursion, escapes, and unknown keys;
- config schema validation (required keys, strict mode).

Needs Discord test doubles:
- the slash interaction after the auto-defer (edit-original tracking);
- channel send and delete;
- button interaction responses (ephemeral reply, modal);
- modal submit (`defer_update`);
- guild channel cache lookup;
- message edit.

---

## 14. Porting assessment

**Difficulty: Low–Medium.** The flow is small, but the port needs persistent dynamic buttons, modal custom-ID compatibility, placeholder parity, and decisions on the hook-ordering bugs.

**discord.py mapping:**
- `app_commands.command(name="feedbacker")` with `member: discord.Member` and `submit_channel: discord.TextChannel` (`@app_commands.rename(submit_channel="submit-channel")`).
  - Leave default permissions unset and check `interaction.user.guild_permissions.administrator` at runtime.
  - Localize through an `app_commands.Translator`.
  - Emulate Core's auto-defer (`defer(ephemeral=True, thinking=True)`), then respond with `edit_original_response`.
- Star buttons: a `discord.ui.DynamicItem[discord.ui.Button]` with template `feedbacker@(?P<body>.+)` decoded by the ported codec, or a raw `on_interaction` dispatcher. Respond with `interaction.response.send_modal(FeedbackModal(custom_id=…))`, then `await interaction.message.edit(view=restyled)`.
- Modal: `discord.ui.Modal(title=…, custom_id="feedbacker@a:submit_form;c:N;d:CID")` containing `TextInput(custom_id="form", style=paragraph, required=False, max_length=1024, placeholder=…)`. Submit: `interaction.response.defer()` (deferred update), `channel.send(embed=…)`, `interaction.message.delete()`.

**Risks:**
- Custom-ID compatibility for live prompts.
- Placeholder-engine parity.
- Locale selection rules.
- Whether to keep the deletion-before-confirmation behavior.
