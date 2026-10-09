# Giveaway: porting inventory (branch `main`)

Paths below are relative to `/Users/xinshou/IdeaProjects/XsDiscordBotKt/Plugins/Giveaway/src/main/` unless they start with `Core/`.
Abbreviations: `GW.kt` = `kotlin/giveaway/Giveaway.kt`, `SM.kt` = `kotlin/giveaway/create/StepManager.kt`, `SD.kt` = `kotlin/giveaway/create/StepData.kt`, `GD.kt` = `kotlin/giveaway/data/GiveawayData.kt`, `EV.kt` = `kotlin/giveaway/Event.kt`.

How the behavioural claims were checked:
- **Date parsing and URL validation:** run with JDK 25 `DateTimeFormatter`/`java.net.URI` in a scratch harness.
- **JSON formats:** produced with Moshi 1.12 + `KotlinJsonAdapterFactory` from the verbatim data classes. The project uses 1.15.2, which has the same layout.
- **JDA behaviour** (`DiscordLocale.from`, `MessageEditBuilder.fromCreateData`, embed field limits, default allowed mentions, client-side permission checks): checked against JDA 6.4.1 bytecode.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/Giveaway` |
| Kotlin files / LOC | 8 files, 1426 lines (1226 non-blank): `Giveaway.kt` 633, `create/StepManager.kt` 380, `create/StepData.kt` 148, `Event.kt` 118, `data/GiveawayData.kt` 102, `command/Register.kt` 24, `command/CmdFileSerializer.kt` 11, `config/ConfigSerializer.kt` 10 |
| Resources | 30 files: `config.yaml`, `info.yaml`, and per locale (`en-US`, `zh-TW`) `register.yaml`, 7 `message/*.yaml`, 6 `modal/*.yaml` |
| Purpose | An admin-only, step-by-step giveaway builder: an ephemeral preview embed with 10 buttons and 6 modals. It posts a public giveaway message with **Join/Leave**, **Draw** and **Reroll** buttons. Supports multiple prizes, each with 1-50 winners, plus a cross-prize duplicate-winner policy. A periodic scheduler auto-draws. Data is persisted as JSON per guild |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (EV.kt:19) |
| Listener flag | `true` |
| Logic | `internal object Giveaway` (GW.kt:44), `internal object StepManager` (SM.kt:16), `internal class Step` (SD.kt:16), data classes plus the pure `drawPrizeWinners` (GD.kt) |
| Build | `id("xs-plugin")` only. `version.patch=0` → `3.4.0-SNAPSHOT` |

`info.yaml` after build-time expansion:
```yaml
author: xinshoutw
name: Giveaway
coreApi: "3.4"
version: 3.4.0-SNAPSHOT
main: "tw.xinshou.discord.plugin.giveaway.Event"
component_prefix: "giveaway@"
```
No intents, cache flags, member-cache policies, plugin dependencies or jar dependencies.

## 2. Lifecycle

**`load()`** (EV.kt:27-46):
1. `super.load()` exports `lang/` if missing and reads `config.yaml` (strict kaml).
2. `Giveaway.stopAutoDrawScheduler()` (EV.kt:29). This is the **first touch of the `Giveaway` object**, so it initialises the object **even when the plugin is disabled** (GW.kt:49-75):
   - `JsonGuildFileManager(data/)` loads and re-saves every `plugins/Giveaway/data/*.json`. A non-`Long` file stem throws `NumberFormatException`, and that aborts the bot.
   - It builds the `ComponentIdManager`.
   - It parses every `lang/*/message/*.yaml` (v2 `MessageCreator`, default zh-TW) and every `lang/*/modal/*.yaml` (`ModalCreator`).
3. If `!enabled`: warn `"Giveaway is disabled."` and return.
4. `defaultLocale = resolveLocale(config.defaultLocale)`.
   - The lookup is `DiscordLocale.from(tag)`, an exact and case-sensitive tag match that **never throws**.
   - An unknown tag therefore yields `DiscordLocale.UNKNOWN`, **not** the zh-TW fallback written in `runCatching` (EV.kt:22-25).
5. `StringLocalizer(defaultLocale)` for `register.yaml`. It throws if `lang/<default>/register.yaml` is missing, which is guaranteed for `UNKNOWN`. That aborts the bot.
6. `Giveaway.reload(defaultLocale)` rebuilds the message and modal creators with the configured fallback locale.
7. `Giveaway.startAutoDrawScheduler(config.autoDrawIntervalSeconds)`.

**`reload()`** (EV.kt:48-67): the same, minus the first-touch effects.
- The data files are **not** re-read: `jsonGuildManager` is a `val` created once per class-loader lifetime.
- Builder sessions survive a plugin reload. A full Core reload, which recreates the class loaders, wipes everything in memory.

**`unload()`** (EV.kt:114-117): stops the scheduler.

**Background job** (GW.kt:93-119):
- `Executors.newSingleThreadScheduledExecutor` with one daemon thread named `giveaway-auto-draw`.
- `scheduleAtFixedRate(task, initialDelay = 5 s, period = clamp(autoDrawIntervalSeconds, 5, 3600) s)`.
- The task is `runCatching { processAutoDraw() }`. Failures are logged and the schedule continues. Stopping calls `shutdownNow()`.

**In-memory state:**
- `Giveaway`: `jsonGuildManager` (all guild files as mutable objects), `defaultLocale`, `messageCreator`, `modalCreator`, `autoDrawScheduler`.
- `StepManager.steps: HashMap<SessionKey(userId, guildId), Step(hook = slash-command InteractionHook, guildId, data = GiveawayConfig draft)>` (SM.kt:17-24).

## 3. Slash command

### `/create-giveaway` (guild command; `command/Register.kt:19-24`)

| Property | Value |
|---|---|
| Base name / description | `create-giveaway` / `Create a giveaway with step-by-step setup` |
| Localizations | en-US `create-giveaway` / `Create giveaway with step-by-step builder`; zh-TW `建立抽獎` / `使用步驟表單建立抽獎`. Source: `lang/<loc>/register.yaml`, top key `create_giveaway` (`@SerialName`), flattened key `createGiveaway.*` |
| Options | none |
| default_member_permissions | `ADMINISTRATOR` |
| Guild-only / NSFW | guild command / false |
| Registered when | enabled **and** the localizer is initialised (EV.kt:69-77) |

Routing: enabled and `event.name ∈ {"create-giveaway"}` (EV.kt:79-83), then `StepManager.onSlashCommandInteraction` (SM.kt:26-42).

Behaviour:
1. Core has already called `deferReply(true)`, so the response is **ephemeral**.
2. If `guild == null`: `editOriginal("This command can only be used in a server.")`. Unreachable for a guild command.
3. Create `Step(hook = event.hook, guildId)` and store it under `(userId, guildId)`. This **replaces** any existing session for that user in that guild, and the old draft is lost.
4. `hook.editOriginal(create-giveaway template)`: the preview embed plus 4 rows of builder buttons, in the invoker's locale (§4, §7).

No server-side permission check happens at this point. One is done at **Confirm** (§4.3).

## 4. Components

### 4.0 custom_id format
`ComponentIdManager(prefix = "giveaway@", idKeys = {action: STRING → "a", sub_action: STRING → "b", giveaway_id: STRING → "c"})` (GW.kt:56-63; `Core/.../util/ComponentIdManager.kt`).
- **Encoding:** `giveaway@` + `key:value` pairs joined by `;`, in the order the map is given. Values pass through the global `%…%` substitutor.
- **Parsing:** strict. Any segment without exactly one `:`, or with an unknown short key, throws.
- **Limit:** 100 characters.
- **Disambiguation:** modals and buttons share the same strings; the interaction type tells them apart.

| custom_id | Kind | Produced by |
|---|---|---|
| `giveaway@a:create;b:set-title` | button and modal | `create-giveaway.yaml` row 1 / `modal/set-title.yaml` |
| `giveaway@a:create;b:set-description` | button and modal | row 1 / `modal/set-description.yaml` |
| `giveaway@a:create;b:set-end-time` | button and modal | row 1 / `modal/set-end-time.yaml` |
| `giveaway@a:create;b:add-prize` | button and modal | row 2 / `modal/add-prize.yaml` |
| `giveaway@a:create;b:remove-prize` | button | row 2 |
| `giveaway@a:create;b:toggle-duplicate-policy` | button | row 2 |
| `giveaway@a:create;b:set-sponsor` | button and modal | row 3 / `modal/set-sponsor.yaml` |
| `giveaway@a:create;b:set-thumbnail` | button and modal | row 3 / `modal/set-thumbnail.yaml` |
| `giveaway@a:create;b:confirm-create` | button | row 4 |
| `giveaway@a:create;b:cancel` | button | row 4 |
| `giveaway@a:participate;c:<id16>` | button | the giveaway post (GW.kt:575-589) |
| `giveaway@a:draw;c:<id16>` | button | the giveaway post (GW.kt:591-604) |
| `giveaway@a:reroll;c:<id16>` | button | the giveaway post (GW.kt:606-619) |

- `<id16>` is 16 lowercase hex characters (§8).
- Text input custom_ids, as raw strings: `title`, `description`, `end-time`, `prize-name`, `winner-count`, `sponsor`, `thumbnail`.
- Routing (EV.kt:85-107; GW.kt:125-149):
  - Any button or modal whose id starts with `giveaway@` is parsed.
  - **Button** `action`: `create` → StepManager; `participate`, `draw`, `reroll` → Giveaway.
  - **Modal:** only `action == "create"` is handled.
  - An unknown action or sub_action means no acknowledgement, so the user sees "This interaction failed".
  - A malformed id throws.
  - String and entity selects with the prefix are logged at debug level and never acknowledged (dead).

### 4.1 Builder message (ephemeral; `lang/<loc>/message/create-giveaway.yaml`)

Button styles: 1 = PRIMARY (blurple), 2 = SECONDARY (grey), 3 = SUCCESS (green), 4 = DANGER (red).

| Row | sub_action | Style | en-US label | zh-TW label |
|---|---|---|---|---|
| 1 | set-title | 1 | Set Title | 設定標題 |
| 1 | set-description | 1 | Set Description | 設定說明 |
| 1 | set-end-time | 1 | Set End Time | 設定結束時間 |
| 2 | add-prize | 3 | Add Prize | 新增獎品 |
| 2 | remove-prize | 2 | Remove Last Prize | 刪除最後獎品 |
| 2 | toggle-duplicate-policy | 2 | Toggle Winner Policy | 切換中獎限制 |
| 3 | set-sponsor | 2 | Set Sponsor | 設定主辦/贊助 |
| 3 | set-thumbnail | 2 | Set Thumbnail | 設定縮圖 |
| 4 | confirm-create | 3 | Confirm Create | 確認建立 |
| 4 | cancel | 4 | Cancel | 取消 |

**Preview embed** (`ga@preview-embed` model; SD.kt:61-128):
- Colour `0x2ECC71`.
- Title `🎁 <title>`. If the title is unset: `🎁 抽獎建立預覽` / `🎁 Giveaway Draft`.
- Fields, in this order:
  1. `抽獎說明` / `Description` (non-inline). The description, or `未設定` / `Not set`.
  2. `結束時間` / `End Time` (non-inline): `<t:END:F>\n<yyyy-MM-dd HH:mm in host TZ>`, or `未設定` / `Not set`.
  3. `獎品清單` / `Prizes` (non-inline): lines `N. <name> (<count> 位)` / `N. <name> (<count> winner(s))`, or `尚未新增獎品` / `No prize yet`. **Not clipped.**
  4. `中獎限制` / `Winner Policy` (non-inline): `允許跨獎品重複中獎` / `Duplicate winners allowed`, or `跨獎品不可重複中獎` / `Unique winners across prizes`.
  5. `總中獎名額` / `Total Winner Slots` (inline): the sum of `max(winnerCount, 1)`.
  6. `主辦/贊助` / `Sponsor` (inline): the sponsor, or `未設定` / `Not set`.
- Thumbnail, set if the URL starts with `http://` or `https://` (case-sensitive).
- Footer `使用下方按鈕逐步設定，最後按「確認建立」` / `Configure step by step, then click Confirm Create`.

**Language selection:**
- Preview text is zh if `userLocale.locale.startsWith("zh")`, otherwise en.
- Button labels come from the YAML for the user's locale. If that locale has no directory, they come from the **config default locale**. An en-GB user therefore sees English preview text with zh-TW button labels.
- **Rendering** always goes through `step.hook.editOriginal(...)`, the *slash command's* interaction token (SD.kt:22-32). That token is valid for 15 minutes.

**Who can use the builder buttons:** only the invoker can see an ephemeral message. Server-side, the session is looked up by `(clicker, guild)`, so if the clicker has no session they get "session expired".

**Common reply when no session exists** (SM.kt:44-54, 70-79, 313-319): ephemeral `建立流程已過期，請重新執行 /create-giveaway。` / `Your setup session expired. Please run /create-giveaway again.`

zh/en for all builder messages follows `userLocale.locale.startsWith("zh")`.

| sub_action (button) | Behaviour |
|---|---|
| set-title, set-description, set-end-time, set-sponsor, set-thumbnail | `replyModal` pre-filled with the current value (table 4.2) |
| add-prize | `replyModal`, pre-filled `prize-name` = `獎品 N` (zh) / `Prize N` with N = current count + 1, and `winner-count` = `1` |
| remove-prize | If there are no prizes: ephemeral `目前沒有可刪除的獎品。` / `No prize to remove.`. Otherwise remove the **last** prize, `deferEdit()`, then re-render the preview through the session hook |
| toggle-duplicate-policy | Switch ALLOW_DUPLICATE ↔ UNIQUE_ACROSS_PRIZES, `deferEdit()`, re-render |
| confirm-create | §4.3 |
| cancel | Remove the session. If it was already gone: the session-expired reply. Otherwise `deferEdit()`, then edit the builder message to `create-cancelled` (`已取消建立抽獎流程。` / `Giveaway setup cancelled.`). This is a **replace** edit, so the embed and buttons are removed (SM.kt:297-311) |

### 4.2 Modals (`lang/<loc>/modal/*.yaml`; Core `ModalCreator`)

How modals are built:
- Each text input is wrapped in a JDA 6 `Label` component.
- `value` is only set when the substituted text is non-blank. The same applies to `placeholder`.
- `min_length` is never set.
- The modal language is the clicker's locale, falling back to the config default.

| Modal custom_id (b:…) | Title en / zh | Input custom_id | Label en / zh | Style | Pre-fill | Placeholder en / zh | max | Required |
|---|---|---|---|---|---|---|---|---|
| set-title | Set Giveaway Title / 設定抽獎標題 | `title` | Giveaway Title / 抽獎標題 | SHORT | `%ga@title%` = current title | Type giveaway title / 輸入抽獎標題 | 100 | yes |
| set-description | Set Giveaway Description / 設定抽獎說明 | `description` | Description / 抽獎說明 | PARAGRAPH | current | Optional description / 可選，填寫抽獎說明 | 4000 | no |
| set-end-time | Set End Time / 設定結束時間 | `end-time` | End Time / 結束時間 | SHORT | current formatted `yyyy-MM-dd HH:mm` (host TZ), or empty | yyyy-MM-dd HH:mm | 20 | yes |
| add-prize | Add Prize / 新增獎品 | `prize-name`; `winner-count` | Prize Name / 獎品名稱; Winner Count / 中獎人數 | SHORT; SHORT | `Prize N` / `獎品 N`; `1` | Prize name / 獎品名稱; Enter a number from 1 to 50 / 請輸入 1 到 50 | 100; 2 | yes; yes |
| set-sponsor | Set Sponsor / 設定主辦/贊助 | `sponsor` | Sponsor / Host / 主辦 / 贊助 | SHORT | current | Optional / 可選 | 100 | no |
| set-thumbnail | Set Thumbnail URL / 設定縮圖網址 | `thumbnail` | Thumbnail URL / 縮圖網址 | SHORT | current | https://... | 1000 | no |

Pre-fill uses the clicker's cached Core substitutor, `Placeholder.get(ButtonInteractionEvent)`, with `ga@…` **put into it**. That cache persists per member.

Substitution is recursive. A draft value containing `%bot_name%` is expanded when pre-filled. A value equal to its own key (e.g. title `%ga@title%`) throws `IllegalStateException`, so the modal is never shown and the interaction fails.

**Modal submit** (SM.kt:70-151):
- The session is looked up as above.
- Every value is Kotlin-`trim()`ed. Kotlin whitespace is Python `isspace()` minus U+0085.
- A validation error produces an **ephemeral reply** and leaves the draft unchanged.
- Success runs `deferEdit()` and then re-renders the preview through the session hook.

| sub_action | Rule → error (zh / en) |
|---|---|
| set-title | Blank → `抽獎名稱不能為空。` / `Giveaway title cannot be empty.` |
| set-description | No validation. Empty clears the field |
| set-end-time | Blank → `請輸入結束時間。` / `Please provide an end time.`<br>Parse failure → `時間格式錯誤，請使用 yyyy-MM-dd HH:mm。` / `Invalid time format. Use yyyy-MM-dd HH:mm.`<br>`epoch <= now` → `結束時間必須是未來時間。` / `End time must be in the future.` |
| add-prize | Name blank → `獎品名稱不能為空。` / `Prize name cannot be empty.`<br>Count missing or not in 1..50 → `中獎人數需為 1 到 50 的整數。` / `Winner count must be an integer between 1 and 50.`<br>On success, append `GiveawayPrize(name, count)`. **There is no cap on the number of prizes** |
| set-sponsor | No validation. Empty clears the field |
| set-thumbnail | Non-empty and not a valid http(s) URL → `縮圖網址格式錯誤，請輸入有效的 http(s) URL。` / `Invalid thumbnail URL. Please provide a valid http(s) URL.`<br>Empty clears the field |
| (unknown) | No change. Still runs deferEdit plus re-render |

**End-time parsing** (SD.kt:130-146).
- Rule: `LocalDateTime.parse(s, ofPattern("yyyy-MM-dd HH:mm"))` with the SMART resolver, then `.atZone(ZoneId.systemDefault())`, then the epoch second. **The host JVM time zone is used**; the dev machine is Asia/Taipei.
- Verified results:
  - Accepted: `2026-03-01 10:00`; `9999-12-31 23:59`; `0001-01-01 00:00`; `+12026-01-05 10:00` (a 5+ digit year needs `+`).
  - **The day is clamped to the month length:** `2026-02-30` → 02-28, `2025-02-29` → 02-28, `2026-04-31` → 04-30.
  - **`24:00` rolls to the next day at 00:00:** `2026-12-31 24:00` → 2027-01-01 00:00, and `2026-02-30 24:00` → 2026-03-01 00:00.
  - Rejected: `24:01`, `23:60`, single-digit fields (`2026-1-05`, `9:00`), the `T` separator, seconds, `/`, a two-digit year, `0000`, a double space, a leading `+` on a 4-digit year, full-width digits, month `00`/`13`, day `00`/`32`.
  - Python `strptime` differs: it accepts single digits and rejects Feb 30. Port with an explicit regex plus clamping.
- Prefill and preview format: `Instant.atZone(systemDefault).format("yyyy-MM-dd HH:mm")`.

**Winner-count parsing.** It uses Kotlin `String.toIntOrNull()` after trimming.
- Accepted: `+5`, `05`, and **Unicode decimal digits** such as `５` and `٥`.
- Rejected: `1_0`, `1e1`.
- Python `int()` additionally allows `_`, but that cannot produce a valid value within the max length of 2.

**Thumbnail validation** (SM.kt:373-379): `java.net.URI(value)`. The scheme must equal `http`/`https` ignoring case, and the host must be non-null and non-blank.

| Verified: accepted | Verified: rejected |
|---|---|
| `https://example.com/a.png`, `HTTPS://EXAMPLE.COM/a.png`, `http://x`, `https://user@host:8080/p?q#f`, `https://1.2.3.4/x`, `https://[::1]/x`, `https://xn--fsqu00a.xn--0zwm56d/a.png` | `https://`, `https:///path`, `ftp://x.com`, `https://exa mple.com`, `https://例子.测试/a.png` (IDN not punycoded), `https://host_name.com/x`, `//host/p`, `javascript:alert(1)` |

### 4.3 Confirm Create (SM.kt:247-295)

1. `step.validate(userLocale)`, checked in this order. The first failure becomes an ephemeral reply.
   - Title blank → `請先設定抽獎名稱。` / `Please set giveaway title first.`
   - `endAt <= now` → `請設定未來的結束時間。` / `Please set an end time in the future.`
   - No prizes → `請至少新增一個獎品。` / `Please add at least one prize.`
2. If `guild == null` → `Guild not found.` (unreachable).
3. **The clicker must have ADMINISTRATOR now.** Otherwise reply with ephemeral `你已失去管理員權限，無法完成建立。` / `Administrator permission is required to finish creation.` This applies even if the server overrode the command's default permission for non-admins.
4. `event.deferEdit()`.
5. `Giveaway.createGiveaway(guildId, channel = event.channel, creatorId = clicker, config = draft, locale = clicker's userLocale)` (GW.kt:187-244):
   - ID: `UUID.randomUUID()` → hex without dashes → first 16 characters. Retried until the ID is unique within the guild.
   - It builds the `GiveawayInstance`, with a deep copy of the draft and `localeTag = userLocale.locale`.
   - It renders `giveaway-post` and calls `channel.sendMessage(...)`. The message is public and posted in the channel where the builder was opened.
   - It then `.map`s on the callback thread: set `messageId`, `data[id] = instance`, `save()`. If an exception escapes (`save()` swallows `IOException`), it deletes the posted message and rethrows.
6. **Success** callback:
   - `steps.remove(sessionKey)`.
   - `step.hook.editOriginal(create-finished)` → `Giveaway created successfully: <jumpUrl>` / `抽獎建立成功：<jumpUrl>`. This is a replace edit: the embed and buttons are removed.
7. **Async failure** callback:
   - `step.hook.editOriginal(create-failed)` → `Failed to create giveaway: <throwable.message or "unknown">` / `建立抽獎失敗：…`. This replace edit also removes the buttons.
   - **The session is kept**, but no buttons remain to drive it.
8. **Synchronous exceptions** escape after `deferEdit` and are never reported to the user:
   - JDA's client-side `InsufficientPermissionException` from `sendMessage` (missing VIEW_CHANNEL or SEND_MESSAGES / SEND_MESSAGES_IN_THREADS);
   - an `IllegalStateException` from an embed over 6000 characters.

### 4.4 Giveaway post (public; `message/giveaway-post.yaml` = embed model + 3 button models)

The language is **the giveaway's `localeTag`** (the creator's Discord locale): zh if `substringBefore('-') == "zh"` (case-insensitive), otherwise en. It does not depend on the viewer (GW.kt:621-627).

**Embed** (GW.kt:481-573):
- Title `🎉 <title>`. **This is raw, without placeholder substitution.**
- Description: the giveaway description, or `按下下方按鈕參加抽獎。` / `Press the button below to join.`
- Colour: `0xF1C40F` while not ended, `0x95A5A6` once ended.
- Fields:
  1. `狀態` / `Status` (inline): `<status>\n<t:END:R>`. The status is `已開獎`/`Drawn` if ended; else `可開獎`/`Ready to draw` if now ≥ END; else `進行中`/`Running`. It is computed **at render time only**.
  2. `參與人數` / `Participants` (inline): the participant count.
  3. `中獎限制` / `Winner Policy`: `每個獎品可重複中獎` / `Duplicates allowed across prizes`, or `跨獎品不得重複中獎` / `Unique winners across prizes`. The wording differs from the preview.
  4. `獎品` / `Prizes`: lines `N. <name> (<count> 位|winner(s))`, clipped to 1024.
  5. `中獎結果` / `Winner Results`: `尚未開獎` / `Not drawn yet`, or one line per prize `<prize>: <@id> <@id>…`, or `<prize>: （名額不足）` / `(not enough participants)` when there are zero winners. Clipped to 1024.
  6. Only if the sponsor is non-blank: `主辦 / 贊助` / `Sponsor` (inline).
- Thumbnail if it starts with `http(s)://` (case-sensitive).
- Footer `Giveaway ID: <id>` in both languages. No timestamp.
- `clipFieldText(s, max)`: if the length exceeds `max`, the first `max-3` UTF-16 units plus `...`.

**Buttons** (one row):

| Button | Style | Label zh / en | Disabled when (at render) |
|---|---|---|---|
| Join/Leave | SUCCESS | `參加 / 退出` / `Join / Leave` | `ended`, or now ≥ END |
| Draw | PRIMARY | `手動開獎` / `Draw Winners` | `ended` |
| Reroll | SECONDARY | `重抽` / `Reroll` | not `ended` |

Clicks on post buttons go through `resolveGiveaway` first (GW.kt:388-409):
- No guild → `Guild not found.`
- Missing `c` → `Invalid giveaway id.`
- Not found in this guild → `找不到該抽獎，可能已被刪除。` / `Giveaway not found.` Here zh/en follows the **clicker's** locale.
- All of these are ephemeral.

**participate** (GW.kt:246-279). Anyone can click; there are no eligibility checks.
1. If the clicked message ID ≠ the stored `messageId`: `deferEdit()` silently, with no change.
2. If `ended` or `now >= END`: ephemeral `抽獎已截止，無法再參加。` / `This giveaway is closed.` The message is not refreshed.
3. **Toggle:** add the user if absent, or remove them if present.
4. Save the guild file.
5. Edit the clicked message through REST, re-rendering the embed with the new count.
6. Reply ephemerally: `你已成功參加抽獎。` / `You joined the giveaway.`, or `你已取消參加抽獎。` / `You left the giveaway.`

**draw / reroll** (GW.kt:281-352):
1. If `member == null`, or the user is not allowed: `只有建立者或管理員可執行此操作。` / `Only creator/admin can do this.`
   - **Draw** is allowed for the creator OR a member with ADMINISTRATOR (the guild owner counts).
   - **Reroll** is allowed for **ADMINISTRATOR only**. A creator who lost admin cannot reroll.
2. Draw rejections:
   - already ended → `此抽獎已開獎，可使用重抽。` / `Already drawn. Use reroll.`
   - `now < END` → `尚未到開獎時間（<t:END:R>）。` / `Too early to draw winners (<t:END:R>).`
3. Reroll rejection: not ended → `抽獎尚未開獎，不能重抽。` / `Giveaway not drawn yet.`
4. When allowed:
   - `winnerResults = drawPrizeWinners(config, participants)`; `ended = true`; `endedAt = now`.
   - Save, then refresh the clicked message.
   - **Ephemeral** reply `draw-result`: `**<header>**\n<body>`.
     - Header: `開獎完成` / `Draw finished`, or `重抽完成` / `Reroll finished`.
     - Body: `目前沒有任何參與者。` / `There are no participants.` if nobody joined. Otherwise one line per prize, `<prize>: <@id> …` or `（名額不足）`/`(not enough participants)`, clipped to 1800.
   - Only the drawer sees the mention list. Mentions in the public embed field do not ping.

### 4.5 Expiry and timeouts

| Item | Expiry behaviour |
|---|---|
| Builder sessions | **Never expire by time.** Removed by successful confirm, cancel, guild leave, or a process/class-loader restart |
| Builder rendering | Uses the slash command token. After 15 minutes previews and the finish/cancel edits fail silently (only logged); giveaway creation itself still works |
| Post buttons | Stateless and permanent. They keep working across restarts while the data record exists |

## 5. Events

| JDA event | Filter | Behaviour |
|---|---|---|
| `onSlashCommandInteraction` | enabled, name `create-giveaway` | §3 |
| `onButtonInteraction` | enabled, id prefix `giveaway@` | §4 |
| `onModalInteraction` | enabled, id prefix `giveaway@`, action `create` | §4.2 |
| `onStringSelectInteraction` / `onEntitySelectInteraction` | enabled, prefix | debug log only, never acknowledged (dead) |
| `onGuildLeave` | **enabled only** | Drop all builder sessions for the guild, **and delete `data/<guildId>.json`** (`jsonGuildManager.removeAndSave` → `JsonFileManager.delete()`; GW.kt:151-154). Giveaway data is lost permanently. While the plugin is disabled, nothing is deleted |

## 6. Configuration (`config.yaml`)

| Key | Type | Default (code / shipped) | Semantics |
|---|---|---|---|
| `enabled` | Boolean | `false` / `false` | When false: no command, no handlers, no scheduler, no guild-leave cleanup. **The object still initialises**, so storage and templates are loaded |
| `defaultLocale` | String | `"zh-TW"` / `"zh-TW"` | Fallback locale for message and modal templates and for `register.yaml`. It must exactly equal a Discord locale tag *and* have a `lang/<tag>/register.yaml`. Otherwise startup aborts (e.g. `zh-tw` gives `UNKNOWN`) |
| `autoDrawIntervalSeconds` | Long | `60` / `60` | Scheduler period, clamped to `[5, 3600]`. The initial delay is always 5 s |

Keys are camelCase; there is no `@SerialName`. Kaml strict mode makes unknown keys fatal.

## 7. Localization and templates

**Locales and selection:**
- Locales: `en-US`, `zh-TW`.
- The fallback is `config.defaultLocale`, used for templates and modals.
- Hard-coded text (most user-facing strings) chooses between zh and en by locale prefix.

**Files under `lang/<loc>/`:**
- `register.yaml`
- `message/`: `create-giveaway`, `giveaway-post`, `create-finished`, `create-failed`, `create-cancelled`, `draw-result`, `auto-draw-result`
- `modal/`: `set-title`, `set-description`, `set-end-time`, `add-prize`, `set-sponsor`, `set-thumbnail`

**Template engines:** the v2 `MessageCreator` reads v1-shaped YAML (`content`, `embeds` with `model_key`, and `components: !ButtonsComponent` rows). Modals use the Core `ModalCreator`.

**Content templates** (`replaceMap` is put into the **global** substitutor):

| Key | en-US | zh-TW |
|---|---|---|
| create-finished | `Giveaway created successfully: %ga@jump-url%` | `抽獎建立成功：%ga@jump-url%` |
| create-failed | `Failed to create giveaway: %ga@error%` | `建立抽獎失敗：%ga@error%` |
| create-cancelled | `Giveaway setup cancelled.` | `已取消建立抽獎流程。` |
| draw-result | `**%ga@header%**\n%ga@body%` | same |
| auto-draw-result | `⏰ Auto draw completed for **%ga@title%**\n**%ga@header%**\n%ga@body%` | `⏰ **%ga@title%** 已自動開獎\n**%ga@header%**\n%ga@body%` |

**Placeholders defined by this plugin:**
- Modal pre-fill: `ga@title`, `ga@description`, `ga@end-time`, `ga@prize-name`, `ga@sponsor`, `ga@thumbnail`.
- Content templates: `ga@jump-url`, `ga@error`, `ga@header`, `ga@body`.
- Model keys: `ga@preview-embed`, `ga@giveaway-embed`, `ga@join-button`, `ga@draw-button`, `ga@reroll-button`.

**Core placeholders reachable in modals:** via `Placeholder.get(ButtonInteractionEvent)` — `user_*`, `member_*`, `component_id`, `component_label`, `component_style`, `language`, `channel_id`, `channel_name`, `bot_id`, `bot_name`.

**Hard-coded strings.** Every participate, draw and validation message, plus the embed field names and statuses, is hard-coded in Kotlin (quoted verbatim above), not in lang files.

## 8. Persistence

**Storage:**
- Core `JsonGuildFileManager<MutableMap<String, GiveawayInstance>>` with Moshi + `KotlinJsonAdapterFactory`.
- **One file per guild: `plugins/Giveaway/data/<guildId>.json`.** All files are loaded eagerly at object initialisation.
- There is no Mongo or SQLite.

**Schema:** a map from giveaway ID to `GiveawayInstance` (GD.kt:7-65). Defaults apply when a field is missing on read.

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | String | required | 16 hex characters. Character 13 is always `4` (UUIDv4 version nibble) |
| `guildId`, `channelId`, `messageId`, `creatorId` | Long | required | |
| `localeTag` | String | `"zh-TW"` | The creator's Discord locale tag |
| `createdAtEpochSecond` | Long | **now at decode time** | Written, never read |
| `endedAtEpochSecond` | Long? | null | **Omitted from the JSON while null.** Set on draw, reroll and auto-draw. Never read |
| `ended` | Boolean | false | |
| `config.title`, `description`, `sponsor`, `thumbnailUrl` | String | `""` | |
| `config.endAtEpochSecond` | Long | 0 | Epoch seconds, UTC |
| `config.winnerDuplicatePolicy` | enum name | `ALLOW_DUPLICATE` | `ALLOW_DUPLICATE` or `UNIQUE_ACROSS_PRIZES`. Any other value raises `JsonDataException` |
| `config.prizes[]` | `{name: String, winnerCount: Int = 1}` | `[]` | |
| `participantIds` | array of Long (a set; insertion order kept) | `[]` | |
| `winnerResults[]` | `{prizeName: String, winnerIds: [Long]}` | `[]` | One entry per prize, in prize order |

Example (exact Moshi output: compact, field order as shown):
```json
{"3f2a9c1b7e4d4a60":{"id":"3f2a9c1b7e4d4a60","guildId":852521987557556284,"channelId":900000000000000001,"messageId":1234567890123456789,"creatorId":270062130470846465,"localeTag":"zh-TW","createdAtEpochSecond":1767000000,"ended":false,"config":{"title":"Nitro","description":"desc","sponsor":"","thumbnailUrl":"https://x/y.png","endAtEpochSecond":1767225600,"winnerDuplicatePolicy":"UNIQUE_ACROSS_PRIZES","prizes":[{"name":"Nitro","winnerCount":2},{"name":"Sticker","winnerCount":1}]},"participantIds":[111,222,333],"winnerResults":[]},
 "0123456789ab4def":{"id":"0123456789ab4def",…,"createdAtEpochSecond":1767000000,"endedAtEpochSecond":1767225660,"ended":true,…,"winnerResults":[{"prizeName":"Nitro","winnerIds":[222,111]},{"prizeName":"Sticker","winnerIds":[333]}]}}
```
Snowflakes are written as JSON numbers, larger than 2^53. Python's `json` handles them; JavaScript would not.

**Write and read semantics** (Core):
- **Writes happen on:**
  - create, inside the `sendMessage` success mapping, so a record exists only if the post succeeded;
  - every join or leave;
  - draw and reroll;
  - once per guild per scheduler tick when something was auto-drawn.
- **Write method:** the whole file, `File.writeText`. Non-atomic.
- **Load:** every file is re-saved immediately.
- **Errors:**
  - A missing required field (e.g. `"Required value 'creatorId' missing at $.abc"`), a bad enum, or malformed JSON → **the guild file is replaced with `{}` and overwritten**.
  - `IOException` on save is logged and swallowed.
- **No retention policy:** ended giveaways are never purged; they are needed for reroll.
- **Deletion:** only on guild leave (whole file).

**Migration and compatibility:**
- The port must read this layout, or import it once. Important cases: the omitted `endedAtEpochSecond`, the camelCase field names, enum names, 64-bit numbers, and duplicate-free `participantIds`.
- `createdAtEpochSecond` defaulting to "now" is a Kotlin artefact; specify it explicitly.

## 9. External dependencies

- No Gradle dependencies beyond Core.
- No HTTP calls by the plugin; Discord renders the user-supplied thumbnail URL.
- No credentials.
- No plugin dependencies.
- JVM APIs whose semantics the port must reproduce: `java.time` (host zone), `java.net.URI`, `java.util.UUID`, `kotlin.random.Random.Default`.

## 10. Discord requirements

- **Privileged intents:** none needed by this plugin. `GuildLeaveEvent` needs only the GUILDS intent; member objects come from the interaction payload.
- **Cache:** default guild and channel caches. `jdaBot.getGuildById` and `guild.getTextChannelById` are used by auto-draw.
- **Bot permissions in the giveaway channel:**
  - View Channel;
  - Send Messages (Send Messages in Threads for threads);
  - Embed Links;
  - **Read Message History** (auto-draw refresh uses `retrieveMessageById`, and JDA throws `InsufficientPermissionException` client-side without it).
  - Mention Everyone is not needed, but if granted, a title containing `@everyone` pings everyone in the auto-draw announcement. JDA's default allowed mentions include all types.
- **User side:** the command requires ADMINISTRATOR by default, and Confirm re-checks ADMINISTRATOR.
- **Rate-limit-sensitive operations:**
  - Each join or leave costs 1 interaction reply + 1 message PATCH on the same message. A burst hits the channel's message-edit bucket, so JDA delays the edits and the count lags.
  - Each auto-draw costs GET + PATCH + POST per due giveaway.

## 11. Concurrency

**Threads:**
1. **JDA gateway thread:** all interaction handlers, sequentially. Core sets no event pool.
2. **JDA callback pool:**
   - `deferEdit().flatMap { render }`;
   - the `createGiveaway` `.map {}` (persistence);
   - the confirm success and failure callbacks, which mutate `steps`.
3. **`giveaway-auto-draw` scheduler thread:** `processAutoDraw`, including file saves and global-substitutor writes.

**Unsynchronized shared state:**

| State | Who touches it | Hazard |
|---|---|---|
| `StepManager.steps` (`HashMap`) | gateway thread, callback thread (remove on success) | data race |
| `jsonGuildManager.mapper` (`LinkedHashMap`) | gateway thread inserts new guilds; scheduler iterates | `ConcurrentModificationException`, caught and retried next tick |
| `manager.data` (Moshi map) | gateway, callback and scheduler threads | `ConcurrentModificationException` inside `toJson` during `save()` is **not** an `IOException`, so it propagates. On the gateway thread it fails the interaction |
| `GiveawayInstance` fields (`participantIds`, `winnerResults`, `ended`, `endedAt`) | gateway and scheduler threads | no `volatile` or locks, see the double-draw race below |
| Core `Placeholder.globalSubstitutor` (`HashMap`) | gateway thread (`draw-result`, `create-*`) and scheduler thread (`auto-draw-result`) | concurrent writes |

`JsonFileManager.save()` is `@Synchronized` per file. That serializes writes but does not protect the data.

**Double-draw race.** A manual draw and the scheduler can both see `ended == false` and both draw. The result is two different winner sets, each announced or replied, and the last save wins.

**Reentrancy:** two fast clicks on **Confirm Create** both pass validation, because the session is only removed in the async success callback. The result is **duplicate giveaways**.

## 12. Bugs, quirks, dead code

Probable bugs to fix:
1. **Double-submit on Confirm creates duplicate giveaways** (SM.kt:247-295, session removed at L273).
2. **The preview stops updating silently** when the description exceeds 1024 characters (it is placed in an embed *field*, SD.kt:101) or when the prize list exceeds 1024 characters (unclipped, SD.kt:103). JDA throws inside the `flatMap` (SM.kt:148-150, 215-224). The modal allows a 4000-character description.
3. **The builder renders through the slash-command token** (SD.kt:31; SM.kt:275, 285, 304). After 15 minutes previews, finish and cancel edits fail silently.
4. **Old builder messages drive the newest session.** Sessions are keyed by (user, guild), not by message (SM.kt:40).
5. **Sessions never expire**, which is an unbounded leak (SM.kt:22). After `create-failed`, the session is kept but its buttons are gone.
6. **Synchronous failures in `createGiveaway` give the user no feedback** (permission exception, embed size). See §4.3 step 8.
7. **Auto-draw only resolves `TextChannel`** (GW.kt:432, 452). Giveaways in threads, announcement channels, voice/stage text chats or forum posts are drawn and marked ended **silently**: no message refresh, no announcement.
8. **Auto-draw saves only after queuing the REST calls** (GW.kt:163-183). A crash in between causes a re-draw with different winners on restart, and possibly two announcements.
9. **Guild leave permanently deletes all giveaway data** for the guild, despite the method name `removeAndSave`.
10. **An invalid `defaultLocale` does not fall back to zh-TW** (`DiscordLocale.from` returns `UNKNOWN`), so startup aborts (EV.kt:22-25).
11. **A disabled plugin still initialises storage and templates** (EV.kt:29). A bad data file or bad YAML can abort the bot even when disabled.
12. **Thumbnail:** an uppercase scheme passes validation but is never displayed, because display uses a case-sensitive `startsWith` (SM.kt:373-379 vs SD.kt:116 and GW.kt:561).
13. **Recursive placeholder substitution of user text** (title, description, sponsor) in modal pre-fill and in the draw/auto-draw content. `%…%` expands and a self-reference crashes. `replaceMap` also **mutates the global substitutor**, so `ga@*` keys leak into every plugin.
14. **Auto-draw announcement content pings** winners and anything mentionable in the title (JDA default allowed mentions are all types).
15. **Malformed `giveaway@…` IDs throw** in `ComponentIdManager.parse`. Unknown actions are never acknowledged.
16. **Concurrency races** (§11).
17. **The "Ready to draw" status is effectively never shown.** The post is not re-rendered when the end time passes (GW.kt:485-489).
18. **Mixed languages:** zh/en is chosen by locale prefix, while templates fall back to the config default (e.g. an `en-GB` user gets English text with zh-TW button labels; a `ja` creator gets an English embed with a zh-TW `auto-draw-result` wrapper).

Behaviour to preserve (unless the spec decides otherwise):
- **Admin-only creation**, with ADMINISTRATOR re-checked at confirm.
- **Permissions:** draw for the creator or an admin; reroll for admins only.
- **Join is a toggle.** Joining closes at `now >= END`, inclusive.
- **Manual draw is allowed at `now >= END`.** **Auto-draw runs on the first tick with `END <= now`.** The initial tick comes 5 s after (re)load; the period is the clamped config value.
- **Overdue giveaways are drawn on startup.**
- **Winner algorithm** (below).
- **Reroll is a full redraw** of every prize from the frozen participant set, previous winners included.
- **Result visibility:** the manual draw result is ephemeral; the auto-draw announcement is public.
- **Post language** follows the creator's locale.
- **End time** is parsed as `yyyy-MM-dd HH:mm` in the host time zone. Make the zone configurable, but keep the default.
- **All custom_id formats** (so existing posts keep working after migration).
- **The data file layout.**

Dead code:
- `GiveawayConfig.isReady()` (GD.kt:26-28).
- The select handlers (GW.kt:136-142).
- The `runCatching` fallback in `resolveLocale`.
- `createdAtEpochSecond` and `endedAtEpochSecond` are never read.
- The identical zh/en footer branches (GW.kt:565-571).
- No TODO or FIXME comments.

### Winner selection (exact, `drawPrizeWinners`, GD.kt:67-102)
```
if no prizes: return []
basePool   = list(participants)            # set iteration order
uniquePool = list(participants)
for prize in config.prizes (list order):
    k    = max(prize.winnerCount, 1)
    pool = basePool if policy == ALLOW_DUPLICATE else uniquePool
    if pool empty: result += (prize.name, []); continue
    picked = shuffled(pool, rng)[:min(k, len(pool))]     # Kotlin Iterable.shuffled = Fisher-Yates
    result += (prize.name, picked)                        # winner order = shuffle order
    if policy == UNIQUE_ACROSS_PRIZES: uniquePool -= picked
return result
```
- **RNG:** `kotlin.random.Random.Default`, which is backed by `ThreadLocalRandom` on the JVM. It is **unseeded, not cryptographically secure, not reproducible**, and leaves no audit log.
- **Within a prize:** sampling is uniform, without replacement.
- **ALLOW_DUPLICATE:** one person may win several different prizes.
- **UNIQUE_ACROSS_PRIZES:** earlier prizes have priority. Once the pool is exhausted, later prizes get fewer winners or none.
- **Short pools:** a prize gets `min(k, available)` winners. "Not enough participants" is shown **only when it has zero**.
- **Eligibility:** participants are not re-validated. Users who left the guild can win.

### State machines

**Builder session** (key = (userId, guildId); in memory only):
```
(none) --/create-giveaway--> DRAFT                       # replaces any existing DRAFT for the key
DRAFT  --button set-*/add-prize--> modal shown ---submit(valid)--> DRAFT' (+re-render)
                                               ---submit(invalid)--> DRAFT (ephemeral error)
