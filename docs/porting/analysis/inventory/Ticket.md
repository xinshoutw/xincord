# Ticket: porting inventory (branch `main`)

Repo: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Runtime: JDA 6.4.1, kaml 0.104.0, Moshi 1.15.2, commons-text 1.15.0 (all from Core). coreApi `3.4`.
Line references are relative to `Plugins/Ticket/src/main/kotlin/ticket/` unless prefixed with `Core:` (= `Core/src/main/kotlin/core/`) or `res:` (= `Plugins/Ticket/src/main/resources/`).
Where JDA internals matter I checked the JDA 6.4.1 bytecode (bundled in `Server/Core-4.0.2-SNAPSHOT.jar`). Anything marked **(unverified)** is an inference I could not confirm.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/Ticket` |
| Kotlin files / LOC | 8 files, 1583 physical lines (1377 non-blank) |
| Files | `Ticket.kt` 879 (runtime router, ticket creation, transcript engine) · `create/StepManager.kt` 332 (setup wizard router) · `create/StepData.kt` 196 (`Step` session + `StepData` defaults) · `Event.kt` 89 (entry) · `command/Register.kt` 43 · `command/CmdFileSerializer.kt` 26 · `json/serializer/JsonData.kt` 10 · `config/ConfigSerializer.kt` 8 |
| Resources | `config.yaml`, `info.yaml`, `lang/{zh-TW,en-US}/register.yaml`, `lang/*/message/*.yaml` (7 per locale), `lang/*/modal/*.yaml` (7 per locale): 32 files |
| Tests | none |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:18). `listener = true` |
| Build | `build.gradle.kts`: `plugins { id("xs-plugin") }` → `compileOnly(project(":Core"))` only. `gradle.properties`: `version.patch=0` → version `3.4.0-SNAPSHOT` |

**Purpose.** Admins build "ticket panel" messages (embed + up to 5 buttons) through an ephemeral wizard. When a member presses a panel button, a modal asks for a reason, and the bot creates a private text channel for that member plus the configured staff roles. The channel gets a control row with lock/unlock, "save transcript" (copies the channel history, including started threads, into a new public thread in another channel through a temporary webhook), and delete.

**info.yaml** (`res:info.yaml`), after Gradle `expand` (`build-logic/convention/src/main/kotlin/xs-jvm-conventions.gradle.kts:65-81`):
```yaml
author: xinshoutw          # ${author}
name: Ticket               # ${name} = Gradle project name
coreApi: "3.4"             # ${coreApi}
version: 3.4.0-SNAPSHOT    # ${version}
main: "tw.xinshou.discord.plugin.ticket.Event"
component_prefix: "ticket@"
```
No `require_intents`, `require_cache_flags`, `require_member_cache_policies`, `depend_plugins`, `soft_depend_plugins`, `depend_jars`, or `description`. `prefix` defaults to the name. **No relationship to TicketAddons is declared**, and neither plugin imports the other. See the TicketAddons report.

`Plugins/Ticket/README.md` lists the commands, message layouts, and modal ids. It mentions `confirm-add`, which code never uses. The root `README.md:289` advertises `/ticket create`, which does not exist (the real commands are `/create-ticket` and `/add-ticket`).

---

## 2. Lifecycle

- **load()** (Event.kt:21-34): `super.load()` exports jar `lang/**` to `plugins/Ticket/lang/**` without overwriting existing files unless CLI `-Flang` (Core: plugin/PluginEvent.kt:23-29). It then reads (exporting if missing) `plugins/Ticket/config.yaml` with kaml strict mode (Core: plugin/PluginEvent.kt:59-65).
  - If `enabled == false`: logs WARN `Ticket is disabled.` and returns. The localizer is not created.
  - Otherwise: creates `StringLocalizer<CmdFileSerializer>(plugins/Ticket, default zh-TW)` from `lang/*/register.yaml`.
- **reload()** (Event.kt:36-51): re-exports lang (non-destructive) and re-reads config. If disabled: WARN and return; in-memory state is kept and handlers become no-ops. If enabled: rebuilds the localizer, then `Ticket.reload()` rebuilds `MessageCreator` and `ModalCreator` from disk (Ticket.kt:91-103). `steps` and the JSON store are **not** reset or re-read.
- **unload()**: not overridden; Core only logs.
- **guildCommands()** (Event.kt:53-59): `emptyArray()` when disabled, else the 2 commands. The Web dashboard can flip `enabled` and call `PluginLoader.reloadPlugin` → `rebuildCommands` → `refreshCommandsStrict`, which overwrites guild commands in every guild (Core: dashboard/CoreDashboardBackend.kt:133-158, base/BotLoader.kt:150-159). The enabled flag therefore works as a runtime toggle.
- **Lazy initialization.** The `Ticket` object (Ticket.kt:56-89) initializes on first access (first interaction or first enabled reload). Initialization creates:
  - the JSON guild store, which eagerly loads and **rewrites** every `plugins/Ticket/data/*.json`;
  - the `ComponentIdManager`;
  - a v2 `MessageCreator`;
  - a `ModalCreator`.

  A broken lang YAML or a non-numeric `*.json` filename makes initialization throw, which leaves the plugin unusable until restart.
- **Background jobs:** none (no scheduler, timer, coroutine, or executor). The transcript engine is an asynchronous continuation chain running on JDA RestAction callback threads.
- **In-memory state:**
  - `StepManager.steps: HashMap<Long /*userId*/, Step>` (StepManager.kt:18). Holds setup sessions. Entries are never removed: not on confirm, reload, or unload. A user's next `/create-ticket` or `/add-ticket` replaces their entry. Lost on restart.
  - Each `Step` holds the slash command's `InteractionHook` (Discord token valid 15 min) and, for add mode, a snapshot `Message` of the target.
  - `Ticket.jsonGuildManager.mapper: MutableMap<Long, JsonFileManager>`: one in-memory copy per guild file.
  - Side effect in Core: `Placeholder.get(event).putAll("tt@…")` writes into Core's per-user/per-member substitutor caches. These caches are global, shared by every plugin, and never evicted (Core: builtin/placeholder/Placeholder.kt:19-58).

---

## 3. Slash commands

Both are **guild** commands. Core registers them per guild for every guild at startup and on `GuildJoinEvent` (Core: base/ListenerManager.kt:18-36). No `guild_only`/contexts are set (implicit for guild commands). Not NSFW. Name and description localizations come from `lang/<locale>/register.yaml` through `StringLocalizer`. Keys are the **Kotlin property paths**, not the YAML keys: `createTicket.name`, `addTicket.options.messageId.name` (Register.kt:16-27, Core: localizations/StringLocalizer.kt:69-97). `getLocaleData` uses `!!`, so a missing key throws while commands are being built.

**Auto-defer (Core).** Before any plugin listener runs, `InteractionLogger` calls `event.deferReply(true).queue()` (ephemeral "thinking") for every slash command and message-context command (Core: logger/InteractionLogger.kt:25-30). It is enabled by default and disabled by `--no-auto-defer-interactions` (Core: util/Arguments.kt:34-41). It runs first because Core registers its listener before the plugin listeners (Core: base/BotLoader.kt:87-100). All Ticket command handlers therefore answer through `event.hook` (editing the ephemeral original). With auto-defer disabled the handlers break: `hook.editOriginal` waits for an acknowledgement that never comes, then times out.

Routing: `Event.onSlashCommandInteraction` returns unless `config.enabled` and `event.name ∈ {"create-ticket","add-ticket"}` (Event.kt:61-65, Register.kt:11-14), then `StepManager.onSlashCommandInteraction` switches on `event.name` (StepManager.kt:20-25).

### 3.1 `/create-ticket`
- Base name `create-ticket`, description `create custom reason of ticket`. `default_member_permissions = ADMINISTRATOR` (Register.kt:30-33). No options.
- Localizations: zh-TW `建立客服按鈕` / `建立具有客服按鈕的訊息`; en-US `create-ticket` / `Create a message with ticket button.`
- No runtime permission check. Access depends only on Discord's default_member_permissions, which guild admins can override in Integrations.
- Behavior (StepManager.kt:27-31):
  1. Create `Step(hook, message=null)` with `StepData` defaults (§3.4).
  2. `hook.editOriginal(create-ticket template)`, rendered with the user's locale.
  3. `steps[userId] = step`, replacing any previous session.
- Resulting **ephemeral** setup panel (`res:lang/*/message/create-ticket.yaml`):
  - Embed: live preview (§3.4).
  - Row 1: preview button. Style = current button style, label/emoji = current button text/emoji, custom_id `ticket@b:prev`. See bug B1: this button does nothing.
  - Row 2 (all PRIMARY): `設定作者` `ticket@a:create;b:modify-author` · `設定文字` `…;b:modify-content` · `設定頻道目錄` `…;b:modify-category` · `設定顏色` `…;b:modify-color`.
  - Row 3: `設定按鈕文字` `…;b:modify-btn-text` · `設定按鈕顏色` `…;b:modify-btn-color` · `設定詢問標題` `…;b:modify-reason` · `設定允許身分組` `…;b:modify-admin` (PRIMARY) · `確定建立` `…;b:confirm-create` (SUCCESS).
  - en-US labels: `set author`, `set content`, `set category`, `set color`, `set btn text`, `set btn color`, `set ask title`, `set allow role`, `confirm create`.

### 3.2 `/add-ticket message_id:<string>`
- Base name `add-ticket`, description `create custom reason of ticket in the text-channel`. `default_member_permissions = ADMINISTRATOR` (Register.kt:35-43).
- Option `message_id`: STRING, required, description `for adding extra button`. No choices, min/max, or autocomplete. Localized names: zh-TW `訊息id` (`要添加按鈕的訊息Id`), en-US `message-id` (`The message id which button will be added.`).
- Command localizations: zh-TW `從已有訊息添加客服按鈕` / `第一行 ActionRow 至多 5 個按鈕`; en-US `add-ticket` / `Limit 1 Action, 5 buttons at most.`
- Behavior (StepManager.kt:33-51):
  1. `getOption("message_id").asLong`. A non-numeric value throws `NumberFormatException` and the ephemeral reply stays "thinking" (bug B7).
  2. `event.messageChannel.retrieveMessageById(id)`. It searches **only the channel where the command was used**.
  3. **Not found:** `hook.editOriginal("Cannot found the message by id: {id}")`. Quirk: `onErrorFlatMap` feeds that edited ephemeral reply into the following `flatMap`. The code then treats the reply as the target: it creates a `Step(hook, reply)`, stores it in `steps`, and fails rendering with `IndexOutOfBounds` because the reply has no embed. The user still sees the "Cannot found…" text (bug B8).
  4. **Found** and the first ACTION_ROW has **exactly 5** components → `hook.editOriginal("This message is full of buttons, please recreate a new message")`.
  5. Otherwise: `Step(hook, target)`, `steps[userId]=step`, edit the original with the add-ticket template.
     - Embed: `target.embeds[0]` (unchanged). Throws if the target has no embed: stuck "thinking" (bug B9).
     - Row 1: preview button.
     - Row 2: `設定頻道目錄`.
     - Row 3: `設定按鈕文字`, `設定按鈕顏色`, `設定詢問標題`, `設定允許身分組` (PRIMARY) and `確定建立` (SUCCESS).
     - Author, content, and colour cannot be edited in add mode.

### 3.3 Setup wizard: component interactions (`action=create`)
Dispatch: `Ticket.onButtonInteraction` with `action=="create"` → `StepManager.onButtonInteraction`, switching on `sub_action` (StepManager.kt:55-76). The session is `steps[event.user.idLong]`; the setup message is ephemeral, so only the invoker can click it.

| sub_action | No session | Behavior |
|---|---|---|
| `prev` | returns, **no ack** | Opens modal `preview-reason`. Unreachable (B1). |
| `modify-author` | `deferEdit` (silent) | Opens modal `modify-author`, prefilled with author and icon URL |
| `modify-content` | `deferEdit` | Opens modal `modify-content`, prefilled with title and description |
| `modify-category` | `deferEdit` | `deferEdit`, then `step.hook.editOriginal(modify-category)` |
| `modify-color` | `deferEdit` | Opens modal `modify-embed-color`, prefilled with `String.format("#%06X", color & 0xFFFFFF)` (StepManager.kt:148) |
| `modify-btn-text` | `deferEdit` | Opens modal `modify-btn-text`, prefilled with button text and `emoji.asReactionCode` |
| `modify-btn-color` | `deferEdit` | `deferEdit`, then edits the **clicked** message through the button's own hook (`it.editOriginal`, StepManager.kt:172-183) |
| `modify-reason` | `deferEdit` | Opens modal `modify-reason-title`, prefilled with reasonTitle |
| `modify-admin` | `deferEdit` | `deferEdit`, then `step.hook.editOriginal(modify-admin-role)` |
| `back` | `deferEdit` | `deferEdit`, then re-renders the main panel through `step.hook` |
| `modify-btn-color-submit` | `deferEdit` | `btnStyle = ButtonStyle.fromKey(color_index.toInt())` (1=PRIMARY, 2=SECONDARY, 3=SUCCESS, 4=DANGER), `deferEdit`, re-render the main panel |
| `confirm-create` | `deferEdit` | §3.5. The button interaction is **never acknowledged** |
| anything else | n/a | No ack, so the interaction fails |

**Sub-screens** (`res:lang/*/message/`):
- `modify-category.yaml`: preview embed, preview button, then a **ChannelSelect** with custom_id `ticket@a:create;b:modify-category`, placeholder `未設定則為預設` / `Empty here to by default`, min 1, max 1, channel types `[CATEGORY]`. Last row: `返回`/`Back` (SECONDARY, `ticket@a:create;b:back`).
- `modify-admin-role.yaml`: preview embed, preview button, then a **RoleSelect** with custom_id `ticket@a:create;b:modify-admin`, the same placeholder, min 1 (default), max 25. Then `返回`.
- `modify-btn-color.yaml`: preview embed, preview button, then a row with `藍色` PRIMARY `…;b:modify-btn-color-submit;c:1`, `灰色` SECONDARY `c:2`, `綠色` SUCCESS `c:3`, `紅色` DANGER `c:4` (en-US `BLUE`/`GRAY`/`GREEN`/`RED`). Then `返回`.

**Entity selects** (StepManager.kt:253-276): with no session, `deferEdit`. Otherwise:
- `modify-admin`: `adminIds = selected role ids` (replaces the list). A selection can never be cleared back to empty because min is 1.
- `modify-category`: `categoryId = values[0]`. If the id is not 0 and is missing from the cache, the bot replies (ephemeral) `Cannot find a category with the id {id}!` and stops. Once set, it cannot be reset to 0 (default).
- Any other `sub_action`: no change.
- After the change: `deferEdit`, then render the main panel through `step.hook`.

**Wizard modals** (StepManager.kt:280-325): with no session, `deferEdit`. Otherwise, by `sub_action`:
- `modify-author`: inputs `author` and `image`. `setAuthor(author, image)`: if author is `null`, both are cleared (unreachable because Discord submits `""`). Otherwise `author = value`, `authorIconUrl = value`; either may be `""`.
- `modify-content`: inputs `title` and `desc`, set as given (may be `""`).
- `modify-reason`: input `reason` sets `reasonTitle`. Empty values are ignored (StepData.kt:77-80).
- `modify-embed-color`: input `color` parsed as `Integer.parseInt(value.substring(1), 16)`. `"#00FFFF"` works. `"0x00FFFF"`, the format the placeholder suggests, throws `NumberFormatException` before any ack, so the modal shows a Discord error (bug B5). `"FFFFFF"` silently becomes `0x0FFFFF`. `"#FFF"` is not expanded and becomes `0x000FFF`.
- `modify-btn-text`: inputs `btn-text` and `btn-emoji`.
  - If **both mappings are null**, the bot replies (ephemeral) `Either ButtonText or ButtonEmoji must be provided!`. This is practically unreachable because Discord sends `""` for empty inputs.
  - Otherwise `btnText = text` (may be `""`) and `btnEmoji = Emoji.fromUnicode(s)` if non-empty, else `null`. Only reachable with the en-US modal (bug B2).
- Other sub_actions, including `modify-btn-content` and `prev`: no change.
- After the change: `deferEdit`, then re-render through `step.hook`.

**Render failures.** These are thrown inside the `flatMap` after the ack, so they are only logged and the UI is unchanged; the user recovers by entering valid values (JDA 6.4.1 checks confirmed in bytecode):
- title `""` → `EmbedBuilder.setTitle`: `Title may not be empty`;
- author icon URL not matching `(?i)\s*(https?|attachment)://\S+\s*`, including `""` → `URL must be a valid http(s) or attachment url.`;
- button label `""` with no emoji → `Action buttons must have either an emoji or label`;
- `Emoji.fromUnicode("<:custom:123>")` builds an invalid unicode emoji, which Discord rejects (400).

