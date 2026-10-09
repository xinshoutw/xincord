# BotInfo — porting inventory (branch `main`)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Plugin sources: `Plugins/BotInfo/src/main/kotlin/botinfo/` (abbreviated `bi/`). Core: `Core/src/main/kotlin/core/` (`core/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/BotInfo` |
| Kotlin files / LOC | 5 files / 134 physical lines (110 non-blank): `BotInfo.kt` (37), `Event.kt` (60), `command/CmdFileSerializer.kt` (10), `command/Register.kt` (19), `config/ConfigSerializer.kt` (8) |
| Build | `plugins { id("xs-plugin") }`; `version.patch=0` → `3.4.0-SNAPSHOT` |
| Purpose | Global `/bot-info` slash command that shows an embed with the number of guilds the bot is in and the summed member count of those guilds. |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`bi/Event.kt:13`) |
| Base class | `PluginEventConfigure<C>` (`core/plugin/PluginEvent.kt:53-74`) |
| Listener flag | `true` |
| Business object | `internal object BotInfo` (`bi/BotInfo.kt:10`) |

`info.yaml`: `author: ${author}` (→ `xinshoutw`), `name: ${name}` (→ `BotInfo`), `coreApi: ${coreApi}` (→ `3.4`), `version: ${version}` (→ `3.4.0-SNAPSHOT`), `main: "tw.xinshou.discord.plugin.botinfo.Event"`. Nothing else (no intents/cache flags/member cache policies/dependencies/description; component prefix defaults to `botinfo@`, unused).

## 2. Lifecycle

- `load()` (`bi/Event.kt:16-29`): `super.load()` exports missing `lang/` files to `plugins/BotInfo/lang/` and reads `plugins/BotInfo/config.yaml`. If disabled → WARN `BotInfo is disabled.` and return (localizer stays uninitialized; safe because `globalCommands()` checks `enabled` first). If enabled → builds `StringLocalizer<CmdFileSerializer>` (default `zh-TW`, file `register.yaml`).
- `BotInfo` object: lazily initialized on the first `/bot-info` (or first enabled reload); holds a v2 `MessageCreator` over `plugins/BotInfo/lang/*/message/` with default `zh-TW` (`bi/BotInfo.kt:11-14`).
- `reload()` (`bi/Event.kt:31-46`): re-export missing lang files, re-read config; if enabled rebuild localizer and `BotInfo.reload()` (new MessageCreator). Only called by the Web Dashboard; Core then re-uploads global + guild commands (`core/base/BotLoader.kt:133-159`).
- `unload()`: default. Background jobs: none. State: `localizer` (`lateinit var`), `messageCreator` (`var`). Side effect state: keys `member_counts` / `guild_counts` written into Core's global substitutor (§7).

## 3. Slash commands & context menus

One **global** command (`globalCommands()`, `bi/Event.kt:48-54`; `bi/command/Register.kt:14-19`); empty array when disabled. Registered via `jdaBot.updateCommands().addCommands(globalCommands)` at startup (`core/base/BotLoader.kt:103`) and after dashboard reloads (`BotLoader.kt:154`).

| Field | Value |
|---|---|
| name | `bot-info` |
| description (default) | `show about the bot data` |
| name_localizations | en-US `bot-info`; zh-TW `機器人資訊` |
| description_localizations | en-US `show about this Bot`; zh-TW `顯示有關機器人的資訊` |
| options | none |
| default_member_permissions | `DefaultMemberPermissions.ENABLED` (no restriction) |
| contexts / integration types | JDA defaults: contexts GUILD + BOT_DM; guild install |
| NSFW | false |

Localization source: `plugins/BotInfo/lang/<locale>/register.yaml` with YAML key `bot-info: {name, description}` mapped by `@SerialName("bot-info")` to property `botInfo` (`bi/command/CmdFileSerializer.kt:7-11`), looked up as `botInfo.name` / `botInfo.description` (`Register.kt:8-12`).

