# SimpleCommand: porting inventory (branch `main`)

Repo: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. JDA 6.4.1, kaml 0.104.0, coreApi `3.4`.
Line references are relative to `Plugins/SimpleCommand/src/main/kotlin/simplecommand/` unless prefixed with `Core:` (= `Core/src/main/kotlin/core/`) or `res:` (= `Plugins/SimpleCommand/src/main/resources/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/SimpleCommand` |
| Kotlin files / LOC | 5 files, 209 physical lines (174 non-blank): `command/Register.kt` 59, `Event.kt` 62, `SimpleCommand.kt` 58, `command/CmdFileSerializer.kt` 22, `config/ConfigSerializer.kt` 8 |
| Resources | `config.yaml`, `info.yaml`, `lang/zh-TW/register.yaml`, `lang/zh-TW/message/{cub-none-card,tsib-none-card,ctcb-none-card,ctcb-remit,chpytwtp-remit}.yaml` (8 files; zh-TW only) |
| Tests | none (`src/test/` holds only a `.DS_Store`) |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:14). `listener = true` |
| Build | `plugins { id("xs-plugin") }` (Core compileOnly only); `version.patch=0` → `3.4.0-SNAPSHOT` |

**Purpose.** Five admin-only slash commands. Each posts a fixed, pre-written embed with bank payment instructions for a shop (bank name, bank code, account number, and a "third-party verification" note asking the payer to write their Discord ID and "storA 商城" on the transfer slip). The root README describes it as a "自定義命令系統" (custom command system). In practice the command set is hard-coded in Kotlin; only the message contents live in editable YAML.

**info.yaml** (`res:info.yaml`, after Gradle expand):
```yaml
author: xinshoutw
name: SimpleCommand
coreApi: "3.4"
version: 3.4.0-SNAPSHOT
main: "tw.xinshou.discord.plugin.simplecommand.Event"
```
It sets no `component_prefix` (Core derives `simplecommand@`, which nothing uses), and declares no intents, cache flags, member cache policies, dependencies, or description.

---

## 2. Lifecycle

- **load()** (Event.kt:17-30): `super.load()` exports `lang/` to `plugins/SimpleCommand/lang/` without overwriting existing files, and reads `plugins/SimpleCommand/config.yaml`.
  - If `enabled` is false, it logs the WARN `SimpleCommand is disabled.` and stops.
  - Otherwise it builds `StringLocalizer<CmdFileSerializer>(plugins/SimpleCommand, default zh-TW)`. zh-TW `register.yaml` must exist or the localizer throws `Default locale not found…`.
- **reload()** (Event.kt:32-47): re-reads config. If disabled, it logs the WARN and returns. Otherwise it rebuilds the localizer and calls `SimpleCommand.reload()` (rebuilds the `MessageCreator`, SimpleCommand.kt:14-19).
- **unload()** is not overridden. **guildCommands()** (Event.kt:55-61) returns an empty array when disabled, otherwise the 5 commands.
- **Lazy initialization:** the `SimpleCommand` object initializes on first access. It holds a v2 `MessageCreator(plugins/SimpleCommand, zh-TW)` with no `ComponentIdManager`.
- There are no background jobs and no state besides the creator.

---

## 3. Slash commands

All five are **guild** commands. Core registers them in every guild, and again on guild join.
- `default_member_permissions = ADMINISTRATOR`. There is no runtime permission check.
- No options, no guild_only or NSFW flags.
- Base description: `generate message`.
- Localizations come from `lang/zh-TW/register.yaml` only. Lookup keys are Kotlin property paths such as `cubNoneCard.name`, mapped by `@SerialName` from YAML keys such as `cub-none-card` (CmdFileSerializer.kt:7-23, Register.kt:17-37).
- en-US clients see the base English names.

| Base name | zh-TW name | zh-TW description | Template key | Embed title | Thumbnail | Fields |
|---|---|---|---|---|---|---|
| `cub-none-card` | `國泰世華-無卡` | `取得訊息` | `cub-none-card` | `國泰世華 - 無卡` | `https://i.meee.com.tw/eXLqPPg.png` | `請配合三方驗證`: "在明細寫您的 Discord ID 以及 storA 商城，然後拍照上傳明細\n教學 https://youtu.be/s52-kgtvgCs" · `銀行帳號`: "`<redacted>`" |
| `tsib-none-card` | `台新銀行-無卡` | `取得訊息` | `tsib-none-card` | `台新銀行 - 無卡` | `https://i.meee.com.tw/JVTYdRJ.png` | `請配合三方驗證`: (same two-line text as above) · `銀行帳號`: "`<redacted>`" |
| `ctcb-none-card` | `中國信託-無卡` | `取得訊息` | `ctcb-none-card` | `中國信託 - 無卡` | `https://i.meee.com.tw/9SF70gL.png` | `請配合三方驗證`: (same two-line text) · `銀行帳號`: "`<redacted>`" |
| `ctcb-remit` | `中國信託-匯款` | `取得訊息` | `ctcb-remit` | `中國信託 - 匯款` | `https://i.meee.com.tw/9SF70gL.png` | `請配合三方驗證`: "在明細寫您的 Discord ID 以及 storA 商城，然後拍照上傳明細" (one line) · `銀行代號`: "`822`" · `銀行帳號`: "`<redacted>`" |
| `chpytwtp-remit` | `郵局-匯款` | `取得訊息` | `chpytwtp-remit` | `郵局 - 匯款` | `https://i.meee.com.tw/YmI2qd9.png` | `請配合三方驗證`: (one-line text) · `銀行代號`: "`700`" · `銀行帳號`: "`<redacted>`" |