### 3.4 Preview and defaults (StepData.kt:145-196)
- Default `StepData`:
  - `reasonTitle = "有任何可以幫助的問題嗎~"`, `adminIds = []`, `categoryId = 0`
  - `author = "Ticket 服務"`, `authorIconUrl = "https://img.lovepik.com/free-png/20211116/lovepik-customer-service-personnel-icon-png-image_400960955_wh1200.png"`
  - `title = "🛠 聯絡我們"`, `description = "✨ 點擊下方 **[按鈕]**，並提供所遭遇的問題，我們盡快給予答覆！ ✨"`, `color = 0x00FFFF`
  - `btnText = "聯絡我們"`, `btnEmoji = ✉ (U+2709)`, `btnStyle = SUCCESS`
- Preview embed:
  - create mode: `EmbedBuilder().setAuthor(author, null, iconUrl).setTitle(title).setDescription(description).setColor(color)`;
  - add mode: `target.embeds[0]`.
- Preview button: `Button.of(btnStyle ?: SUCCESS, "ticket@b:prev", btnText, btnEmoji)`.

### 3.5 Confirm (`confirm-create`) (StepManager.kt:219-232, StepData.kt:106-142)
1. `step.hook.deleteOriginal()` deletes the ephemeral setup panel. This happens before anything else, so every later failure is silent.
2. **Create mode:** send `confirm-create` (`res:…/message/confirm-create.yaml`: embed `tt@embed` plus one row containing `tt@btn`) to `event.channel`, the channel where the button was clicked. The panel button is `Button.of(btnStyle ?: SUCCESS, "ticket@a:press;f:0", btnText, btnEmoji)`.
3. **Add mode:** take the snapshot's first ACTION_ROW; if there is none, it throws `IllegalStateException("Cannot find action row in the target message.")` synchronously. The new button gets custom_id `ticket@a:press;f:{N}`, where N is the current component count of that row. The bot then edits the target message:
   - `embeds := [snapshot.embeds[0]]`: other embeds are dropped.
   - `components := [ActionRow(existing row-1 components + new button)]`: **every other row is dropped**.
   - Content is not touched.
   - The edit fails with 403 if the bot does not own the message (silent).
   - The source has a `TODO` here: "currently, we only support modifying the message components" (StepData.kt:124-125).
