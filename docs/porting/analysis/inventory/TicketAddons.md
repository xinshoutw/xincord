# TicketAddons: porting inventory (branch `main`)

Repo: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. JDA 6.4.1, kaml 0.104.0, coreApi `3.4`.
Line references are relative to `Plugins/TicketAddons/src/main/kotlin/addons/ticket/` unless prefixed with `Core:` (= `Core/src/main/kotlin/core/`) or `res:` (= `Plugins/TicketAddons/src/main/resources/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/TicketAddons` |
| Kotlin files / LOC | 3 files, 95 physical lines (79 non-blank): `TicketAddons.kt` 39, `Event.kt` 30, `config/ConfigSerializer.kt` 26 |
| Resources | `config.yaml`, `info.yaml`, `lang/zh-TW/message/not-online.yaml` (zh-TW only; no `register.yaml`) |
| Tests | none |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:7). `listener = true` |
| Build | `plugins { id("xs-plugin") }` (Core compileOnly only). `version.patch=0` → `3.4.0-SNAPSHOT` |

**Purpose.** When a channel whose name starts with a configured prefix is created, the bot checks whether one configured user (the shop owner) is OFFLINE. If so, after a delay it posts a fixed "the owner is not online, please wait" embed into the new channel. It was written for a specific server ("白月代購", footer "❖ ORDERLY SERVER ❖").

**Relationship to Ticket: none in code or metadata.**
- `info.yaml` declares no `depend_plugins`/`soft_depend_plugins`; neither plugin imports the other; they share no data or component ids.
- The only coupling is the naming convention: default prefixes are `客服單-` and `ticket-`. The `Ticket` plugin on `main` names ticket channels after the **user's username** (`Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:281`), so TicketAddons does **not** fire for Ticket-created channels unless a username happens to start with a prefix or the prefixes are changed.
- Git history: TicketAddons was added on 2024-10-01 (commit `9ecf738`), before the Ticket plugin (2025-01-09, `c5ce134`). It targeted another ticket system's channel names.
- The README groups them as "Ticket & TicketAddons", which is misleading.

**info.yaml** (`res:info.yaml`, after Gradle expand):
```yaml
author: xinshoutw
name: TicketAddons
coreApi: "3.4"
version: 3.4.0-SNAPSHOT
main: "tw.xinshou.discord.plugin.addons.ticket.Event"
require_cache_flags: ["ONLINE_STATUS"]
require_intents: ["GUILD_PRESENCES"]
```
- No `component_prefix`; Core derives `ticketaddons@`, which is unused (Core: base/PluginLoader.kt:277-285).
- No `require_member_cache_policies`, no dependencies, no `description`.

---

## 2. Lifecycle

- **load()** (Event.kt:8-14):
  - `super.load()` exports `lang/` to `plugins/TicketAddons/lang/` (non-destructive) and reads (exporting if missing) `plugins/TicketAddons/config.yaml`. Decoding runs the `ConfigSerializer.init` validation **even when disabled** (§6).
  - If disabled, logs WARN `TicketAddons is disabled.`. There is nothing else to initialize.
- **reload()** (Event.kt:16-24): re-reads config. If disabled, WARN and return. Otherwise `TicketAddons.reload()` rebuilds the `MessageCreator` from disk (TicketAddons.kt:17-22).
- **unload()**: not overridden.
- **guildCommands()/globalCommands()**: not overridden (no commands).
- **Lazy initialization:** the `TicketAddons` object (and its `MessageCreator(plugins/TicketAddons, zh-TW)` with no `ComponentIdManager`) initializes on the first matching `ChannelCreateEvent` or on reload.
- **Background jobs:** none persistent. Each trigger schedules **one** delayed send with `RestAction.queueAfter(delay_millis, MILLISECONDS)` on JDA's rate-limit scheduler (TicketAddons.kt:32-37). Nothing cancels it, even if the channel is deleted first; the send then fails and is logged.
- **In-memory state:** only the `MessageCreator`.

---

## 3. Slash commands and context menus

None.

---

## 4. Components

None. The plugin sends no buttons, selects, or modals.

---

## 5. Events

`ChannelCreateEvent`. `Event.onChannelCreate` returns if `config.enabled` is false (Event.kt:26-29), then `TicketAddons.onChannelCreate` (TicketAddons.kt:24-39) runs:

