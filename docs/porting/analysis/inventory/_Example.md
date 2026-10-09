# _Example — porting inventory (branch `main`)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Plugin sources: `Plugins/_Example/src/main/kotlin/_example/` (abbreviated `ex/`). Core: `Core/src/main/kotlin/core/` (`core/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/_Example` |
| Kotlin files / LOC | 5 files / 171 physical lines (143 non-blank): `_Example.kt` (44), `Event.kt` (62), `command/CmdFileSerializer.kt` (21), `command/Register.kt` (32), `config/ConfigSerializer.kt` (12) |
| Build | `plugins { id("xs-plugin") }`; `version.patch=0` → `3.4.0-SNAPSHOT`. Included in `settings.gradle.kts:21-22`, so it is built and shipped in release BotPacks (disabled by default). |
| Purpose | Reference/template plugin demonstrating the plugin contract: config with `enabled`, localized guild slash command with two options, MessageCreator v2 embed reply with custom placeholders. No real functionality. Last change: `6291f39 fix(_Example): update MessageCreator import to v2`. |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`ex/Event.kt:14`) |
| Base class | `PluginEventConfigure<C>` (`core/plugin/PluginEvent.kt:53-74`) |
| Listener flag | `true` |
| Business object | `internal object _Example` (`ex/_Example.kt:11`) |

`info.yaml`: `author: ${author}` (→ `xinshoutw`), `name: ${name}` (→ `_Example`), `coreApi: ${coreApi}` (→ `3.4`), `version: ${version}` (→ `3.4.0-SNAPSHOT`), `main: "tw.xinshou.discord.plugin._example.Event"`. No intents/cache flags/member cache policies/dependencies/description/component_prefix (derived `_example@`, unused).

## 2. Lifecycle

Same pattern as BotInfo:
- `load()` (`ex/Event.kt:17-30`): export missing `lang/`, read config; disabled ⇒ WARN `_Example is disabled.`; enabled ⇒ build `StringLocalizer<CmdFileSerializer>` (default `zh-TW`).
- `_Example` object lazily builds a v2 `MessageCreator` (default `zh-TW`) on first command (`ex/_Example.kt:12-15`).
- `reload()` (`ex/Event.kt:32-47`): re-read config, rebuild localizer and `_Example.reload()` when enabled (dashboard-only path).
- `unload()` default; no background jobs; state: `localizer` (lateinit), `messageCreator` (var).

## 3. Slash commands & context menus

One **guild** command (`ex/Event.kt:49-55`, `ex/command/Register.kt:21-33`), registered per guild by Core; empty when disabled.

| Field | Value |
|---|---|
| name | `example-command` (localized: en-US `example-command`, zh-TW `範例指令`) |
| description | default `this is an example command`; en-US `This is an example command`; zh-TW `這是一個範例指令` |
| default_member_permissions | not set (everyone) |
| option 1 | `option1`, type STRING, **required**; default description `this is an example option`; localized names en-US `option1` / zh-TW `選項1`; descriptions en-US `This is a required option` / zh-TW `這是一個必填選項`; no choices/min/max/autocomplete |
| option 2 | `option2`, type **INTEGER**, optional; default description `this is an example option`; localized names `option2` / `選項2`; descriptions `This is an optional option` / `這是一個可選選項` |

Localization file schema `lang/<locale>/register.yaml`: `example{name, description, options{option1{name,description}, option2{name,description}}}` (`ex/command/CmdFileSerializer.kt:6-22`), keys `example.name`, `example.options.option1.name`, … (`Register.kt:9-19`).

Behavior (`ex/Event.kt:57-61` → `ex/_Example.kt:24-42`):
1. Core auto-defers ephemerally and logs (`core/logger/InteractionLogger.kt:25-30`).
2. Return if disabled or `event.fullCommandName != "example-command"`.
3. `option1 = getOption("option1")!!.asString`; `option2 = getOption("option2")?.asString` (integer rendered as decimal string) or `"none"`.
4. Puts `_Example@option1`, `_Example@option2` into the caller's cached Core substitutor `Placeholder.get(event)` (`ex/_Example.kt:28-31`).
5. Renders template `example` in **`event.userLocale`** and `event.hook.editOriginal(...)` (relies on Core auto-defer ⇒ ephemeral; breaks with `--no-auto-defer-interactions`).