4. On success (`.map{}`): `data[guildId][resultMessageId]` is created as `[step.json]` or has `step.json` appended, then `save()`. The **same `DataContainer` instance** stays referenced by the Step.
5. The session is not removed.

### 3.6 Runtime actions on panels and tickets (`Ticket.kt`)
Dispatch: `Event.onButtonInteraction` requires the custom_id to start with `ticket@` (Event.kt:67-71). Then `componentIdManager.parse` runs and the handler switches on `action` (Ticket.kt:109-234). Ticket.kt:110 re-runs the prefix check and ignores the result (dead code).

**`press`**, the panel button (Ticket.kt:121-146):
- Lookup: `data[guildId][msg_id ?: clickedMessageId][btn_index]` (Ticket.kt:839-852). The panel buttons have no `msg_id`, so the clicked message id is used.
- Missing → ephemeral `錯誤 (找不到 Ticket 設定資料，可能已被刪除)`.
- Found → respond with modal `press-ticket`:
  - custom_id `ticket@a:submit;e:{clickedMessageId};f:{btn_index}`;
  - title: zh-TW template `Create Ticket`, en-US template `創建客服單` (**swapped**, bug B13);
  - one PARAGRAPH input `reason`, label = `reasonTitle` (`%tt@reason%`), required, no min/max (Discord default max 4000).
- No role restriction, cooldown, or "one open ticket per user" check.

**Modal submit `action=submit`** (Ticket.kt:248-310):
1. `deferReply(ephemeral=true)`.
2. `data[guild][msg_id]!![btn_index.toInt()]` has no null-safety. Missing data throws and leaves the reply stuck "thinking" (bug B4).
3. Category:
   - `categoryId == 0` → `event.guildChannel.asTextChannel().parentCategory`, i.e. the category of the panel's channel. Throws if the panel is not in a TextChannel.
   - Otherwise → `guild.getCategoryById(categoryId)`.