1. Guild filter, **buggy**: `if (!event.isFromGuild && event.guild.id != config.guildId) return`. `ChannelCreateEvent` is always from a guild, so the condition is always false and **`guild_id` is never enforced**. The handler runs in every guild the bot is in (bug B1).
2. Prefix filter: return unless `config.prefix.any { event.channel.name.startsWith(it) }`. The match is case-sensitive. Discord lowercases text channel names, so ASCII prefixes must be lowercase to match. It applies to **all channel types** JDA reports through ChannelCreateEvent, including voice, category, forum, and threads.
3. `event.guild.retrieveMemberById(config.userId)` returns the cached member if present, otherwise a REST fetch. On failure (for example, the user is not in that guild), nothing happens beyond a logged error.
4. Inside the callback: if `member.onlineStatus != OnlineStatus.OFFLINE`, return.
   - The message is sent only when the user is OFFLINE. Invisible users also appear OFFLINE to bots.
   - `UNKNOWN` status counts as not offline, so no message is sent.
5. Build `not-online` (zh-TW forced, global substitutor), then `event.channel.asTextChannel().sendMessage(…).queueAfter(delay_millis ms)`.
   - `asTextChannel()` throws `IllegalStateException` for non-text channels, inside the JDA callback, so it is only logged (bug B2).

**Presence accuracy depends on the member cache.** The plugin requests GUILD_PRESENCES and the ONLINE_STATUS cache flag, but no member cache policy. Core's default policy caches only `OWNER` and `VOICE` members, plus whatever other plugins add (Core: base/PluginLoader.kt:33; plugin/yaml/InfoSerializer.kt:42-66). A REST-fetched member carries no presence, so JDA reports `OFFLINE` **(unverified, but JDA's member default is OFFLINE)**. Unless the configured user is the guild owner, sits in voice, or another plugin widens the policy, the plugin very likely **always** considers the user offline and always posts.

---

## 6. Configuration

`plugins/TicketAddons/config.yaml` (defaults from `res:config.yaml`):

| Key | Type | Required | Default (resource) | Validation / use |
|---|---|---|---|---|
| `enabled` | Boolean | no (serializer default `false`) | `false` | false: handler is a no-op |
| `guild_id` | String | **yes** | `858672865355890708` (unquoted YAML number, decoded as String) | `require(isNotBlank)`. Intended to limit the handler to one guild, but ineffective (B1) |
| `user_id` | String | **yes** | `270062130470846465` | `require(isNotBlank)`. Member whose presence is checked |
| `prefix` | List<String> | **yes** | `["客服單-", "ticket-"]` | `require(isNotEmpty)`. Channel-name prefixes |
| `delay_millis` | Long | **yes** | `2000` | `require(> 0)`. Delay before posting |

- Validation lives in the data class `init` (config/ConfigSerializer.kt:20-25). It runs at decode time **regardless of `enabled`**, so an invalid config fails load even for a disabled plugin.
- kaml strict mode: unknown keys also fail.
- Core does not catch load exceptions, so a failure terminates the application (Core: base/PluginLoader.kt:145-155, Main.kt:21-31).
- Enabled-flag semantics: runtime-togglable through dashboard/reload, like the other plugins.

---

## 7. Localization and templates

- Locale: `zh-TW` only. The template is always rendered with `DiscordLocale.CHINESE_TAIWAN` (TicketAddons.kt:33-36), never the user's or guild's locale.
- `lang/zh-TW/message/not-online.yaml`, loaded by the MessageCreator v2 class with the legacy schema and **no placeholders**:
  ```yaml
  embeds:
    - author: { name: "白月代購" }
      title:
        text: "營業時間參考請看 <#1036632849043955753> \n如果老闆沒有馬上回你代表人不在，請等老闆回覆訊息，並且先說出需要購買的商品還有 <#1035435839125196881>"
      footer: { text: "❖ ORDERLY SERVER ❖" }
  ```
- Rendered message: empty content plus one embed.
  - Author name `白月代購`, no URL or icon.
  - The title contains a real newline.
  - The channel mentions are **not rendered inside embed titles**; Discord shows them as raw `<#…>` text.
  - Footer `❖ ORDERLY SERVER ❖`. No colour, no timestamp.