Failure modes (no user-facing error messages exist):
- Invoked from a non-`TextChannel` (thread, voice chat, announcement channel, forum post): `Placeholder.get(event)` throws at `event.guildChannel.asTextChannel()` (`core/builtin/placeholder/Placeholder.kt:75`) ⇒ no reply.
- `option1` longer than 1024 chars (Discord allows up to 6000) ⇒ embed field value limit ⇒ JDA `EmbedBuilder.addField` throws ⇒ no reply.
- `option1` containing `%_Example@option1%` (self reference) ⇒ commons-text cyclic-substitution `IllegalStateException` ⇒ no reply; other `%key%` tokens in user input are expanded (e.g. `%bot_name%`).

## 4. Components

None.

## 5. Events

Only `SlashCommandInteractionEvent`.

## 6. Configuration

`plugins/_Example/config.yaml` (`ex/config/ConfigSerializer.kt:6-12`), strict kaml:

| Key | Type | Default | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` | Master switch (no command registered when false). |
| `example_key` | String | **required, no default** (shipped `"example_value"`) | Never read anywhere — but removing it makes config decoding fail and aborts bot startup. |

## 7. Localization & templates

- Locales `en-US`, `zh-TW`; fallback `zh-TW`; user locale selects the reply language.
- Files: `lang/{en-US,zh-TW}/register.yaml`, `lang/{en-US,zh-TW}/message/example.yaml`.
- `message/example.yaml` (v2 MessageCreator → v1 embed builder):

| Field | en-US | zh-TW |
|---|---|---|
| author.name | `Example Reply` (no icon) | `範例回覆` |
| title.text | `This is an example reply.` | `這是一個範例回覆` |
| footer.text | `❖ ORDERLY SERVER ❖` | same |
| fields | `Option 1` → `%_Example@option1%`; `Option 2` → `%_Example@option2%` (not inline) | `選項 1` / `選項 2` |
| color_code | `#00FFFF` | same |

- Placeholders defined: `%_Example@option1%` (raw string option), `%_Example@option2%` (integer as string or `none`). Also available: Core command placeholders (`user_*`, `member_*`, `command_*`, `channel_*`, `language`, `bot_*`).

## 8. Persistence

None.

## 9. External dependencies

`compileOnly(project(":Core"))` only. No HTTP, credentials, or plugin dependencies.

## 10. Discord requirements

No privileged intents, no special permissions (`applications.commands` scope only). Not rate-limit sensitive.

## 11. Concurrency

Plain `var`s swapped on dashboard reload; per-user substitutor cache mutation (unsynchronized `HashMap` in Core). Single JDA event thread in practice.

## 12. Bugs, quirks, dead code, hard-coded values

Behavior to preserve (if ported as a sample): ephemeral embed echoing the two options; `none` when option2 omitted; user-locale selection with zh-TW fallback.

Probable bugs: dependence on auto-defer; non-TextChannel crash; no length guard for embed field; recursive substitution of user input; `example_key` required but unused (`ex/config/ConfigSerializer.kt:10-11`); `_Example@…` keys persist in the user's cached substitutor after the command (leak to other plugins' renders).

Hard-coded: default locale zh-TW, footer branding "ORDERLY SERVER".

## 13. Testability

Pure: `build_placeholders(option1, option2) -> {"_Example@option1": option1, "_Example@option2": str(option2) if not None else "none"}`; template render goldens; command metadata snapshot (option types STRING/INTEGER, required flags, localizations).

## 14. Porting assessment

Difficulty: **Low** (≈30 lines in Python). Decide whether to port it at all: it is the canonical "how to write a plugin" sample, so the most useful port is a Python template Cog demonstrating the new plugin API (config model with `enabled`, localized command via Translator, `option1: str`, `option2: int | None = None`, ephemeral embed via the shared template renderer). Risks: none beyond shared template/placeholder parity.