4. Category `null` → `event.reply("錯誤 (無法取得目錄)")`. The interaction was already deferred, so JDA hands an `IllegalStateException` to the failure logger and the user stays "thinking" (bug B3).
5. `category.createTextChannel(user.name)`, named after the submitter's **username**. JDA first copies the category's permission overrides (`CategoryImpl.trySync`, when the bot can sync), then sets per-holder overrides, replacing any copied override for the same holder:
   - `@everyone`: allow 0, deny VIEW_CHANNEL;
   - submitter (member override): allow VIEW_CHANNEL;
   - each admin role: allow VIEW_CHANNEL.

   No override is added for the bot itself (bug/requirement B11).
6. When the channel exists:
   - Hook follow-up `請到此頻道 <#{newChannelId}> 並等待人員回覆繼續!`, which replaces the ephemeral "thinking" message.
   - In the new channel, content = for each admin role `"<@&{roleId}> "`, then `"\n\n"`, then reason. Components = the **unlocked control row** (below), with `user_id` = submitter and `msg_id`/`btn_index` taken from the modal id.
   - Content longer than 2000 characters makes JDA throw before sending, leaving the channel with no opener and no controls (bug B10).
   - A channel creation failure gives no user feedback (stuck "thinking").
   - JDA's default allowed mentions are **all types** (`AllowedMentionsData.defaultParse = EnumSet.allOf(MentionType)`, verified). Role pings therefore fire, and a user-typed `@everyone` in the reason fires if the bot has Mention Everyone (security concern S1).

**Control row** (Ticket.kt:784-832). `d` = submitter id in lowercase hex.

| State | Button 1 | Button 2 | Button 3 |
|---|---|---|---|
| unlocked | `🔒 關閉` SECONDARY `ticket@a:lock;d:{hex};e:{msgId};f:{idx}` | `💾 儲存對話` PRIMARY `ticket@a:save;d:…;e:…;f:…` | `🗑 刪除` DANGER `ticket@a:delete;d:…;e:…;f:…` |
| locked | `🔓 開啟` SUCCESS `ticket@a:unlock;d:…;e:…;f:…` | same | same |

(🗑 is U+1F5D1 without VS16.)

**`lock` / `unlock`** (Ticket.kt:148-179):
- **No permission check**: anyone who can see the channel can press them, including the opener, who can lock themselves out.
- Steps: `guild.retrieveMemberById(user_id)` (REST if uncached) → `channel.upsertPermissionOverride(member).deny(VIEW_CHANNEL)` (or `.grant`; other bits are preserved) → `event.editComponents(row(locked=true|false))`. The edit is the interaction ack (UPDATE_MESSAGE).
- The ack happens only after up to two REST calls (member fetch if uncached, then the override upsert), so the 3-second deadline is at risk. Any failure, such as the member having left or missing permissions, means no ack and the interaction fails.

**`delete`** (Ticket.kt:181-196):
- `member == null` → `deferEdit`.
- Data missing → ephemeral not-found message.
- Admin, meaning the member has any role in `adminIds` **or** guild ADMINISTRATOR (Ticket.kt:834-837) → `deferEdit`, then delete the channel. No confirmation and no transcript.
- Non-admin → `deferEdit` only (silent no-op).

**`save`** (Ticket.kt:198-232):
- `member == null` → `deferEdit`.
- Data missing → not-found message.
- Non-admin → ephemeral `僅管理員可使用此功能`.
- Admin → ephemeral reply `請選擇要儲存對話的文字頻道` with a **ChannelSelect**: custom_id `ticket@a:save;b:select-channel;d:{hex};e:{msgId};f:{idx}`, TEXT channels only, required range 1..1, placeholder `請選擇要儲存對話的文字頻道`.

**Save select → transcript** (Ticket.kt:236-242, 312-376):
- `sub_action != "select-channel"` → `deferEdit`.
- Checks, in order. Each failure sends an ephemeral reply and stops:
  1. member null → `錯誤 (無法取得成員資訊)`
  2. data missing → `錯誤 (找不到 Ticket 設定資料，可能已被刪除)`
  3. non-admin → `僅管理員可使用此功能`
  4. current channel not a TextChannel → `錯誤 (目前頻道不是文字頻道)`
  5. no TextChannel in the resolved selection → `請選擇一個文字頻道`
  6. bot lacks VIEW_CHANNEL + MESSAGE_HISTORY in the source channel → `機器人缺少讀取 Ticket 訊息歷史的權限`
  7. bot lacks any of VIEW_CHANNEL, MESSAGE_SEND, MESSAGE_SEND_IN_THREADS, CREATE_PUBLIC_THREADS, MANAGE_WEBHOOKS in the target channel → `機器人缺少目標頻道權限 (VIEW_CHANNEL / MESSAGE_SEND / MESSAGE_SEND_IN_THREADS / CREATE_PUBLIC_THREADS / MANAGE_WEBHOOKS)`
- Then `deferReply(ephemeral=true)`, a **new** ephemeral message (the select message stays usable, so repeated archives are possible). On success it is edited to `存檔中...` and the transcript engine (§3.7) starts.
- Final edit: `存檔完成，已建立 Thread：<#{threadId}>` or `存檔失敗：{readableError}`.
- The ticket channel is neither locked nor deleted afterwards.

### 3.7 Transcript / archive engine (Ticket.kt:378-878): exact semantics
Constants: `archivePageSize = 100`, `threadNameMaxLength = 100` (Ticket.kt:57-60).

1. **Thread.** `targetChannel.createThreadChannel(name)` creates a **public** thread with no starter message. The bot sets no auto-archive duration.
   - `name = trimByGrapheme(sourceChannel.name, 100 - len(suffix)) + suffix`, with `suffix = "-" + now(systemDefaultZone).format("yyyy-MM-dd_HH:mm:ss")` (20 chars, so 80 are left for the name).
   - Trimming uses `BreakIterator.getCharacterInstance(Locale.ROOT)` and keeps the longest prefix whose grapheme boundary is ≤ max. Lengths are **UTF-16 code units** (Java `String.length`) (Ticket.kt:756-782).
   - On failure: `onError`. There is no webhook yet.