- The title is about 90 characters, within the 256 limit.
- The file is exported to disk, so operators can edit it.
- No command localizations (no commands).

---

## 8. Persistence

None. No Mongo, JSON, SQLite, or other files besides the exported `config.yaml` and `lang/**`.

---

## 9. External dependencies

- Gradle: none beyond Core.
- HTTP: Discord only. No credentials.
- Plugin dependencies: none, hard or soft (see §1).

---

## 10. Discord requirements

- **Privileged intent: `GUILD_PRESENCES`**, declared. Core also always enables `GUILD_MEMBERS` (privileged).
- Cache flag: `ONLINE_STATUS`. Core disables it by default and re-enables it when a plugin requests it, because `enableCache` runs after `disableCache` (Core: base/BotLoader.kt:62-75).
- Member cache: not declared. Presence accuracy is limited as described in §5.
- Bot permissions in the new channel: VIEW_CHANNEL, SEND_MESSAGES, EMBED_LINKS.
- Rate limits: one member fetch plus one delayed message per matching channel. Mass channel creation causes bursts.

---

## 11. Concurrency

- The handler runs on the JDA event thread. The member fetch callback and the delayed send run on JDA callback and scheduler threads.
- No shared mutable state besides the `MessageCreator` reference, which reload swaps without synchronization (benign).
- Nothing deduplicates or cancels a send: one message per create event, even if the channel is deleted before the delay elapses.

---

## 12. Bugs, quirks, hard-coded values

**Probable bugs to fix:**
- **B1** `!event.isFromGuild && event.guild.id != config.guildId` (TicketAddons.kt:25) should be `event.guild.id != config.guildId`. Today the guild filter is a no-op, so posts can appear in other guilds where the configured user is a member and offline.
- **B2** `event.channel.asTextChannel()` (TicketAddons.kt:32) throws for non-text channels with a matching name, including threads, forum, and voice channels. It is caught only by JDA's callback logging.
- **B3** Presence check against an uncached member is likely always `OFFLINE` (§5).
- **B4** Config validation runs while disabled, so required fields must be present even when the plugin is off (ConfigSerializer.kt:20-25).

**Behavior to preserve (or decide):**
- Fire only on name-prefix match; send only when OFFLINE; send after `delay_millis`; template rendered with fixed zh-TW.
- Text: business-specific embed (author `白月代購`, channel ids `1036632849043955753` and `1035435839125196881`, footer `❖ ORDERLY SERVER ❖`).

**Hard-coded values:**
- default `guild_id` `858672865355890708` and `user_id` `270062130470846465` (in `config.yaml`);
- default prefixes `客服單-` and `ticket-`;
- forced locale zh-TW.

---

## 13. Testability

Pure functions to extract:
- `should_notify(channel_name, channel_guild_id, cfg) -> bool`, covering prefix matching and the fixed guild filter;
- `is_offline(status)` (OFFLINE → true; ONLINE, IDLE, DND, UNKNOWN → false);
- config validation (the four `require`s, defaults, strict unknown-key rejection);
- template render → embed dict (golden test).

Needs Discord doubles: the channel-create event, member lookup (cache vs. fetch), presence status, delayed send. Use an injectable clock or sleep so the delay can be asserted.

---

## 14. Porting assessment

**Difficulty: Low.** One listener, no state, no commands. The only subtleties are presence and member-cache semantics and the guild-filter bug decision.

**discord.py mapping:**
- `@commands.Cog.listener() async def on_guild_channel_create(self, channel)`. Thread creation arrives through `on_thread_create`; JDA's ChannelCreateEvent also covers threads, so decide whether to keep that.
- Require `Intents.presences` and `Intents.members`. Get the member with `guild.get_member(uid)` (cached, has `.status`), falling back to `await guild.fetch_member(uid)` (no presence → `Status.offline`, which matches JDA's behavior).
- Delay with `asyncio.create_task(self._send_later(channel, delay))` and `await asyncio.sleep(delay_ms / 1000)`. Guard `isinstance(channel, discord.TextChannel)`.
- Load `not-online.yaml` through the shared template renderer. Force locale zh-TW.

**Risks:**
- Presence accuracy requires member caching; in discord.py, member cache plus presences means chunking and memory cost.
- Fixing B1 changes behavior in multi-guild deployments.
- Thread and non-text handling.
