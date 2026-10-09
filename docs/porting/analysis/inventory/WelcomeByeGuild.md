# WelcomeByeGuild — porting inventory (branch `main`)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Paths below are relative to it.
Plugin sources: `Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/` (abbreviated `wbg/`).
Core sources: `Core/src/main/kotlin/core/` (abbreviated `core/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/WelcomeByeGuild` |
| Kotlin files / LOC | 7 files / 633 physical lines (537 non-blank) |
| Files | `Event.kt` (81), `WelcomeByeGuild.kt` (304), `WelcomeByeGuildMessageKeys.kt` (20), `WelcomeByeGuildSubstitutorFactory.kt` (113), `command/CmdFileSerializer.kt` (32), `command/Register.kt` (75), `config/ConfigSerializer.kt` (8) |
| Build | `build.gradle.kts` = `plugins { id("xs-plugin") }` (compileOnly Core, plain jar to `DevServer/plugins/WelcomeByeGuild-<ver>.jar`); `gradle.properties`: `version.patch=0` → version `3.4.0-SNAPSHOT` (root `version.major=3`, `version.minor=4`, `version.snapshot=true`; CI release sets snapshot=false) |
| Purpose | Per-guild "welcome" (member join) and "bye" (member leave) messages posted as embeds into an admin-bound text channel; 4 admin slash commands to bind/unbind the channels. |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`wbg/Event.kt:18`) |
| Base class | `PluginEventConfigure<C>` (`core/plugin/PluginEvent.kt:53-74`) → `PluginEvent` → JDA `ListenerAdapter` |
| Listener flag | `true` → registered as a JDA event listener (`core/base/PluginLoader.kt:151`, `core/base/BotLoader.kt:100`) |
| Business object | `internal object WelcomeByeGuild` (`wbg/WelcomeByeGuild.kt:30`) |

`src/main/resources/info.yaml` (Gradle `expand()` fills `${...}` from `build-logic/convention/src/main/kotlin/xs-jvm-conventions.gradle.kts:65-81`):