DRAFT  --remove-prize (prizes>0)--> DRAFT' ; (prizes==0) -> ephemeral "No prize to remove."
DRAFT  --toggle-duplicate-policy--> DRAFT'
DRAFT  --confirm (invalid | not admin)--> DRAFT (ephemeral error)
DRAFT  --confirm (ok)--> SUBMITTING(implicit; still DRAFT, buttons live!) --post ok--> (none) [builder := create-finished]
                                                                          --post failed--> DRAFT orphaned [builder := create-failed]
DRAFT  --cancel--> (none) [builder := create-cancelled]
any    --guild leave / restart--> (none)
(none) --any builder button/modal--> ephemeral "session expired"
```

**Giveaway** (persisted; END = `config.endAtEpochSecond`):

| State | Condition | Join/Leave | Draw (creator/admin) | Reroll (admin) | Auto-draw |
|---|---|---|---|---|---|
| RUNNING | `!ended && now < END` | toggle | "Too early" | "not drawn yet" | skip |
| DUE | `!ended && now ≥ END` | "closed" | → DRAWN | "not drawn yet" | → DRAWN (+public announcement) |
| DRAWN | `ended` | "closed" | "Already drawn. Use reroll." | → DRAWN (new winners) | skip |
| GONE | record or file absent | "Giveaway not found." | same | same | n/a |

There is no cancel, delete, edit or end-early command.

### Timing
- **Units:** epoch seconds throughout. All comparisons use `Instant.now().epochSecond`, truncated.
- **Auto-draw latency after END:** `(0, P]` seconds, where P = clamp(interval, 5, 3600), plus processing. Ticks run at `T0+5s + n·P`, where T0 is the last load or reload.
- **No catch-up storms:** each due giveaway is drawn exactly once; `ended` is persisted.

### Restart recovery
1. All guild files are reloaded eagerly.
2. Post buttons keep working, because custom_ids are stateless and routing is by prefix.
3. DUE giveaways, including those whose END passed while offline, are drawn at the first tick (about 5 s after load), with participants as last persisted.
4. Builder drafts are lost, so clicks get "session expired".
5. Clicks made while the bot was offline fail on Discord's side ("This interaction failed").
6. If the bot was removed from a guild while offline, no `GuildLeaveEvent` arrives. The data stays, and auto-draw still draws it but skips the refresh and announcement because the guild is not in the cache.

## 13. Testability

Pure functions to extract (all deterministic, given injected `now`, `tz` and `rng`):
- `draw_prize_winners(prizes, policy, participants, rng)`. Properties:
  - winners ⊆ participants;
  - no duplicates within a prize;
  - with UNIQUE, no duplicates across prizes;
  - `len = min(k, available)`;
  - prize order is preserved;
  - uniform distribution (chi-square with a seeded rng).
- `parse_end_time(text, tz) -> epoch | Error`, using the exact rules in §4.2.
- `format_end_time(epoch, tz)`.
- `is_valid_http_url(text)`, using the java.net.URI-equivalent rules and the table in §4.2.
- `parse_winner_count(text)`.
- `validate_draft(draft, now) -> error_key | None`.
- `clip_field_text(s, max)`.
- `render_preview(draft, locale) -> embed dict` and `render_post(giveaway, locale, now) -> (embed dict, buttons)`.
- `build_draw_result(giveaway, locale, reroll) -> (header, body)`.
- Permission predicates: `can_draw(member_is_admin, is_creator)` and `can_reroll(member_is_admin)`.
- Transitions: `toggle_participation(giveaway, user, now) -> joined|left|closed`.
- `due_giveaways(all, now)`.
- `encode_custom_id(fields)` / `decode_custom_id(str)`.
- JSON (de)serialization round-trip against the Moshi examples above, including the omitted `endedAtEpochSecond`.

Tests that need Discord doubles:
- Builder flow: an ephemeral original response; a modal round-trip; `deferEdit` plus edit of the original.
- Post creation: `channel.send`, and the jump URL.
- Join, draw and reroll replies, plus the REST edit of the post.
- Auto-draw: fetch the message by ID, edit it, and send the announcement, including permission failures and non-text channels.
- Guild leave.
- A fake clock for the scheduler (`tasks.loop` with an injectable `now`).

## 14. Porting assessment

**Difficulty: High.** The plugin combines:
- a multi-step modal builder with in-memory sessions and token-lifetime subtleties;
- persistent component routing that must survive restarts;
- a background scheduler with catch-up semantics;
- per-guild JSON persistence with compatibility needs;
- randomness that should be testable;
- host-time-zone date parsing with Java SMART-resolver quirks;
- mixed localisation rules (many hard-coded strings);
- several latent races and bugs whose fixes must be decided in the spec.

discord.py mapping:
- **Cog:** `/create-giveaway` with `@app_commands.default_permissions(administrator=True)` and `@app_commands.guild_only()`; localizations via a `Translator`.
- **Builder:** `interaction.response.defer(ephemeral=True)`, then `edit_original_response(embed, view)`.
  - Route builder buttons and modals globally with `ui.DynamicItem` templates such as `giveaway@a:create;b:(?P<sub>[a-z-]+)` registered in `setup_hook`, so a post-restart click yields "session expired" rather than "interaction failed".
  - Modals: `ui.Modal(custom_id="giveaway@a:create;b:<sub>")` with `ui.Label` + `ui.TextInput(custom_id=…, style, default, placeholder, max_length, required)` (discord.py ≥ 2.6).
  - For updates, prefer the **current** interaction (`interaction.response.edit_message` for buttons, or `defer` + `edit_original_response`) over the original slash token. This fixes the 15-minute expiry, but it is a behaviour change; put it in the spec.
- **Post:** persistent `DynamicItem` buttons with template `giveaway@a:(?P<action>participate|draw|reroll);c:(?P<gid>[0-9a-f]{16})`. Keep the exact strings so existing Kotlin-era posts keep working after migration.
- **Scheduler:** `@tasks.loop(seconds=clamp(interval, 5, 3600))` with `before_loop` → `await bot.wait_until_ready(); await asyncio.sleep(5)`. Restart it on reload.
- **Persistence:** keep everything on the event loop. Use a per-guild `asyncio.Lock` around read-modify-write and draw, and atomic file writes. Persist the draw **before** announcing.
- **Randomness:** inject the RNG (`random.SystemRandom()` in production, a seeded `random.Random` in tests).
- **Time zone:** use `zoneinfo` with a configurable zone, defaulting to the host local zone.
- **Allowed mentions:** pass `discord.AllowedMentions(users=True, roles=False, everyone=False)` on announcements. This is a deliberate change.

Risks:
- Data-file compatibility and the Core "wipe on parse error" behaviour.
- Preserving custom_id strings exactly.
- Java date-parse parity.
- Deciding which quirks (#1-#18 in §12) to fix versus preserve.
- Discord rate limits on join bursts.
- Testing scheduler timing deterministically.