Bank account numbers are redacted here. The real values live in `XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/*.yaml`; the port ships example values only.

Common to every embed:
- `color_code: "0x9bd9d5"`, decoded with `java.awt.Color.decode`.
- Fields are not inline.
- No author, footer, timestamp, or content.
- No placeholders.

YAML block scalars (`|-`) keep the newline before `教學 …`. Field values include Markdown backticks.

**Behavior** (Event.kt:49-53 → SimpleCommand.kt:21-58). Every command does the same thing. The interaction has already been deferred as ephemeral by Core's InteractionLogger (Core: logger/InteractionLogger.kt:25-30).
1. Route only if `config.enabled` and `event.name` is one of the five names (Register.kt:9-15).
2. `event.hook.deleteOriginal().queue()`: delete the ephemeral "thinking" response, so the invoker sees no acknowledgement text.
3. `event.channel.sendMessage(creator.getCreateBuilder(<name>).build()).queue()`: post the embed **publicly** in the invocation channel. It is always rendered with the **default locale zh-TW** and the global substitutor, whatever the user's or guild's locale.
4. Steps 2 and 3 are independent and concurrent. If the send fails (for example, missing permissions in the channel or thread), the error is only logged and the invoker gets no feedback because the deferred response is already gone.

If auto-defer is disabled (`--no-auto-defer-interactions`), `deleteOriginal` waits for an acknowledgement that never comes, so the user sees "The application did not respond". The embed is still posted.

---

## 4. Components

None.

---

## 5. Events

| JDA event | Filter | Behavior |
|---|---|---|
| `SlashCommandInteractionEvent` | `config.enabled` and `event.name ∈ {cub-none-card, tsib-none-card, ctcb-none-card, ctcb-remit, chpytwtp-remit}` | §3 |

---

## 6. Configuration

`plugins/SimpleCommand/config.yaml` defaults to `enabled: false`.

| Key | Type | Default | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` (also the serializer default) | When false, no commands are registered and the handler is a no-op. It can be toggled at runtime through reload or the dashboard |

kaml runs in strict mode, so unknown keys fail the load. Core then exits, because it does not catch exceptions thrown by `load()`.

---

## 7. Localization and templates

- Locale: zh-TW only, used for both command localization and messages. Templates are always rendered in zh-TW (SimpleCommand.kt:26 and the other branches call `getCreateBuilder(key)` with the default locale).
- `register.yaml`: name and description for each of the 5 commands (schema `CmdFileSerializer`).
- `message/*.yaml`: five embed templates, loaded by the MessageCreator v2 class using the legacy `embeds` schema. They have no components, no model keys, and no placeholders.
- Files are exported to disk and are operator-editable. In practice this is how bank details get updated without a rebuild.

---

## 8. Persistence

None, apart from the exported `config.yaml` and `lang/**`.

---

## 9. External dependencies

- Gradle: none beyond Core.
- Thumbnail images are hot-linked from `i.meee.com.tw`, a third-party image host. Discord fetches them, not the bot.
- A YouTube tutorial link appears in field text.
- No credentials and no plugin dependencies.

---

## 10. Discord requirements

- Intents: none.
- Bot permissions in the invocation channel: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS. In a thread, it also needs SEND_MESSAGES_IN_THREADS.
- No rate-limit concerns beyond one message per invocation.

---

## 11. Concurrency

None to speak of. `deleteOriginal` and `sendMessage` run concurrently; `reload` swaps the creator reference without synchronization, which is benign.

---

## 12. Bugs, quirks, hard-coded values

**Probable issues:**
- **B1** No feedback on failure: the ephemeral is deleted before the send result is known.
- **B2** The five handler branches are copy-pasted (SimpleCommand.kt:22-57). The behavior is identical; `creator.getCreateBuilder(event.name)` would do.
- **B3** The "custom command" system is not data-driven. Adding a command needs Kotlin changes in Register.kt, CmdFileSerializer.kt, and SimpleCommand.kt.
- **Data sensitivity:** bank account numbers are hard-coded in default resources and shipped inside the jar.

**Behavior to preserve:**
- Admin-only by default member permissions.
- The ephemeral deferral is deleted.
- The embed is posted publicly in the invocation channel.
- zh-TW rendering.
- Exact embed contents, including the colour `#9BD9D5`.

---

## 13. Testability

Pure parts:
- the command-name → template-key mapping (identity);
- template YAML → embed dict, as a golden test per command (title, thumbnail, fields, colour);
- localization loading (Kotlin-property-path keys, zh-TW default).

Needs Discord doubles: the deferred interaction (`delete_original_response`) and channel send.

---

## 14. Porting assessment

**Difficulty: Low.**

**discord.py mapping:**
- Generate the five `app_commands.Command`s from a table: name → template key. Apply `@app_commands.default_permissions(administrator=True)` and register them as guild commands. Add zh-TW `name_localizations` via a Translator.
- Handler: emulate Core's auto-defer (`await interaction.response.defer(ephemeral=True, thinking=True)`), then `await interaction.delete_original_response()` and `await interaction.channel.send(embed=render("…"))`.
- Optionally make the command set data-driven from YAML. That would be a behavior change; make it an explicit decision.

**Risks:** minimal. Colour parsing (`0x9bd9d5`) and block-scalar newlines must be preserved, and command registration must match the localized names.