2. **Webhook** in the target channel: `"ticket-save-content-" + base36(System.currentTimeMillis()) + "-" + base36(System.nanoTime() & 0xFFFFF)` (Ticket.kt:709-717). On failure: `onError`, and the thread is **left behind empty**.
3. **History.** `source.iterableHistory.order(FORWARD).cache(false)`, then `takeAsync(100)` repeatedly. Messages come **oldest → newest**. JDA continues after the last iterated element because `updateIndex` sets `last/lastKey` when cache is false (verified). An empty page means done.
4. For each message M, in order (`forwardMessagesWithWebhook`, Ticket.kt:453-516):
   - M is "handled" if it is forwardable (`contentRaw` non-empty **or** at least one attachment) or, at top level, if `M.startedThread` is non-null and that thread id has not been processed. Others are skipped silently: embed-only, sticker-only, poll, and empty system messages.
   - **Forwardable** M → webhook message into the archive thread (`setThread`):
     - content = `M.contentRaw` (only if non-empty);
     - files = every attachment re-downloaded through the Discord media proxy and re-uploaded with its original `fileName`;
     - username = `M.member?.effectiveName ?: M.author.name`;
     - avatar = `M.member?.effectiveAvatarUrl ?: M.author.effectiveAvatarUrl`.

     `M.member` is cache-dependent, so uncached authors appear under their **username** **(unverified, but REST history carries no member object)**. Not preserved: embeds, stickers, reactions, components, reply references, original timestamps, edits, pins. Allowed mentions default to all, so content mentions may re-ping **(unverified for webhooks)**.
   - Then, if M started an unprocessed thread T (top level only), T is added to `processedThreadIds` and **flattened**:
     1. The webhook sends a start marker (no username/avatar override, so it posts under the webhook's own name):
        ```
        【Thread 開始】
        作者: {owner}
        名稱: {T.name}
        開始時間: {T.timeCreated as yyyy-MM-dd HH:mm:ss in system zone}
        ```
     2. T's history is paged FORWARD in pages of 100, and every forwardable message is forwarded (nested threads are not flattened). `lastMessageTime` = `timeCreated` of the last message of the last non-empty page, whether or not that message was forwarded.
     3. End marker:
        ```
        【Thread 結束】
        作者: {owner}
        名稱: {T.name}
        最後一則訊息時間: {yyyy-MM-dd HH:mm:ss | 無訊息}
        ```
     4. On any failure in step 1 or step 2, an error marker is sent:
        ```
        【Thread 攤平失敗】
        作者: {owner}
        名稱: {T.name}
        錯誤: {readableError}
        ```
        It is followed by the end marker with `無訊息`. If the error marker itself fails, a WARN is logged and the end marker is still sent. **Thread failures are non-fatal**, but if the end marker fails the whole archive aborts.
     5. `{owner}` = `T.owner?.effectiveName` (cached member) or else `T.ownerId`.
   - Threads created without a starter message (a `THREAD_CREATED` system message) and private threads are most likely **not** flattened; only the system message's content, if any, is forwarded **(unverified)**.
5. **Completion:** delete the webhook (errors ignored), then `onSuccess(thread)`.
6. **Failure** (thread creation, webhook creation, history page, forward send, end marker): delete the webhook if it exists (errors ignored), then `存檔失敗：{e}`. The thread keeps whatever was already posted.
   - `readableError`: unwrap nested `CompletionException`, take the message, replace `\n` with a space, keep 200 characters; with no message, use the exception's simple class name (Ticket.kt:860-878).
7. Everything is sequential: exactly one webhook request is in flight at a time, so order is preserved. There is no cancellation, timeout, or progress report.
   - If the run exceeds 15 minutes, the final `hook.editOriginal` fails silently (token expiry).
   - An exception thrown inside a `whenComplete` lambda, for example `MessageCreateBuilder.setContent` rejecting a Nitro 4000-character message (webhook limit 2000), is swallowed. The archive then **hangs silently**: no final message, webhook not deleted (bug B12).

---

## 4. Components and custom_id formats

`ComponentIdManager(prefix="ticket@")` (Ticket.kt:69-79; Core: util/ComponentIdManager.kt):
- Format: `{prefix}{k}:{v};{k}:{v}…`. Keys are single letters assigned in `idKeys` order.
- Encoding order follows the order of the map passed to `build`. **Parsing ignores order.**
- Separators are `;` and `:` with no escaping.
- Maximum length 100 (`Button.ID_MAX_LENGTH`), checked after value substitution in `build`. For modals the check runs before the second substitution pass.

| key | short | type | encoding |
|---|---|---|---|
| action | `a` | STRING | raw |
| sub_action | `b` | STRING | raw |
| color_index | `c` | STRING | raw (`"1"`..`"4"`) |
| user_id | `d` | LONG_HEX | `Long.toString(16)`, lowercase, no padding |
| msg_id | `e` | STRING | decimal snowflake |
| btn_index | `f` | STRING | decimal index |

| Component | custom_id | Who can use | Notes |
|---|---|---|---|
| Wizard buttons | `ticket@a:create;b:{modify-author\|modify-content\|modify-category\|modify-color\|modify-btn-text\|modify-btn-color\|modify-reason\|modify-admin\|confirm-create\|back}` | invoker (ephemeral) | Session expires 15 min after the slash command (B14) |
| Colour buttons | `ticket@a:create;b:modify-btn-color-submit;c:{1-4}` | invoker | |
| Category select | `ticket@a:create;b:modify-category` | invoker | CATEGORY, 1..1 |
| Role select | `ticket@a:create;b:modify-admin` | invoker | 1..25 |
| Preview button | `ticket@b:prev` | none in practice | no `a:` → ignored, no ack (B1) |
| Wizard modals | `ticket@a:create;b:{modify-author\|modify-content\|modify-embed-color\|modify-reason}`; `ticket@a:create;b:modify-btn-text` (en-US) / `ticket@a:create;b:modify-btn-content` (zh-TW, B2); `ticket@a:create;b:prev` (unreachable) | invoker | |
| **Panel button (persistent)** | `ticket@a:press;f:{index}` (`e:{msgId}` honoured if present) | anyone who sees the panel | Data lookup uses the clicked message id |
| **Press modal** | `ticket@a:submit;e:{panelMsgId};f:{index}`, input `reason` | presser | |
| **Ticket controls (persistent)** | `ticket@a:{lock\|unlock\|save\|delete};d:{hexUserId};e:{panelMsgId};f:{index}` | lock/unlock: anyone in the channel; save/delete: admins | |
| **Save select** | `ticket@a:save;b:select-channel;d:{hex};e:{panelMsgId};f:{index}` | admins | TEXT, 1..1, ephemeral |

There are no View timeouts; Discord's limits apply instead. Panel and control-row buttons live on normal messages and **must stay decodable after the port**. IDs from before commit `b4d10e2` (2025-09-28) carried only `f:` (no `a:`) and are already non-functional on `main`.

Modal text inputs: JDA 6 wraps each input in a `Label` component (Core: builtin/messagecreator/modal/builder/ModalBuilder.kt:43-54). `value` is set only when the substituted value is non-blank, `placeholder` only when non-blank, `min_length`/`max_length` only when ≥ 0, `required` defaults to `true`.

| Modal key | title (zh-TW / en-US) | inputs |
|---|---|---|
| `modify-author` | 創建客服單 / Create Ticket | `author` SHORT label 設定作者名稱/Modify author name, value `%tt@author%`, placeholder `Ticket 服務`/`Ticket Service`, max 256, optional · `image` PARAGRAPH label 設定作者圖示/Modify Author Image, value `%tt@author-icon-url%`, placeholder `https://img .... 5_wh1200.png`, max 4000, optional |
| `modify-content` | 創建客服單 / Create Ticket | `title` SHORT 設定標題/Modify title, `%tt@title%`, ph `🛠 聯絡我們`/`🛠 Contact Us`, max 256, optional · `desc` PARAGRAPH 設定內文/Modify description, `%tt@description%`, same placeholder, max 4000, optional |
| `modify-embed-color` | 創建客服單 / Create Ticket | `color` SHORT 設定顏色/Modify color, `%tt@hex-color%`, ph `0x00FFFF`, max 8, required |
| `modify-btn-text` | 創建客服單 / Create Ticket | `btn-text` SHORT 設定按鈕文字/Modify button text, `%tt@btn-text%`, ph `聯絡我們`/`Contact Us`, max 80, optional · `btn-emoji` SHORT 設定按鈕符號/Modify button emoji, `%tt@btn-emoji%`, ph `✉`, optional |
| `modify-reason-title` | 創建客服單 / Create Ticket | `reason` PARAGRAPH 設定原因/Modify reason, `%tt@reason-title%`, ph `有任何可以幫助的問題嗎~`/`Do you have any questions we can help with?`, max 45, required |
| `press-ticket` | **Create Ticket / 創建客服單** (swapped) | `reason` PARAGRAPH, label `%tt@reason%`, required |
| `preview-reason` | `%tt@reason-title%` | `reason` PARAGRAPH 原因/Reason, required |

---

## 5. Events handled

Every handler first returns if `config.enabled` is false (Event.kt:61-88).

| JDA event | Filter | Behavior |
|---|---|---|
| `SlashCommandInteractionEvent` | `name ∈ {create-ticket, add-ticket}` | §3.1, §3.2 |
| `ButtonInteractionEvent` | custom_id starts with `ticket@` | `action`: create→wizard; press, lock, unlock, delete, save; anything else → no ack |
| `EntitySelectInteractionEvent` | starts with `ticket@` | `action`: create→wizard; save→transcript; anything else → nothing |
| `ModalInteractionEvent` | modal id starts with `ticket@` | `action`: create→wizard; submit→ticket creation; anything else → return without ack |
| `GuildLeaveEvent` | none | `jsonGuildManager[guildId].delete()` deletes `plugins/Ticket/data/{guildId}.json`. If the file did not exist, it is created as `{}` and then deleted (StepManager.kt:329-331) |

A malformed custom_id with the `ticket@` prefix makes `parse` throw (`require`/`error`), so the interaction gets no ack.

---

## 6. Configuration

`plugins/Ticket/config.yaml` (default `res:config.yaml`): `enabled: false`.

| Key | Type | Default | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` (also the serializer default when the key is absent) | false: no commands registered, every handler is a no-op, the localizer is not built. Toggled at runtime through reload/dashboard |

kaml is in strict mode, so **unknown keys fail plugin load**. Core does not catch exceptions from `plugin.load()`, so the whole application exits (Core: base/PluginLoader.kt:145-155, Main.kt:21-31). Everything else is hard-coded: Chinese runtime strings, button labels, defaults, page size, and name formats.

---

## 7. Localization and templates

- Locales: `zh-TW` (default for every creator and the localizer) and `en-US`. Files are exported to `plugins/Ticket/lang/` and **loaded from disk**, so operators can edit them.
- `register.yaml`: command and option localizations only. Schema `CmdFileSerializer` (`create_ticket{name,description}`, `add_ticket{name,description,options{message_id{name,description}}}`).
- `message/*.yaml` (MessageCreator **v2** class, but legacy v1 schema: `embeds`, `components` with `!ButtonsComponent` / `!EntitySelectMenu` tags; kaml `strictMode=false`): `create-ticket`, `add-ticket`, `modify-category`, `modify-admin-role`, `modify-btn-color`, `confirm-create`, `confirm-add` (**unused**).
- `modal/*.yaml` (ModalCreator; kaml strict): `modify-author`, `modify-content`, `modify-embed-color`, `modify-btn-text`, `modify-reason-title`, `press-ticket`, `preview-reason`.
- Template selection: `event.userLocale`. A locale without its own directory falls back to zh-TW. If a locale directory **exists but lacks the key**, the call throws instead of falling back (Core: builtin/messagecreator/v2/MessageCreator.kt:130-134; modal/ModalCreator.kt:68-72).
- **Model keys** (non-text objects injected by code): `tt@embed-demo` (MessageEmbed), `tt@btn-demo` (Button), `tt@embed`, `tt@btn`.
- **Placeholders defined by Ticket**, all set through `Placeholder.get(buttonEvent).putAll(…)`:

  | placeholder | template | value |
  |---|---|---|
  | `%tt@msg-id%` | press-ticket uid | clicked message id |
  | `%tt@btn-index%` | press-ticket uid | btn_index |
  | `%tt@reason%` | press-ticket label | reasonTitle |
  | `%tt@reason-title%` | modify-reason-title value, preview-reason title | reasonTitle |
  | `%tt@author%`, `%tt@author-icon-url%` | modify-author | author or `""`, iconUrl or `""` |
  | `%tt@title%`, `%tt@description%` | modify-content | title or `""`, description or `""` |
  | `%tt@hex-color%` | modify-embed-color | `#RRGGBB` (uppercase) |
  | `%tt@btn-text%`, `%tt@btn-emoji%` | modify-btn-text | text or `""`, `emoji.asReactionCode` or `""` |

  Core placeholders that are also available in these templates (none used by the shipped files): `user_id`, `user_mention`, `user_name`, `user_avatar_url`, `member_display_name`, `member_avatar_url`, `member_fixed_name`, `component_id`, `component_label`, `component_style`, `component_url`, `component_emoji`, `component_emoji_name`, `language`, `channel_id`, `channel_name`, `bot_id`, `bot_name`.
- Substitution engine (Core: builtin/placeholder/Substitutor.kt): Apache `StringSubstitutor` with `%` as both prefix and suffix and escape `$`. Unknown keys stay literal, **resolved values are substituted recursively**, and a cycle raises `IllegalStateException`. Modal custom_ids are substituted twice: once by the global substitutor inside `ComponentIdManager.build`, then by the event substitutor (ModalBuilder.kt:22-25).
- Hard-coded, non-localized strings in code are listed in §3.6, §3.7 and §12.

---

## 8. Persistence

- **Storage:** `JsonGuildFileManager<MutableMap<String, MutableList<DataContainer>>>` writes one file per guild: `plugins/Ticket/data/{guildId}.json` (Ticket.kt:62-67). There is no Mongo and no SQLite. Serialization is Moshi with `KotlinJsonAdapterFactory`, compact (one line). Field names are the Kotlin property names.
- **Schema:**
  ```
  { "<panelMessageId:string>": [ DataContainer, ... ] }   // list index == btn_index
  DataContainer = { "reasonTitle": string, "adminIds": [int64,...], "categoryId": int64 }  // 0 = panel channel's category
  ```
  Example:
  ```json
  {"1290000000000000001":[{"reasonTitle":"有任何可以幫助的問題嗎~","adminIds":[1280000000000000002],"categoryId":0},{"reasonTitle":"退款","adminIds":[],"categoryId":1270000000000000003}]}
  ```
- **Lifecycle:**
  - All files load at `Ticket` initialization and are immediately rewritten (`JsonFileManager.init` calls `save()`, Core: json/JsonFileManager.kt:29-39).
  - Reading an unknown guild creates `{}` on disk, even for a read-only press lookup (Core: json/JsonGuildFileManager.kt:21-36).
  - Saved only after confirm.
  - Deleted on GuildLeave.
  - No cleanup when panel messages or ticket channels are deleted, so stale entries accumulate.
  - Open tickets have **no persisted record**. Their state lives entirely in channel overwrites and component ids.
  - Corrupt JSON (malformed or wrong shape) is logged and replaced by `{}` (the default instance). Because `JsonFileManager.init` calls `save()`, the empty map is **written back immediately at load**, so the corrupt file's data is lost (Core: json/JsonFileManager.kt:29-67).
- **Migration/compat:**
  - The port must read these files as-is: string keys; `adminIds` and `categoryId` as JSON integers (int64; Python `int` is exact).
  - It must keep the list-index ↔ `btn_index` correspondence.
  - Existing panels and ticket control rows in live guilds use the custom_id formats in §4.
  - Add-mode index mismatch: if the target message's first row already contains non-Ticket buttons, the new button's `f:` index differs from its list index and the lookup fails (B6).

---

## 9. External dependencies

- Gradle: none beyond `compileOnly(project(":Core"))`. Moshi, kaml, and JDA come through Core's `api` deps (Core/build.gradle.kts:62-71).
- HTTP: Discord API only, plus attachment download from the Discord media proxy (`attachment.proxy.downloadAsFileUpload`) during archives. The default embed author icon is hot-linked from `img.lovepik.com` (third-party). No credentials.
- Plugin dependencies: none, hard or soft. TicketAddons is independent: it reacts to channel names `客服單-*` and `ticket-*`, while Ticket names channels after the user's username.

---

## 10. Discord requirements

- **Intents:** none declared. Core always enables `GUILD_MEMBERS` (privileged), `SCHEDULED_EVENTS`, and `GUILD_EXPRESSIONS` (Core: base/BotLoader.kt:68-72); JDA always includes GUILDS. **The transcript needs the Message Content privileged intent enabled for the application.** Without it, REST history returns empty `content` and attachments for messages from other users, so those messages are skipped. This requirement is undeclared.
- **Cache:** channels and categories come from JDA's cache. The member cache affects archive display names and thread owner names. No member cache policy is requested.
- **Bot permissions:**
  - Panel: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS in the panel channel; add mode can only edit the bot's own messages.
  - Tickets: MANAGE_CHANNELS and MANAGE_ROLES (Manage Permissions) on the category; MENTION_EVERYONE to ping non-mentionable admin roles.
  - **The bot must have ADMINISTRATOR or hold one of the admin roles.** The new channel denies VIEW_CHANNEL to @everyone and adds no override for the bot. Without one of the two, sending the opener fails and lock/unlock overrides may also fail (B11).
  - Archive: source VIEW_CHANNEL + READ_MESSAGE_HISTORY; target VIEW_CHANNEL, SEND_MESSAGES, SEND_MESSAGES_IN_THREADS, CREATE_PUBLIC_THREADS, MANAGE_WEBHOOKS (checked explicitly).
  - Delete: MANAGE_CHANNELS.
- **Rate-limit-sensitive operations:**
  - The archive makes one webhook execute per message, sequentially, plus history pages.
  - Channel creation per ticket.
  - Override upserts.
  - Discord limits webhooks to 15 per channel: when the target channel already has 15, creation fails and leaves an empty thread.

---

## 11. Concurrency

- JDA's default event manager dispatches listeners synchronously on the gateway thread. RestAction callbacks (`queue`, `flatMap`, `map`, `whenComplete`) run on JDA callback threads.
- `StepManager.steps` is a plain `HashMap`. The event thread writes it (`onCreateTicket`) and so does a callback thread (`onAddTicket`'s `flatMap`). The race is benign but real.
- `JsonFileManager.data` (a LinkedHashMap from Moshi) is mutated in the confirm `.map{}` on a callback thread and read on the event thread. Only `save()` is synchronized; `JsonGuildFileManager.mapper` is unsynchronized.
- `Step.json` stays referenced after persistence. Later wizard edits through the same session mutate the stored entry in memory and persist on the next save. Confirming twice stores the same object under two panels.
- Add mode is a lost update: two concurrent `/add-ticket` sessions on one panel edit from stale snapshots, and the later edit overwrites the earlier button while the data list still grows.
- Archive: independent concurrent runs are allowed (unique webhook names). There is no lock per ticket and no de-duplication. Exceptions inside `whenComplete` are swallowed, which causes a silent hang.
- Lock/unlock acknowledge only after up to two REST calls (member fetch if uncached, override upsert), against the 3-second deadline.
- There is no reentrancy guard on any handler.

---

## 12. Bugs, quirks, dead code, hard-coded values

**Probable bugs to fix** (keep the user-visible intent, fix the mechanism):
- **B1** The preview button id `ticket@b:prev` has no `action` (StepData.kt:156-162). `Ticket.onButtonInteraction` matches nothing and never acks, so clicking the preview fails. `previewReason` and modal `preview-reason` are therefore unreachable (StepManager.kt:57, 79-91).
- **B2** zh-TW `modal/modify-btn-text.yaml` uses `sub_action: "modify-btn-content"` (`res:lang/zh-TW/modal/modify-btn-text.yaml:3`), but the handler expects `modify-btn-text` (StepManager.kt:303). For zh-TW users and every locale that falls back to zh-TW, **button text and emoji cannot be changed**; the submit only re-renders.
- **B3** Missing category → `event.reply` after `deferReply` (Ticket.kt:257, 275-277). The message is dropped and the user stays "thinking".
- **B4** Submit path uses `!!` lookups (Ticket.kt:260-264) where the button paths are null-safe.
- **B5** Colour parsing `substring(1)` (StepManager.kt:298-300) contradicts the placeholder `0x00FFFF`.
- **B6** Add-mode index = current row size (StepData.kt:131-134). It diverges from the data-list index when the target row has non-Ticket buttons or the data entry is missing.
- **B7** `asLong` on a STRING option (StepManager.kt:34): non-numeric input leaves the reply stuck.
- **B8** `onErrorFlatMap` falls through to `flatMap` (StepManager.kt:36-50): a broken Step is stored and an exception logged.
- **B9** `message.embeds[0]` (StepData.kt:153): a target without an embed leaves the reply stuck "thinking".
- **B10** Opener content (role mentions + "\n\n" + reason up to 4000) can exceed 2000 characters (Ticket.kt:280-308). The channel is created without controls.
- **B11** No override is added for the bot on the new channel (Ticket.kt:281-297). This silently requires the bot to be ADMINISTRATOR or an admin role member.
- **B12** Exceptions thrown inside `whenComplete` or callback lambdas during an archive (e.g. content > 2000) hang the archive silently: no `onError`, the webhook leaks (Ticket.kt:421-450, 603-634).
- **B13** `press-ticket` titles swapped between locales (zh-TW `Create Ticket`, en-US `創建客服單`).
- **B14** The wizard edits through the slash command hook, so the session dies after 15 minutes. `modify-btn-color` alone uses the fresh component hook (StepManager.kt:173).
- **B15** `confirm-create` never acknowledges the button and deletes the setup message first. Any failure afterwards (missing permissions, editing a foreign message, no action row) is invisible to the admin (StepData.kt:107, StepManager.kt:219-232).
- **B16** The `add-ticket` "full" check is `== 5` instead of `>= 5`. A first row holding a select menu passes the check and then fails at edit time (StepManager.kt:43).
- **B17** Add mode drops every row except the first and every embed except the first (StepData.kt:136-139).
- **S1 (security)** User-supplied reason and archive content are sent with JDA's default allowed mentions (all types), so `@everyone` pings are possible from user input and the archive may re-ping.

**Behavior to preserve (or decide deliberately):**
- lock/unlock have no permission check; non-admin delete is a silent no-op; the select-based admin check covers roles in `adminIds` plus ADMINISTRATOR.
- Channels are named after the username; duplicates are allowed; there is no limit per user.
- Defaults (`StepData`), Chinese strings, emoji, labels, styles, custom_id formats, archive marker formats, and the thread and webhook name formats.
- Sequential, ordered archive with forward-only content and attachments; thread flattening; non-fatal thread failures.
- The guild data file is deleted on leave.

**Dead code / TODO / misc:**
- `confirm-add.yaml` unused.
- `GlobalUtil.checkComponentIdPrefix` result ignored (Ticket.kt:110).
- `TODO` at StepData.kt:124-125.
- `Event.componentPrefix` comes from info.yaml (`ticket@`).
- Hard-coded values: archive page size 100, thread name max 100, time formats `yyyy-MM-dd_HH:mm:ss` and `yyyy-MM-dd HH:mm:ss` in the **host system time zone**, error text truncated to 200, default lovepik icon URL.
- README advertises `/ticket create`.

---

## 13. Testability

Pure logic that can be extracted and unit-tested in Python:
- Custom-id codec (Core `ComponentIdManager` port): key-letter assignment, LONG_HEX, order-independent parse, 100-character limit, error cases. Golden strings come from §4.
- `get_ticket_data(store, guild_id, id_fields, fallback_msg_id)`: null-safety and index parsing.
- `is_ticket_admin(member_role_ids, is_administrator, admin_ids)`.
- `build_control_row(locked, user_id, msg_id, idx)` → list of (style, custom_id, label, emoji).
- `opener_content(admin_ids, reason)` → `"<@&a> <@&b> \n\nreason"`; overwrite spec builder (everyone/member/roles).
- Archive helpers: `archive_thread_name(name, now)` with UTF-16/grapheme trimming, `webhook_name(ms, ns)`, marker builders (start/end/error, timezone injectable), `readable_error`, `should_forward`, `should_handle`, and the traversal algorithm. The algorithm is best tested with fake channel/message/thread objects and a recording webhook, checking order, skips, flattening, failure-marker paths, and abort semantics.
- Wizard state machine: `StepData` defaults, `set_author`, `set_reason` (ignores empty), colour parse (`#RRGGBB`), `#%06X` prefill, button-style index mapping, add-mode "row full" rule, add-mode index computation, the confirm persistence rule (append or create).
- JSON store: load existing files, append, save format, delete on guild leave.
- Template rendering: YAML → embed/components/modal dicts with placeholder substitution, including the recursive and escape semantics.

Needs Discord test doubles: interaction response tracking (defer vs. reply vs. modal vs. update; ephemeral flags; follow-up after defer), channel creation with overwrites (including category sync), member fetch, permission override upsert, webhook create/send/delete with thread target, history pagination, thread creation, permission checks (`permissions_for`), guild/category cache.

---

## 14. Porting assessment

**Difficulty: High.** The reasons:
1. A multi-screen ephemeral wizard with per-user in-memory sessions and many sub-flows.
2. **Persistent custom-id compatibility** with live panels and ticket channels.
3. The transcript engine (webhooks, threads, paginated history, thread flattening, failure markers, rate limits, 15-minute token).
4. Modals with prefilled values, entity selects, Label-wrapped inputs.
5. File-based YAML templates with the Core placeholder semantics.
6. Many latent bugs that need explicit "preserve vs. fix" decisions.

**Suggested discord.py mapping (2.6+, Python 3.14):**
- Cog with `app_commands.command` for `create-ticket` and `add-ticket` (`@app_commands.default_permissions(administrator=True)`, guild-only). Localizations come from YAML through an `app_commands.Translator` (locale_str). Sync per guild, as Core does, including on `on_guild_join`.
- Emulate Core auto-defer: `await interaction.response.defer(ephemeral=True, thinking=True)` before command handlers when the flag is on. Answer with `interaction.edit_original_response` / `followup`.
- Routing: one `on_interaction` listener (or `DynamicItem` with template `ticket@(?P<body>.+)` for Button, ChannelSelect, and RoleSelect) that decodes with a ported ComponentIdManager, so the exact custom_ids work across restarts. Avoid `View` objects for persistent rows, or register them as `DynamicItem`s.
- Wizard: `dict[user_id, Step]`. Edit screens with `interaction.response.edit_message(...)` on each component interaction rather than the original 15-minute token, which also fixes B14. Use `discord.ui.Modal` with an explicit `custom_id` and `TextInput(default=…, required=…, max_length=…)`, `discord.ui.ChannelSelect(channel_types=[ChannelType.category])`, `RoleSelect(min_values=1, max_values=25)`.
- Ticket channel: build the overwrites as `{**category.overwrites, guild.default_role: deny view, member: allow view, *roles: allow view}`. Passing `overwrites=` to `create_text_channel` disables syncing, and this merge reproduces JDA's copy-then-replace. Consider adding the bot's own member to fix B11.
- Lock/unlock: `ow = channel.overwrites_for(member)`, set `ow.view_channel = False/True`, then `await channel.set_permissions(member, overwrite=ow)`, which preserves other bits like JDA's upsert. Then `interaction.response.edit_message(view=…)`.
- Archive: `create_thread(name=…, type=ChannelType.public_thread)`, `create_webhook(name=…)`, `async for m in channel.history(limit=None, oldest_first=True)`, `webhook.send(content=…, files=[await a.to_file() for a in m.attachments], username=…, avatar_url=…, thread=thread, wait=True, allowed_mentions=…)`. Started threads: `m.thread` or `guild.get_thread`/`fetch_channel`. Run it as an `asyncio` task with try/except around every step so B12 cannot recur. Rate limits are handled by discord.py.
- Storage: keep `plugins/Ticket/data/{guildId}.json` with the same schema. Write atomically and add a lock per guild.

**Risks:**
- Custom-id and template parity.
- The Message Content intent requirement.
- Allowed mentions (S1).
- discord.py's `create_text_channel` overwrite semantics.
- Webhook username restrictions (no `discord`/`clyde`, at most 80 characters) can abort the archive.
- Webhook upload size limits (per guild boost tier) abort the archive.
- UTF-16 vs. code-point length in thread-name trimming.
- Locale fallback quirks.
- The ephemeral "first follow-up replaces thinking" behavior.