Behavior (`bi/Event.kt:56-60` → `bi/BotInfo.kt:23-37`):
1. Core `InteractionLogger` auto-defers ephemerally (default on) and logs `[CMD] …` (`core/logger/InteractionLogger.kt:25-30`).
2. Return if disabled; return if `event.fullCommandName != "bot-info"` (`core/util/GlobalUtil.kt:46-47`). `fullCommandName` is the base (unlocalized) name, so zh-TW users invoking `/機器人資訊` match.
3. `memberCounts = event.jda.guilds.sumOf { it.memberCount }` (sum of each guild's member_count; users in several guilds counted multiple times; bots included); `guild_counts = event.jda.guilds.size`.
4. Writes `member_counts` and `guild_counts` into `Placeholder.globalSubstitutor` (`bi/BotInfo.kt:26-27`).
5. Renders template `bot-info` in **`event.userLocale`** (user client locale, not guild locale) with the global substitutor and calls `event.hook.editOriginal(...)` (`bi/BotInfo.kt:29-36`).
   - The plugin never acknowledges the interaction itself ⇒ it depends on Core auto-defer. With `--no-auto-defer-interactions` the interaction is never acknowledged (user sees "The application did not respond").
   - Result is therefore **ephemeral**.
   - No error messages; no permission checks; works in guilds and in the bot's DMs.

## 4. Components

None.

## 5. Events

Only `SlashCommandInteractionEvent` (above).

## 6. Configuration

`plugins/BotInfo/config.yaml` (shipped `enabled: false`), schema `bi/config/ConfigSerializer.kt:5-8`, strict kaml:

| Key | Type | Default | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` | false ⇒ no command registered (`globalCommands()` returns `[]`), handler ignores events, localizer not built. |

## 7. Localization & templates

- Locales: `en-US`, `zh-TW`; default/fallback `zh-TW` (`bi/Event.kt:26`, `bi/BotInfo.kt:13`). Any user locale other than en-US/zh-TW (including en-GB) gets the zh-TW reply (whole-locale fallback, `core/builtin/messagecreator/v2/MessageCreator.kt:130-134`).
- Files: `lang/{en-US,zh-TW}/register.yaml` (command localization), `lang/{en-US,zh-TW}/message/bot-info.yaml` (reply).
- Template engine: Core MessageCreator **v2** delegating to v1 embed builder (same rules as described in WelcomeByeGuild.md §7: `%key%` placeholders with commons-text semantics, http-only URL filter, `Color.decode`).

`message/bot-info.yaml` (exact):

| Field | en-US | zh-TW |
|---|---|---|
| embeds[0].author.name | `Info Query` | `狀態查詢` |
| embeds[0].author.icon_url | `https://i.imgur.com/a7z4ch2.png` | same |
| embeds[0].title.text | `☛ ORDERLY BOT's INFORMATION` | `☛ 序之徒的資訊` |
| embeds[0].footer.text | `❖ ORDERLY SERVER ❖` | same |
| fields[0] | name `Server Counts`, value `%guild_counts%`, inline false | `伺服器總數` / `%guild_counts%` |
| fields[1] | name `Member Counts`, value `%member_counts%`, inline false | `成員總數` / `%member_counts%` |
| embeds[0].color_code | `#00FFFF` | same |

No `content` (empty string), no description, no timestamp.

Placeholders: `%guild_counts%`, `%member_counts%` (set by BotInfo into the global substitutor right before rendering); the global substitutor also always has `%bot_id%`, `%bot_name%` (`core/builtin/placeholder/Placeholder.kt:15-18`).

## 8. Persistence

None.

## 9. External dependencies

Gradle: `compileOnly(project(":Core"))` only. External URL in template: `https://i.imgur.com/a7z4ch2.png` (fetched by Discord clients, not by the bot). No credentials, no plugin dependencies.

## 10. Discord requirements

- No privileged intent strictly required; accurate live member counts rely on member add/remove updates, which need **GUILD_MEMBERS** (Core enables it always). `GUILDS` for the guild list.
- No bot permissions needed beyond responding to interactions (`applications.commands` scope).
- Not rate-limit sensitive (one interaction response).

## 11. Concurrency

`messageCreator` and `localizer` are plain non-volatile vars swapped by dashboard reloads (Ktor thread) while the JDA event thread reads them — benign. `Placeholder.globalSubstitutor` is an unsynchronized `HashMap` mutated from the event thread on each call.

## 12. Bugs, quirks, dead code, hard-coded values

Behavior to preserve:
- Ephemeral embed reply (via auto-defer) with guild count and summed member count.
- Locale chosen from the **user's** locale; unsupported locales → zh-TW.
- Global command usable in guilds and bot DMs, no permission restriction.
- zh-TW localized command name `機器人資訊`.

Probable bugs / smells:
1. Relies on Core auto-defer; breaks with `--no-auto-defer-interactions` (`bi/BotInfo.kt:29`).
2. Mutates the process-wide global substitutor (`bi/BotInfo.kt:26-27`): the keys leak to every plugin; per-user substitutors created afterwards copy a stale snapshot.
3. "Member Counts" double-counts users present in several guilds and includes bots (possibly intended; document).
4. Hard-coded branding in templates ("ORDERLY BOT", "ORDERLY SERVER", "序之徒") and imgur icon URL.
5. `Register.kt` default description `show about the bot data` differs from en-US localized text `show about this Bot` (cosmetic).

Dead code / TODOs: none.

## 13. Testability

Pure logic: `compute_stats(guilds) -> (guild_count, member_sum)` (treat `member_count=None` as 0); template rendering per locale (golden embed dicts for en-US and zh-TW, fallback for e.g. `ja` and `en-GB`); command metadata snapshot (name, localizations, no default permissions, contexts guild+DM).

Discord doubles: `Interaction` (locale, response.defer, edit_original_response/followup), bot with a list of fake guilds having `member_count`.

## 14. Porting assessment

Difficulty: **Low**.

discord.py mapping: global `@app_commands.command(name="bot-info", description="show about the bot data")` with `@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)` and `@app_commands.allowed_installs(guilds=True, users=False)` to match JDA defaults; localizations via the shared `app_commands.Translator`; `await interaction.response.defer(ephemeral=True)` then `await interaction.edit_original_response(embed=…)` (or `response.send_message(..., ephemeral=True)` directly); stats from `bot.guilds` / `guild.member_count`. Pass counts as local render context instead of mutating a global placeholder map.

Risks: minimal — output parity of embed fields and the locale fallback rule.