| Field | Value |
|---|---|
| `author` | `${author}` → `xinshoutw` |
| `name` | `${name}` → `WelcomeByeGuild` (Gradle project name) |
| `coreApi` | `${coreApi}` → `3.4` (must equal Core's `Version.CORE_API`, `core/base/PluginLoader.kt:222-232`) |
| `version` | `${version}` → `3.4.0-SNAPSHOT` (validated by regex `^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$`, `PluginLoader.kt:29`) |
| `main` | `tw.xinshou.discord.plugin.welcomebyeguild.Event` |
| `component_prefix` | `"welcome-bye@"` — declared but **no components exist** (dead) |
| `prefix` | not set → defaults to plugin name |
| `description` | not set (dashboard shows "No description found in info.yaml.") |
| `require_intents` / `require_cache_flags` / `require_member_cache_policies` | none (relies on Core's always-on `GUILD_MEMBERS`, `core/base/BotLoader.kt:68-72`) |
| `depend_plugins` / `soft_depend_plugins` / `depend_jars` / `soft_depend_jars` | none |

## 2. Lifecycle

Order inside Core: `PluginLoader.run()` calls `load()` for every plugin (reverse dependency order), then `rebuildCommands()` calls `guildCommands()`/`globalCommands()` (`core/base/PluginLoader.kt:145-180`). `plugin.load()` is **not wrapped in try/catch** — any exception aborts the whole bot startup (`PluginLoader.kt:147-152`, `BotLoader.kt:85`).

- `load()` (`wbg/Event.kt:27-37`):
  1. `super.load()` → `PluginEvent.load()` exports bundled `lang/` into `plugins/WelcomeByeGuild/lang/` **only for files that do not exist yet** (overwrite only with CLI `-Flang/--force-renew-lang-resources`) (`core/plugin/PluginEvent.kt:23-29`, `core/util/FileGetter.kt:61-103`, `core/util/Arguments.kt:12-17`); then `PluginEventConfigure.load()` reads `plugins/WelcomeByeGuild/config.yaml` (exported from jar if missing) with strict kaml decoding (`PluginEvent.kt:59-65`).
  2. Creates the command `StringLocalizer` (default locale `zh-TW`) and stores it in `localizerRef` — **even when disabled** (`wbg/Event.kt:29`).
  3. If `!config.enabled`: log WARN `WelcomeByeGuild is disabled.` and return.
  4. Else `WelcomeByeGuild.load()` → first access initializes the object: builds `JsonGuildFileManager` (reads **all** `data/*.json` eagerly) and a v2 `MessageCreator`; `load()` then builds a second `MessageCreator` and swaps it into the `AtomicReference` (`wbg/WelcomeByeGuild.kt:38-49`). Double construction is harmless.
- `reload()` (`wbg/Event.kt:39-49`): `super.reload()` (re-export missing lang files, re-read config.yaml), recreate localizer, if enabled `WelcomeByeGuild.reload()` (new `MessageCreator` → picks up edited lang/message YAML). Data files are **not** re-read on reload (manager is created once per class-loader lifetime).
  - Who calls `reload()`: only the Web Dashboard (`BotLoader.reloadPluginStrict`, `core/base/BotLoader.kt:133-138`, called from `core/dashboard/CoreDashboardBackend.kt:214`). The console `reload` command does a full stop/start with fresh class loaders → `load()` again, not `reload()` (`core/cli/JLineManager.kt:68-70`, `BotLoader.kt:112-123`). `BotLoader.reloadAllStrict()` is dead code.
  - After a plugin reload Core re-uploads **all** global commands and the guild command set to **every** guild (`BotLoader.kt:150-159`).
- `unload()`: not overridden (default logs only).
- Background jobs: none (no schedulers/timers/coroutines/executors).
- In-memory state: `localizerRef: AtomicReference<StringLocalizer?>` (`Event.kt:25`); `messageCreatorRef: AtomicReference<MessageCreator>` (`WelcomeByeGuild.kt:45`); `jsonGuildManager.mapper: MutableMap<Long, JsonFileManager<GuildSetting>>` holding every guild's settings (`core/json/JsonGuildFileManager.kt:12`). Indirectly: Core `Placeholder` per-user substitutor caches (see §11/§12).

## 3. Slash commands & context menus

All four are **guild commands** (returned from `guildCommands()`, `wbg/Event.kt:51-59`; built in `wbg/command/Register.kt:43-75`). Core bulk-overwrites the guild command list for every guild at startup (`core/base/ListenerManager.kt:18-24`, only if the combined guild list is non-empty), on `GuildJoinEvent` (`ListenerManager.kt:32-36`) and after dashboard reloads (`BotLoader.kt:150-159`). When `enabled: false`, `guildCommands()` returns an empty array (commands removed on the next overwrite).

No subcommands/groups, no context menus, no autocomplete, no choices, no min/max, NSFW=false. `default_member_permissions = ADMINISTRATOR (8)` on all four (`Register.kt:41`).

Command metadata (name/description localizations come from `plugins/WelcomeByeGuild/lang/<locale>/register.yaml` via `StringLocalizer`; only locales that have a file are emitted — `en-US`, `zh-TW`):

| Command | Default (unlocalized) description | en-US description | zh-TW description | Option |
|---|---|---|---|---|
| `welcome-channel-bind` | `bind channel for welcome message` | `Bind the channel for welcome messages` | `綁定成員加入歡迎訊息頻道` | `channel` |
| `welcome-channel-unbind` | `unbind welcome channel` | `Unbind the channel for welcome messages` | `解除綁定成員加入歡迎訊息頻道` | — |
| `bye-channel-bind` | `bind channel for bye message` | `Bind the channel for leave messages` | `綁定成員離開難過訊息頻道` | `channel` |
| `bye-channel-unbind` | `unbind bye channel` | `Unbind the channel for leave messages` | `解除綁定成員離開難過訊息頻道` | — |

Name localizations: en-US and zh-TW names are identical to the base names.

Option `channel` (bind commands only, `Register.kt:49-52`, `:65-68`): type `CHANNEL`, `required=false`, `channel_types=[TEXT]` (GUILD_TEXT=0 only; announcement/news, threads, voice, forum excluded). Default description `welcome output channel` / `bye output channel`; localized name `channel` (both locales); localized description en-US `Optional. Uses the current text channel if omitted`, zh-TW `可選，不填則使用當前文字頻道`.

Localization key mechanics: `StringLocalizer` flattens the decoded `CmdFileSerializer` by **Kotlin property names** (camelCase), not YAML keys (`core/localizations/StringLocalizer.kt:69-97`), so YAML `welcome_channel_bind.options.channel.name` is looked up as `welcomeChannelBind.options.channel.name` (`Register.kt:19-39`). YAML schema per locale (`CmdFileSerializer.kt:7-32`): `welcome_channel_bind{name,description,options{channel{name,description}}}`, `welcome_channel_unbind{name,description}`, `bye_channel_bind{...same as welcome bind...}`, `bye_channel_unbind{name,description}` — all required. The default locale (`zh-TW`) file must exist or `StringLocalizer` throws (`StringLocalizer.kt:66`).

### Behavior (common path, all four)

1. Core `InteractionLogger` (registered before plugin listeners, `BotLoader.kt:89` vs `:100`; JDA's default event manager invokes listeners in registration order on one thread) auto-defers **ephemerally** if CLI auto-defer is on (default `true`, `--no-auto-defer-interactions` disables) and logs `[CMD] <username>: <commandString>` (`core/logger/InteractionLogger.kt:25-30`, `core/util/Arguments.kt:34-41`).
2. `Event.onSlashCommandInteraction` (`Event.kt:61-65`): return silently if `!config.enabled`; return if `event.name ∉ {welcome-channel-bind, welcome-channel-unbind, bye-channel-bind, bye-channel-unbind}` (`core/util/GlobalUtil.kt:49-50`, `Register.kt:12-17`). (Every plugin receives every slash event; routing is by name filter.)
3. `WelcomeByeGuild.onSlashCommandInteraction` (`WelcomeByeGuild.kt:59-76`):
   - `event.guild == null` → reply `guild-only` (practically unreachable for guild commands).
   - `event.member?.hasPermission(ADMINISTRATOR) != true` → reply `no-permission` (`WelcomeByeGuild.kt:65-68`, `:272-274`). Guild-level permission (owner ⇒ true). Users granted the command through Server Settings → Integrations but lacking Administrator still get this message.
   - Dispatch on `event.name`.
4. `reply()` (`WelcomeByeGuild.kt:286-303`): locale = `event.guild.locale` (guild preferred locale; falls back to `event.userLocale` only if no guild). Builds `MessageEditData` from the template. If already acknowledged → `event.hook.editOriginal(data)`; else `deferReply(true)` then `hook.editOriginal(data)`. **Always ephemeral**, always "defer + edit original". No failure callbacks.

### `/welcome-channel-bind [channel]` (`WelcomeByeGuild.kt:120-161`)
1. Target = `channel` option if given, accepted only if `type == TEXT`; otherwise (no option) the invoking channel if its type is `TEXT`; else null (`:276-284`).
2. Null → reply `invalid-channel`. Side effect: `jsonGuildManager[guildId]` creates and writes `data/<guildId>.json` (`{"welcomeChannelId":0,"byeChannelId":0}`) if absent (`:122`; `core/json/JsonGuildFileManager.kt:21-28`; `core/json/JsonFileManager.kt:29-39`).
3. If `welcomeChannelId == target.id` → reply `welcome-bind-already` (placeholders: selected channel).
4. Else set `welcomeChannelId = target.id`, `save()` synchronously, reply `welcome-bind-success`.

### `/welcome-channel-unbind` (`:163-194`)
1. Get-or-create guild setting (creates file if absent).
2. `welcomeChannelId == 0` → reply `welcome-unbind-empty`.
3. Else remember old id, set 0, `save()`, reply `welcome-unbind-success` with `%wbg@old_channel_mention%` = `<#oldId>` (rendered even if the channel was deleted).

### `/bye-channel-bind [channel]` (`:196-237`) and `/bye-channel-unbind` (`:239-270`)
Identical to the welcome variants, operating on `byeChannelId` with `bye-bind-already`, `bye-bind-success`, `bye-unbind-empty`, `bye-unbind-success`. The same channel may be bound for both welcome and bye.

### User-visible reply texts (exact; `plugins/WelcomeByeGuild/lang/<locale>/message/*.yaml`, all `content:` only)

| Key | en-US | zh-TW |
|---|---|---|
| `guild-only` | `This command can only be used in a guild.` | `此指令只能在伺服器內使用。` |
| `no-permission` | `You need administrator permission to use this command.` | `你需要管理員權限才能使用此指令。` |
| `invalid-channel` | ``Unable to read a valid text channel. Please choose the `channel` option again.`` | ``無法讀取文字頻道，請重新選擇 `channel` 參數。`` |
| `welcome-bind-already` | `Welcome channel is already %wbg@channel_mention%; no update is needed.` | `歡迎頻道已經是 %wbg@channel_mention%，不需重複綁定。` |
| `welcome-bind-success` | `Welcome channel has been bound to %wbg@channel_mention% (%wbg@channel_name%).` | `已綁定歡迎頻道到 %wbg@channel_mention%（%wbg@channel_name%）。` |
| `welcome-unbind-empty` | `No welcome channel is currently bound.` | `目前尚未綁定歡迎頻道。` |
| `welcome-unbind-success` | `Welcome channel unbound successfully (previous: %wbg@old_channel_mention%).` | `已解除歡迎頻道綁定（原頻道：%wbg@old_channel_mention%）。` |
| `bye-bind-already` | `Leave channel is already %wbg@channel_mention%; no update is needed.` | `離開訊息頻道已經是 %wbg@channel_mention%，不需重複綁定。` |
| `bye-bind-success` | `Leave channel has been bound to %wbg@channel_mention% (%wbg@channel_name%).` | `已綁定離開訊息頻道到 %wbg@channel_mention%（%wbg@channel_name%）。` |
| `bye-unbind-empty` | `No leave channel is currently bound.` | `目前尚未綁定離開訊息頻道。` |
| `bye-unbind-success` | `Leave channel unbound successfully (previous: %wbg@old_channel_mention%).` | `已解除離開訊息頻道綁定（原頻道：%wbg@old_channel_mention%）。` |

### Failure mode that must not be replicated
Any command path that builds a substitutor through `Placeholder.get(event)` (the `no-permission` path and every `forCommand(...)` call, `WelcomeByeGuildSubstitutorFactory.kt:22`) calls `event.guildChannel.asTextChannel()` (`core/builtin/placeholder/Placeholder.kt:75`), which throws `IllegalStateException` when the command is invoked from a non-`TextChannel` (thread, voice text chat, stage, announcement channel, forum post). Result: no reply (ephemeral "thinking…" until the token expires). For bind/unbind the setting is **saved before** the reply substitutor is built, so the change persists silently (e.g. `/welcome-channel-bind channel:#general` run inside a thread).

Consequence: the `invalid-channel` reply can never actually be delivered. The `channel` option is restricted to GUILD_TEXT by Discord, so the only way to reach `invalid-channel` is "no option + invoked from a non-text channel", and exactly that case crashes in `Placeholder.get(event)` before the reply is sent. Acceptance criteria should specify the *intended* behavior (ephemeral `invalid-channel` message, binding unchanged) and not the crash. (Today the path still creates the default `data/<guildId>.json` before crashing, `WelcomeByeGuild.kt:122`.)

## 4. Components

None. No buttons/selects/modals/text inputs, no `ComponentIdManager`. `component_prefix: "welcome-bye@"` is unused.

## 5. Events

| JDA event | Filter | Behavior |
|---|---|---|
| `SlashCommandInteractionEvent` | `config.enabled` and name in set (`Event.kt:61-65`) | §3 |
| `GuildMemberJoinEvent` (`Event.kt:67-70` → `WelcomeByeGuild.kt:78-97`) | `config.enabled`; guild has a loaded setting (`mapper[guildId]`, no auto-create); `welcomeChannelId != 0`; `guild.getTextChannelById(id)` non-null (cached TEXT channel; deleted/non-text ⇒ silent return) | Builds substitutor (`forMemberEvent`, eventType `join`, member = joining member) and `channel.sendMessage(welcome template rendered in guild.locale).queue()`. No bot filter (bots joining also get welcomed). No permission pre-check; JDA throws `InsufficientPermissionException` synchronously if the bot cannot view/send/embed → only logged by JDA. |
| `GuildMemberRemoveEvent` (`Event.kt:72-75` → `WelcomeByeGuild.kt:99-118`) | same with `byeChannelId` | Fires for leave/kick/ban regardless of member cache (JDA gives `event.user` always). Uses `event.user` and **passes `member = null`** even when cached ⇒ `wbg@member_*` placeholders are not set for bye templates (they render literally). Sends `bye` template. |
| `GuildLeaveEvent` (`Event.kt:77-80` → `WelcomeByeGuild.kt:55-57`) | `config.enabled` | Deletes `data/<guildId>.json` and drops it from memory (`JsonGuildFileManager.removeAndSave`, `core/json/JsonGuildFileManager.kt:38-40`). When the plugin is disabled, data is kept. |

Member count note: JDA increments the cached `member_count` before dispatching the join event, so `%wbg@guild_member_count%` includes the new member (discord.py's `parse_guild_member_add` behaves the same).

## 6. Configuration

`plugins/WelcomeByeGuild/config.yaml` (shipped: `enabled: false`), schema `wbg/config/ConfigSerializer.kt:5-8`:

| Key | Type | Default | Use |
|---|---|---|---|
| `enabled` | Boolean | `false` | Master switch. `false`: load logs WARN and skips `WelcomeByeGuild.load()`; `guildCommands()` returns `[]`; all four handlers return immediately (including the GuildLeave data cleanup). Toggling via dashboard calls `reload()`. |

Decoding is kaml strict (`Yaml()` default; `core/plugin/PluginEvent.kt:62-63`): unknown keys raise an error → load fails (startup abort) or dashboard reload fails (then rolled back).

## 7. Localization & templates

- Locales shipped: `en-US`, `zh-TW`. Default/fallback locale: `zh-TW` (`WelcomeByeGuild.kt:31`, `Event.kt:21`).
- Files (14 per locale, 28 total: 1 `register.yaml` + 13 `message/*.yaml`):
  `lang/{en-US,zh-TW}/register.yaml`; `lang/{en-US,zh-TW}/message/{welcome,bye,guild-only,no-permission,invalid-channel,welcome-bind-success,welcome-bind-already,welcome-unbind-success,welcome-unbind-empty,bye-bind-success,bye-bind-already,bye-unbind-success,bye-unbind-empty}.yaml` (keys in `WelcomeByeGuildMessageKeys.kt:3-20`). (A stray untracked `.DS_Store` exists under `src/main/resources/lang/` locally; ignore.)
- `register.yaml` → command localizations only (§3). `message/*.yaml` → reply/embeds via Core **MessageCreator v2** (`core/builtin/messagecreator/v2/MessageCreator.kt`), which delegates content/embeds to the v1 builder (`core/builtin/messagecreator/v2/builder/MessageBuilder.kt:56-86`). None of these templates use `components`/`components_v2`.
- Template schema actually used: `content: String`; `embeds[]: {author{name, icon_url}, title{text}, description, thumbnail_url, color_code}`. Full v1 embed schema the engine accepts (for admin-customized files on disk): `model_key`, `author{name,url,icon_url}`, `title{text,url}`, `description`, `thumbnail_url`, `image_url`, `color_code` (`#RRGGBB`/`0xRRGGBB`, `java.awt.Color.decode`), `footer{text,icon_url}`, `timestamp` (epoch-ms digits or literal `%now%`), `fields[]{name,value,inline=false}` (`core/builtin/messagecreator/v1/serializer/MessageDataSerializer.kt:16-71`). Unknown keys ignored (`strictMode=false`, v2 `MessageCreator.kt:60`).
- Rendering rules to preserve (`core/builtin/messagecreator/v1/builder/MessageBuilder.kt`): every string is placeholder-parsed; URL fields (author url/icon, title url, thumbnail, image, footer icon) are set **only if the parsed value starts with `http`** (`:120-159`) — e.g. guild without icon ⇒ `%wbg@guild_icon_url%` = `-` ⇒ author icon omitted; an embed that ends up empty is dropped (`:117`); `content` is always set (empty allowed).
- Locale resolution (`v2/MessageCreator.kt:130-134`): exact locale map if that locale directory exists, else the default-locale map; **no per-key fallback** (key missing in an existing locale ⇒ `IllegalStateException`). Directory name → `DiscordLocale.from(dir)`. Guild locale is used for both replies and join/leave messages, so most non-Community guilds (preferred locale `en-US`) get English; any locale other than en-US/zh-TW gets zh-TW.

Welcome/bye templates (exact):

- en-US `welcome.yaml`: author name `%wbg@guild_name%`, icon `%wbg@guild_icon_url%`; title `🎉 Welcome %wbg@user_effective_name% joined us`; description (YAML `|` block, trailing newline):
  ```
  Nice to meet you %wbg@user_effective_name%!
  You are the **#%wbg@guild_member_count%** member of this server.
  Please read the rules: %wbg@guild_rules_channel_mention%
  Don't be shy!
  ```
  thumbnail `%wbg@user_avatar_url%`; color `#57F287`.
- zh-TW `welcome.yaml`: title `🎉 歡迎 %wbg@user_effective_name% 加入伺服器！`; description `很高興在這裡看到你 %wbg@user_mention%！` / `你是我們的第 **%wbg@guild_member_count%** 位成員！` / `請先閱讀規則：%wbg@guild_rules_channel_mention%` / `也不坊到處看看喔！` (sic, typo "不坊"); same author/thumbnail/color.
- en-US `bye.yaml`: author as above; title `😢 %wbg@user_effective_name% left`; description `Hope we can see each other again in the future...`; thumbnail `%wbg@user_avatar_url%`; color `#ED4245`.
- zh-TW `bye.yaml`: title `😢 %wbg@user_effective_name% 離開了我們`; description `但願我們會能未來的道路相見...` (sic).

### Placeholder engine semantics (Core `Substitutor`, `core/builtin/placeholder/Substitutor.kt`)
- Syntax `%key%`; escape char `$` (`$%key%` → literal `%key%`); Apache commons-text `StringSubstitutor` 1.15 defaults: unresolved keys are left verbatim; default-value syntax `%key:-fallback%` is active; **values are substituted recursively** and a self-referencing value throws `IllegalStateException("Infinite loop in property interpolation…")` (`Substitutor.kt:80-86`; commons-text default `disableSubstitutionInValues=false`).
- Lazy values (`putAllLazy`) are evaluated at parse time; supplier exceptions fall back to the default (`Placeholder.kt:285-287`).

### Placeholders available (all `wbg@`-prefixed keys set by `WelcomeByeGuildSubstitutorFactory.kt` via Core `Placeholder.put*`)

| Group (source) | Keys (prefix `wbg@`) | Values / none-value |
|---|---|---|
| Guild (`Placeholder.putGuild`, `Placeholder.kt:145-186`) — command + join + leave | `guild_id`, `guild_name`, `guild_name_upper`, `guild_name_lower`, `guild_locale` (JDA enum **name**, e.g. `CHINESE_TAIWAN`, `ENGLISH_US`), `guild_member_count`, `guild_boost_count`, `guild_booster_count` (alias of boost count), `guild_icon_url`, `guild_banner_url`, `guild_description`, `guild_owner_id`, `guild_owner_name`, `guild_owner_mention`, `guild_system_channel_{id,name,mention}`, `guild_rules_channel_{id,name,mention}` | ids default `0`, others `-` |
| User (`putUser`, `:188-215`) — command: the operator; join/leave: the member | `user_id`, `user_name`, `user_name_upper`, `user_name_lower`, `user_global_name`, `user_effective_name`, `user_mention`, `user_avatar_url` (effective avatar URL), `user_default_avatar_url`, `user_is_bot` (`true`/`false`), `user_created_unix`, `user_created_iso` (Java `OffsetDateTime.toString()`, e.g. `2021-06-25T12:34:56.789Z`; seconds/millis omitted when zero) | `0` / `-` / `false` |
| Member (`putMember`, `:217-248`) — command (operator) and join only | `member_id`, `member_display_name`, `member_nickname`, `member_nickname_or_name`, `member_avatar_url`, `member_roles_count`, `member_roles_mentions` (space-joined `<@&id>`), `member_roles_names` (`, `-joined), `member_joined_unix`, `member_joined_iso` | `0` / `-` |
| Event (`putEvent`, `:250-262`) | `event_type` (`command` / `join` / `leave`), `event_timestamp_unix`, `event_timestamp_ms`, `event_timestamp_iso` (`Instant.toString()`) | — |
| Selected channel (command only, `SubstitutorFactory.kt:28-34`) | `channel_id`, `channel_name`, `channel_mention`, `channel_type` (`TEXT`) | `0` / `-` |
| Operator (command only, `:36-40`) | `operator_id`, `operator_name` (username), `operator_mention` | — |
| Bound channels (all, `:65-93`) | `welcome_channel_{id,name,mention,type}`, `bye_channel_{id,name,mention,type}`, `welcome_channel_is_set`, `bye_channel_is_set` | `*_id` = stored id as string (`0` if unset; still the stored id if the channel was deleted); `*_mention` = `<#id>` or `-` (from stored id, not cache); `*_name`/`*_type` from cache (`-` if missing); `*_is_set` = `true`/`false` |
| Old channel (command only, `:95-110`) | `old_channel_id`, `old_channel_mention` (`<#id>` or `-`), `old_channel_name`, `old_channel_type` (cache; `-`) | — |

Also present (unprefixed, inherited from Core `Placeholder.get(...)` and the global substitutor): `bot_id`, `bot_name`, `user_id`, `user_mention`, `user_name`, `user_avatar_url`; for members `member_display_name`, `member_avatar_url`, `member_fixed_name`; for commands `command_name`, `full_command_name`, `language` (user locale native name), `command_string`, `channel_id`/`channel_name` (invoking channel), `channel_category_name`, `subcommand_name`. Plus any keys other plugins put into the global substitutor before this user's cached substitutor was first created (snapshot copy, `Substitutor.kt:20-23`).

## 8. Persistence

| Data set | Storage | Location | Key | Schema |
|---|---|---|---|---|
| Guild bindings | `JsonGuildFileManager<GuildSetting>` (Moshi + `KotlinJsonAdapterFactory`) | `plugins/WelcomeByeGuild/data/<guildId>.json` (CWD-relative; `WelcomeByeGuild.kt:39-43`, `core/plugin/PluginEvent.kt:21`) | guild id = file name (parsed with `toLong()`) | `GuildSetting(welcomeChannelId: Long = 0, byeChannelId: Long = 0)` (`WelcomeByeGuild.kt:25-28`); `0` = unset |

Example file (compact, keys in constructor order, snowflakes as JSON integers):
```json
{"welcomeChannelId":1277193832378667040,"byeChannelId":0}
```
Behavior details:
- All files are loaded eagerly when the object initializes (`core/json/JsonGuildFileManager.kt:14-19`); any non-numeric `*.json` file name throws `NumberFormatException` → plugin init fails → bot startup aborts.
- `get(guildId)` creates + writes a default file if missing (also from read-only paths like `invalid-channel` and `*-unbind-empty`).
- Missing JSON fields → constructor defaults; unknown fields skipped (Moshi behavior).
- Corrupt/empty file → logged, replaced by defaults and **immediately rewritten** (data loss) (`core/json/JsonFileManager.kt:42-67`, `:38`).
- Writes are synchronous `File.writeText` (truncate + write, not atomic) on the JDA event thread (`JsonFileManager.kt:100-113`).
- Delete on `GuildLeaveEvent` (enabled only).
- No Mongo, no SQLite, no other files.

Migration/compat for the port: read existing files as-is (camelCase keys, integer snowflakes — Python `json` keeps them exact; never round-trip through float/JS); keep file-per-guild layout or write an importer; treat missing/0 as unset.

## 9. External dependencies

- Gradle: only `compileOnly(project(":Core"))` (convention `xs-plugin`); uses Core's JDA 6.4.1, kaml, Moshi, commons-text.
- No HTTP calls, no credentials, no external services. Templates make Discord fetch avatar/guild icon CDN URLs.
- No hard/soft plugin dependencies; no other plugin calls into it.

## 10. Discord requirements

- Privileged intent **GUILD_MEMBERS** required for join/remove events (enabled unconditionally by Core, not declared in info.yaml — the port should declare it explicitly). `GUILDS` (implicit in JDA) for guild/channel cache and `GuildLeaveEvent`. No MESSAGE_CONTENT, no GUILD_PRESENCES.
- Cache: needs text-channel cache (`getTextChannelById`); no member cache needed (join payload carries the member; leave uses user).
- Bot permissions in bound channels: View Channel, Send Messages, Embed Links. No check at bind time.
- OAuth scope `applications.commands` for guild commands.
- Rate-limit sensitive: one channel message per join and per leave (raids ⇒ bursts; no throttling/batching); dashboard reloads and guild joins trigger per-guild command bulk overwrites.

## 11. Concurrency

- JDA dispatches gateway events sequentially on its event thread (Core configures no event pool), so command/join/leave handlers do not race each other in practice.
- `localizerRef`/`messageCreatorRef` are `AtomicReference` (safe swap during dashboard reload from a Ktor thread).
- `PluginEventConfigure.config` is a non-volatile `lateinit var` reassigned by `reload()` on the Ktor thread (visibility not guaranteed, benign in practice).
- `JsonGuildFileManager.mapper` is a plain `LinkedHashMap`; `GuildSetting` is mutated in place; `JsonFileManager.save/delete` are `@Synchronized` per file. Safe only under single-threaded dispatch.
- The deferred-reply callback (`WelcomeByeGuild.kt:300-302`) runs on JDA's callback pool but only uses the already-built `MessageEditData`.
- Core `Placeholder` per-user caches are unsynchronized `HashMap`s shared by all plugins (`Placeholder.kt:19-20`).

## 12. Bugs, quirks, dead code, hard-coded values

Behavior to preserve:
- All command replies ephemeral (defer-ephemeral + edit original) (`WelcomeByeGuild.kt:286-303`, `InteractionLogger.kt:26-28`).
- Double admin gate: `default_member_permissions=8` and runtime Administrator check (`Register.kt:41`, `WelcomeByeGuild.kt:272-274`).
- Channel option restricted to GUILD_TEXT; omitted option ⇒ current channel; non-text current channel ⇒ `invalid-channel` (`:276-284`).
- "Already bound" short-circuit (no write) and "nothing bound" unbind message.
- Unbind success shows `<#oldId>` even when the channel no longer exists.
- Same channel allowed for welcome and bye.
- Guild data deleted when the bot leaves/is removed from a guild (only when enabled).
- Join/leave messages silently skipped when unset, setting missing, or channel missing/not text.
- Locale = guild preferred locale; unsupported locales fall back to zh-TW.
- URLs that don't start with `http` are dropped from embeds; no bot filter on join/leave.

Probable bugs to fix (do not replicate):
1. Crash on commands invoked outside a regular `TextChannel` (`core/builtin/placeholder/Placeholder.kt:75`) — no reply; bind may be persisted silently (`WelcomeByeGuild.kt:148-160` saves before building the reply substitutor); as a result the `invalid-channel` message is never delivered in practice (§3).
2. Recursive placeholder expansion of user-controlled values (display names, guild/channel names): `%bot_name%` in a nickname expands; a self-reference (e.g. global name `%wbg@user_effective_name%`) throws ⇒ welcome/bye not sent (`Substitutor.kt:80-86`).
3. Per-user substitutor cache keyed by user id only (not guild), never evicted (memory growth), and leaks keys across events/plugins; bye uses the "user" cache so `wbg@member_*` are absent (`Placeholder.kt:19-58`, `SubstitutorFactory.kt:54`).
4. Read-only paths create data files (`WelcomeByeGuild.kt:122`, `:164`, `:198`, `:240`).
5. Corrupt data file silently reset; non-numeric data file name aborts startup (§8).
6. No validation that the bot can post in the bound channel; send failures only appear in logs.
7. `GuildLeaveEvent` cleanup skipped while disabled ⇒ orphan files.
8. If the combined guild command list across all plugins is empty at startup, Core skips the per-guild overwrite, leaving stale registrations (`core/base/ListenerManager.kt:19`); invoking a stale command of a disabled plugin is auto-deferred and never answered.

Dead code / oddities: `component_prefix` unused; `guild-only` path unreachable; `WelcomeByeGuild.load()` and `reload()` are identical and the object initializer already builds a `MessageCreator` (`:45-53`).

Hard-coded: default locale `DiscordLocale.CHINESE_TAIWAN` (`WelcomeByeGuild.kt:31`, `Event.kt:21`); none-value `-` (`WelcomeByeGuildSubstitutorFactory.kt:13`); default English command descriptions (`Register.kt:44-71`); embed colors `#57F287` / `#ED4245` (lang YAML); zh-TW copy typos noted in §7.

## 13. Testability

Pure logic to extract (unit-testable without Discord):
- `resolve_target_channel(option_channel, current_channel) -> channel | None` (type == text only).
- Bind/unbind state machine on `GuildSetting`: returns result key (`*-bind-already`, `*-bind-success`, `*-unbind-empty`, `*-unbind-success`) + new state + old id; persistence call expectations.
- Placeholder map builders from plain snapshots (guild/user/member/channel dataclasses) — table in §7 as golden data; mention/none rules (`<#id>`, `-`, `0`, `true/false`).
- Template engine: `%key%` substitution with `$` escape, `:-` default, non-recursive values (decide), unresolved left verbatim; YAML → embed dict with the `http` URL filter, empty-embed drop, color parsing.
- Locale resolution: (guild locale, available locales, default zh-TW) → locale; whole-locale fallback.
- JSON store: load directory, get-or-create, save, delete; corrupt-file handling; numeric-filename validation.
- Command metadata snapshot: names, descriptions, localizations, option types, channel_types, default permissions (compare generated payload against golden JSON).

Needs Discord test doubles: `Interaction` (response.defer/edit_original_response, user, guild, channel, permissions, locale), `Member`/`User`, `Guild` (get_channel, preferred_locale, member_count, icon, rules_channel, owner), `TextChannel.send` (assert embed), raw member-remove payload, guild-remove event.

## 14. Porting assessment

Difficulty: **Medium** — business logic is small, but faithful output depends on reproducing Core's template engine (v1 embed YAML schema, `%…%` placeholders with commons-text semantics, ~70 placeholder keys, http URL filter), command localization from `register.yaml`, per-guild JSON persistence, and channel-type restrictions.

Suggested discord.py mapping:
- `commands.Cog` with four `@app_commands.command`s, `@app_commands.default_permissions(administrator=True)`, `@app_commands.guild_only()`; runtime check `interaction.user.guild_permissions.administrator`.
- Localization via an `app_commands.Translator` (`CommandTree.set_translator`) backed by `lang/<locale>/register.yaml`, keys mirroring the camelCase paths; emit only en-US/zh-TW.
- `channel` option: in discord.py announcement channels are `TextChannel` objects and, to my knowledge, a `discord.TextChannel` annotation is registered as `channel_types=[text, news]` (verify against the pinned discord.py version); to keep `channel_types=[GUILD_TEXT]` use a custom `app_commands.Transformer` whose `channel_types` is `[discord.ChannelType.text]`, and validate `channel.type is ChannelType.text` (not `is_news()`) for the current-channel fallback.
- Auto-defer: `await interaction.response.defer(ephemeral=True, thinking=True)` (either per command or globally in `CommandTree.interaction_check`, skipping autocomplete), then `interaction.edit_original_response(...)`.
- Events: `on_member_join`; **`on_raw_member_remove`** (discord.py's `on_member_remove` only fires for cached members, unlike JDA); `on_guild_remove` for cleanup. Requires `Intents.members = True`.
- Registration: Kotlin registers guild-scoped commands to every guild; either replicate (`tree.copy_global_to(guild)`/`tree.sync(guild=…)` on ready + `on_guild_join`) or switch to global commands with guild-only contexts (document the change).
- Persistence: keep `data/<guildId>.json` compatible (atomic write via temp file + `os.replace`), `asyncio.Lock` per guild if handlers become concurrent.

Risks: placeholder/format parity (Java `OffsetDateTime`/`Instant` ISO strings, JDA enum names for `guild_locale`, CDN URL formats differ — discord.py appends `?size=1024`); stale/admin-customized lang files on disk must keep working; deciding whether to keep recursive substitution; concurrency (discord.py runs handlers concurrently, unlike JDA's single event thread).
