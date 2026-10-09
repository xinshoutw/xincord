# Research: `refactor/modern-change` (v4.0.0 rewrite) vs `main` (v3.4)

- Repo: `/Users/xinshou/IdeaProjects/XsDiscordBotKt` (read-only inspection via `git show/diff/log/ls-tree/grep`; nothing was built or run).
- `main` = production baseline (v3.4). `B` = `refactor/modern-change` (16 commits on top of `95d2b96`, merge-base `95d2b96`; also on `origin`).
- Path notation: `B:Core/...` = file on the branch, `main:Core/...` = file on main. Core sources live under `Core/src/main/kotlin/core/` (package `tw.xinshou.discord.core`).
- Method caveat: findings come from reading code. Anything marked *(unverified)* was inferred but not proven by reading a definitive source.

---

## 0. TL;DR

1. **v4 Core is a small, readable skeleton (2,324 Kotlin LOC vs 5,866 on main)**: a `Plugin` interface with `PluginContext.onLoad()/onUnload()`, `commands(): List<CommandHandler>`, `components(): List<ComponentHandler>`, `listeners()`, a map-based `CommandRegistry`/prefix-based `ComponentRegistry`, a Koin `coreModule`, kotlinx-serialization everywhere, a Mongo coroutine `DatabaseProvider`, `JsonFile`/`GuildJsonFile`, `Localizer` + `MessageTemplate`, and a builder-style `Substitutor`.
2. **The branch is not production-viable as-is.** Even on an upgraded install (v3 config and lang files already on disk), only the three API plugins, IntervalPusher and NtustCourse (minus persistence) behave roughly as on main. NtustManager works but re-posts everything on each restart. Every other plugin is broken end to end. All findings come from reading code; none was run. The Core defects:
   - Subcommands are never dispatched (handler keyed by name, looked up by full path).
   - Six plugins' `ListenerAdapter` overrides are never registered (ChatLogger, DynamicVoiceChannel, VoiceLogger, MusicPlayer autocomplete, Giveaway, Ticket).
   - Buttons, modals and selects are auto-acknowledged with `deferEdit()`, so `replyModal` and ephemeral replies fail.
   - The unchanged v3 message YAML cannot be parsed by the new strict `MessageTemplate`, ids it would generate cannot be parsed by `ComponentId`, and there is no modal template support.
   - `Localizer` very likely fails on every `register.yaml` (KAML → `JsonElement`).
   - Plugin `config.yaml` defaults resolve to **Core's** `config.yaml`, and plugin `lang/` is never exported.
   - `GUILD_MEMBERS` and DAVE voice encryption were dropped.
   - `onLoad()` runs before JDA exists.
   - The new plain `URLClassLoader` hides SQLiteAPI from ChatLogger.
   - `logback.xml` names classes that were renamed.
   - A first run without `config.yaml` crashes.
3. **It is not an "architecture-only" migration.** The plugin commit deleted about 6.2k lines. That includes real features: Ticket transcript thread flattening and live preview; Giveaway post embed, refresh and result announcements; MusicPlayer `/queue` list, progress bar and pre-checks; startup data pruning in several plugins. Persistence also moved from Mongo to memory: DynamicVoiceChannel rooms, NtustCourse subscriptions, and NtustManager seen-lists, so it re-posts every announcement on restart. Most zh-TW UI strings became English. The spec's own "out of scope: plugin business logic changes" and "template format stays" rules were broken. Command names, options and custom_id wire formats *were* preserved, except MusicPlayer's prefix.
4. **Docs:** `CLAUDE.md` and `PROJECT_CONTEXT.md` on the branch describe **v3/main** (`PluginEvent`, `load()/guildCommands()`, `GlobalUtil.checkCommandString`, `CacheDbServer`, Moshi). The branch `README.md` describes **v4/B** (`object X : Plugin`, `PluginContext.onLoad()`, `commands()`). Both docs are also partly stale relative to main (Java 21 vs 25, single classloader, no coreApi validation, reload semantics, plugin count).
5. **For the Python port:** use main as the behavioral contract. Keep the v4 *shape* of the code (declarative per-plugin registration, exact command-path dispatch, prefix/regex component routing, typed config models, per-guild JSON store, external-or-embedded DB option). Drop Koin-style DI, classloader isolation, central auto-defer of components, and silent strict-schema rewrites. discord.py already provides most of this through Cogs, `app_commands`, persistent `View`s/`DynamicItem`, and `load_extension`/`reload_extension`.

---

## 1. v4 Core architecture as implemented on the branch

### 1.1 File map (B)

| Area | File (B:Core/src/main/kotlin/core/...) | LOC | Notes |
|---|---|---|---|
| Entry | `Main.kt` | 74 | runBlocking, Logback/Jansi, Clikt args, `startKoin`, token override, start order |
| App | `BotApplication.kt` | 162 | JDA build (`jda-ktx light()`), listeners, command refresh, builtins, stop/reload, private `CoreEventListener` |
| DI | `di/CoreModule.kt` | 34 | Koin singles: BotConfig, DatabaseProvider, CommandRegistry, ComponentRegistry, PluginRegistry, InteractionLogger, DashboardServer |
| Plugins | `plugin/Plugin.kt`, `PluginConfig.kt`, `PluginContext.kt`, `PluginRegistry.kt` | 28/37/15/242 | interface, info.yaml model, context, discovery+lifecycle |
| Commands | `command/CommandHandler.kt`, `CommandRegistry.kt`, `ComponentRegistry.kt` | 48/53/26 | data classes + DSL, registries |
| Config | `config/BotConfig.kt`, `config/ConfigLoader.kt` | 53/46 | core config model, KAML loader + default export |
| DB | `database/DatabaseProvider.kt`, `Collection.kt`, `GuildCollection.kt`, `DatabaseConfig.kt` | 209/41/19/3 | embedded (flapdoodle, Mongo 8.2) or external Mongo, coroutine driver |
| i18n | `i18n/Localizer.kt`, `LocaleMap.kt`, `LocaleUtil.kt`, `MessageTemplate.kt` | 84/16/15/315 | register.yaml flattening, message YAML → JDA builders |
| Placeholders | `placeholder/Substitutor.kt`, `Placeholder.kt` | 31/53 | `%key%` substitution, `withUser/withMember/withGuild/withCommand/withBot` |
| Utils | `util/ComponentId.kt`, `JsonFile.kt`, `FileGetter.kt`, `JdaExtensions.kt`, `Arguments.kt` | 93/85/98/61/52 | |
| Builtins | `builtin/StatusChanger.kt`, `ConsoleLogger.kt`, `AppEmoji.kt` | 39/44/18 | |
| Console/log | `cli/ConsoleManager.kt`, `logger/InteractionLogger.kt`, `LogbackConfig.kt`, `JLineLogbackAppender.kt`, `HighlightingCompositeConverterEx.kt`, `Color.kt` | 56/49/24/21/19/42 | |
| Dashboard | `dashboard/CoreDashboardBackend.kt` | 19 | now only a no-op `class DashboardServer` stub |

Removed from main's Core: `base/BotLoader, ListenerManager, PluginLoader, SettingsLoader, UpdateChecker`, `plugin/ClassLoader (PluginSandboxClassLoader), PluginEvent, yaml/InfoSerializer`, `builtin/messagecreator/{v1,v2,modal}`, `builtin/placeholder/*`, `json/JsonFileManager, JsonGuildFileManager`, `localizations/*`, `mongodb/*` (CacheDbServer renamed into DatabaseProvider), `util/GlobalUtil, ComponentIdManager, UrlDataGetter`, `logger/LogBackManager`, `cli/JLineManager`, and the 355-line `CoreDashboardBackend`.

### 1.2 Startup sequence (B:`Main.kt`, `BotApplication.start()`)

1. `LogbackConfig.configureSystem()` (Jansi), then `Arguments.parse(args)` (Clikt `main()`, which prints usage and exits on bad flags), then `LogbackConfig.setLevel(--log-level)`.
2. `startKoin { modules(coreModule) }`. `getKoin().get<BotConfig>()` loads `./config.yaml` (see §1.11). If `-t` is given, `getKoin().declare(config.copy(botToken = ...))` overrides it. `require(botToken != "YOUR_BOT_TOKEN_HERE")` runs **outside** the try block, so failures here are uncaught.
3. `db.start()` (embedded or external Mongo), `dashboard.start()` (stub, logs only), `bot.start()`:
   1. `pluginRegistry.discoverAndLoad()`: read jars, run each plugin's **`onLoad()` (before JDA exists)**, register `commands()`/`components()`.
   2. `light(token, enableCoroutines = true) { enableIntents(plugins); enableCache(plugins); setMemberCachePolicy(plugins); disableCache(ACTIVITY, CLIENT_STATUS); setBulkDeleteSplittingEnabled(false) }`. This is `JDABuilder.createLight` with `GatewayIntent.DEFAULT` (no privileged intents) plus jda-ktx `CoroutineEventManager`.
   3. `addEventListener(InteractionLogger)`, `CoreEventListener`, then every plugin's `listeners()`. These are added **before** `awaitReady()`, so plugins now receive Ready/GuildReady events; v3 added them after ready.
   4. `loadKoinModules(module { single<JDA> { jda } })`. JDA becomes injectable only now.
   5. `jda.awaitReady()`, then `refreshCommands()`: global commands via `jda.updateCommands()`, guild commands pushed to every guild.
   6. `StatusChanger(jda, config.statusChanger).start(builtinScope)`, `ConsoleLogger(...)` (constructed, never wired), `AppEmoji(jda).initialize()` (never exposed).
4. `console.start(...)`, then `stopSignal.await()`. The `finally` block runs `console.stop(); bot.stop(); dashboard.stop(); db.stop(); stopKoin(); LogbackConfig.uninstall()`.

v3 order for comparison (`main:Core/.../Main.kt`, `base/BotLoader.kt`): Logback, then Args, then `CacheDbServer.start`, then the real `DashboardServer.start(CoreDashboardBackend)`, then `BotLoader.start` (UpdateChecker (disabled), SettingsLoader, `--no-online` early return, token check, `PluginLoader.preLoad` (jars, info.yaml, sandbox classloaders), JDA `createDefault` + `setEnabledIntents(GUILD_MEMBERS, SCHEDULED_EVENTS, GUILD_EXPRESSIONS)` + plugin intents + DAVE, `awaitReady`, **then** `PluginLoader.run()` (plugin `load()`), then listeners: InteractionLogger, ListenerManager (guild commands, StatusChanger, ConsoleLogger), plugin listeners, global commands), then JLine.

### 1.3 Plugin interface and PluginContext

```kotlin
// B:Core/src/main/kotlin/core/plugin/Plugin.kt
interface Plugin {
    var config: PluginConfig                    // injected by PluginRegistry after instantiation
    fun Module.definitions() {}                 // Koin definitions (no plugin overrides this)
    fun PluginContext.onLoad() {}
    fun PluginContext.onUnload() {}
    fun PluginContext.onReload() { onUnload(); onLoad() }   // never called by Core
    fun commands(): List<CommandHandler> = emptyList()
    fun components(): List<ComponentHandler> = emptyList()
    fun listeners(): List<Any> = emptyList()    // raw JDA listeners, added after JDA build
}

// B:Core/src/main/kotlin/core/plugin/PluginContext.kt
class PluginContext(val pluginName: String, val pluginDirectory: File /* plugins/<Name> */, val logger: Logger) {
    val fileGetter: FileGetter by lazy { FileGetter(pluginDirectory, this::class.java) } // bound to Core's class (bug, see C11)
}
```

The spec's `PluginContext` was meant to expose "inject, register, i18n". The implementation exposes only name, directory, logger and fileGetter. Plugins still use `object Event : Plugin` and stash the context in a `lateinit var` (e.g. `B:Plugins/BasicCalculator/.../Event.kt`).

### 1.4 PluginConfig (`info.yaml`)

```kotlin
// B:Core/src/main/kotlin/core/plugin/PluginConfig.kt
@Serializable data class PluginConfig(
  val author: String = "", val main: String, val name: String, val description: String = "",
  @SerialName("coreApi") val coreApi: String, val version: String,
  @SerialName("component_prefix") val componentPrefix: String = "",
  @SerialName("require_intents") val requireIntents: List<String> = emptyList(),
  @SerialName("require_cache_flags") val requireCacheFlags: List<String> = emptyList(),
  @SerialName("require_member_cache_policies") val requireMemberCachePolicies: List<String> = emptyList(),
  @SerialName("depend_plugins") val dependPlugins: List<String> = emptyList(),
  @SerialName("soft_depend_plugins") val softDependPlugins: List<String> = emptyList())
```

Compared with v3 `InfoSerializer`, the branch dropped `prefix`, `depend_jars` and `soft_depend_jars`. KAML `Yaml.default` is strict, so an info.yaml that still contains those keys would now fail to parse. None of the shipped info.yaml files use them. Member cache policies: an empty list now means `NONE` (v3 always had `OWNER`+`VOICE`), and only `VOICE|ONLINE|OWNER|PENDING` are accepted. `ALL` and `BOOSTER` throw. Unknown intents or cache flags also throw now (v3 skipped them silently).

### 1.5 Plugin loading, ordering, reload (B:`plugin/PluginRegistry.kt`)

- Discovery: `plugins/*.jar`, reading `info.yaml` straight from the jar. **coreApi check** compares major.minor against `System.getProperty("core.version", "4.0")`. It ignores the generated `Version.CORE_API`, so a 4.1 Core would reject 4.1 plugins unless `-Dcore.version` is set. There is no version-format check (v3 had a regex).
- Order: DFS topological sort over `depend_plugins` only. Soft dependencies are ignored. **A missing hard dependency is not reported**, so the plugin loads anyway (v3 failed it). A cycle throws `error(...)` out of `discoverAndLoad`, which aborts the whole bot start (v3 failed only the plugins involved).
- Class loading: `URLClassLoader(arrayOf(jar), coreLoader)`. Delegation is plain parent-first, and there is **no access to dependency plugins** (v3's `PluginSandboxClassLoader` was child-first and could resolve classes and resources from `depend_plugins`). Instantiation reads the `INSTANCE` field, falling back to a no-arg constructor. This is still reflection, despite the commit message "no reflection".
- Per plugin: `plugin.config = config`; `mkdirs(plugins/<Name>)`; `loadKoinModules(module { definitions() })`; `PluginContext`; `onLoad()`; register `commands()` (tagged with plugin name) and `components()`. If `onLoad` throws, the error is logged and the plugin skipped, but its Koin module and classloader leak.
- Unload: in reverse order, `onUnload()`, `unloadKoinModules`, close classloader, deregister commands and (only if `component_prefix` is non-empty) components.
- **Reload**: the console `reload` calls `BotApplication.reload()`, which runs `stop()`, clears both registries, then `start()`. That is a full restart: all plugins unloaded, new classloaders and object instances, and **a new JDA login**. `PluginRegistry.reloadAll()/reloadPlugin()` exist but nothing calls them, and no plugin's `onReload()` is ever invoked. Side effects: `builtinScope` is cancelled in `stop()` and never recreated, so **StatusChanger never runs again after a reload**. The core `BotConfig` is a Koin singleton and is **not re-read** (v3's reload re-read `config.yaml`). There is no hot reload of a single plugin and no file watching.

### 1.6 Commands

```kotlin
// B:Core/src/main/kotlin/core/command/CommandHandler.kt
data class CommandHandler(val data: CommandData, val isGlobal: Boolean = false,
                          val execute: suspend (SlashCommandInteractionEvent) -> Unit)
fun slashCommand(data: CommandData, isGlobal: Boolean = false,
                 execute: suspend (SlashCommandInteractionEvent) -> Unit) = CommandHandler(data, isGlobal, execute)

// B:Core/src/main/kotlin/core/command/CommandRegistry.kt
fun register(handler: CommandHandler, pluginName: String? = null) {
    val name = handler.data.name            // top-level name, e.g. "economy"
    handlers[name] = handler.execute
    ...
}
suspend fun dispatch(event: SlashCommandInteractionEvent) {
    val handler = handlers[event.fullCommandName]   // e.g. "economy balance"  -> miss for any subcommand
    if (handler != null) handler.invoke(event) else logger.warn("No handler found for command: {}", ...)
}
val guildCommands: List<CommandData>  /  val globalCommands: List<CommandData>
```

- **Bug: commands with subcommands or subcommand groups are never dispatched.** The handler is stored under the top-level name but looked up by full path. The auto-deferred reply is never completed, so the user sees "thinking..." until the interaction expires. The spec (§5.1) keyed by `fullCommandName`, and the DSL `slashCommand("economy","balance")` from the spec was never implemented.
- Guild commands are pushed to every guild at start and on `GuildJoinEvent`. Global commands go through `jda.updateCommands()`. Same as v3.
- Message-context and user-context commands and autocomplete are not routed. Plugins must handle them through `listeners()`.

### 1.7 Components (buttons, modals, selects)

```kotlin
data class ComponentHandler(val prefix: String,
  val onButton: (suspend (ButtonInteractionEvent) -> Unit)? = null,
  val onModal: (suspend (ModalInteractionEvent) -> Unit)? = null,
  val onStringSelect: (suspend (StringSelectInteractionEvent) -> Unit)? = null,
  val onEntitySelect: (suspend (EntitySelectInteractionEvent) -> Unit)? = null)
fun componentHandler(prefix: String, builder: ComponentHandlerBuilder.() -> Unit): ComponentHandler
// ComponentRegistry.findHandler(id) = handlers.entries.find { id.startsWith(it.key) }   (first prefix match)
```

`CoreEventListener` (private, in `BotApplication.kt`) launches each handler in its own `CoroutineScope(SupervisorJob() + Dispatchers.Default)`, which is multi-threaded. Plugin `listeners()` *also* receive every interaction event, so a plugin that registers both can handle one interaction twice.

### 1.8 Listener registration

`Plugin.listeners(): List<Any>` objects are added with `jda.addEventListener` right after the JDA build. jda-ktx's `CoroutineEventManager` is active, so a listener may be a `ListenerAdapter` or a `CoroutineEventListener`. Only AutoRole, TicketAddons and WelcomeByeGuild return listeners on B. Six other plugins override `ListenerAdapter` methods on their `Event` object that are never registered (C24).

### 1.9 Auto-defer (B:`logger/InteractionLogger.kt`)

Unless `--no-auto-defer-interactions` is passed: slash commands get `deferReply(true)` (as in v3). **Buttons, modals, string selects and entity selects now get `deferEdit()`** (v3 deferred none of them). Message-context commands are **no longer** deferred (v3 deferred them). Consequences: a component handler can no longer open a modal (`replyModal`), send a fresh ephemeral reply, or `deferReply` on the event. Every such flow fails with "Interaction has already been acknowledged". The config key `auto_defer_replies` exists in `BotConfig` but is never read; only the CLI flag works. **No flag setting makes the plugins work.** The single flag toggles slash commands and components together, and the B plugins answer slash commands through `event.hook.editOriginal` without acknowledging first. With `--no-auto-defer-interactions`, the component flows work again but every slash command goes unanswered. Exceptions thrown in handlers are swallowed by `CoreEventListener`'s scope, which has no handler, so users see "…is thinking" until the token expires.

### 1.10 Dependency injection (Koin 4.2.0)

- `coreModule` (B:`di/CoreModule.kt`) holds `single { ConfigLoader.load<BotConfig>(File("config.yaml"), "config.yaml") }`, `single { DatabaseProvider(get<BotConfig>().database) }`, `CommandRegistry`, `ComponentRegistry`, `PluginRegistry(File("plugins"), get(), get())`, `InteractionLogger`, `DashboardServer`.
- `BotApplication` and `ConsoleManager` are constructed by hand in `Main.kt`, not by Koin. JDA is added as a dynamic module after plugins load.
- **No plugin overrides `Module.definitions()`.** A few plugins (IntervalPusher, NtustCourse, NtustManager) use Koin as a service locator (`get<JDA>()`, `get<DatabaseProvider>()`), which is fragile because JDA is not in Koin while `onLoad` runs. `koin-ktor` and `koin-test` are in the version catalog but unused.
- Net effect: Koin adds a dependency and a timing hazard and buys almost nothing over constructor parameters.

### 1.11 Config loading

```kotlin
// B:Core/src/main/kotlin/core/config/BotConfig.kt
@Serializable data class BotConfig(
  @SerialName("bot_token") val botToken: String,
  val database: DatabaseConfig = DatabaseConfig(),          // embedded=true, connection_string, port(unused), data_path="mongodb-data"
  @SerialName("status_changer") val statusChanger: StatusChangerConfig = ..., // activities: List<"TYPE;text;delayMs">
  @SerialName("console_loggers") val consoleLoggers: List<ConsoleLoggerConfig> = emptyList(), // guild_id, channel_id, log_types, format
  @SerialName("auto_defer_replies") val autoDeferReplies: Boolean = true)   // never read
// B:Core/src/main/kotlin/core/config/ConfigLoader.kt
inline fun <reified T> load(file: File, default: String? = null): T   // export default if missing, then Yaml.default (strict)
fun exportDefault(resourcePath: String, targetFile: File)            // uses ConfigLoader::class.java.getResourceAsStream(resourcePath)
```

- Core passes `"config.yaml"` without a leading slash. `Class.getResourceAsStream` resolves that relative to the package (`tw/xinshou/discord/core/config/config.yaml`), which does not exist, so **a first run without `config.yaml` throws `IllegalArgumentException("Classpath resource not found")` inside Koin and the process dies**. The README promises the opposite.
- Plugins call `ConfigLoader.load(..., default = "/config.yaml")`. That is resolved by **Core's** class, so it exports **Core's** `config.yaml` (the bot_token template) into `plugins/<Name>/config.yaml`. Strict KAML then fails on `bot_token`. Fresh installs therefore cannot load any plugin that relies on this.
- The core schema was renamed (`general_settings`/`builtin_settings` → flat keys) and KAML is strict on both refs, so a v3 core `config.yaml` fails to parse on B. There is no migration path. Plugin `ConfigSerializer`s are unchanged, so existing plugin config files still load.

### 1.12 i18n

```kotlin
class Localizer(langDir: File, defaultLocale: DiscordLocale) {   // reads ONLY lang/<locale>/register.yaml
  operator fun get(key: String): LocaleMap; fun get(key: String, locale: DiscordLocale): String; fun has(key: String): Boolean }
class LocaleMap(data: Map<DiscordLocale,String>, defaultLocale: DiscordLocale) {
  fun resolve(locale): String /* locale -> default -> any -> "" */; fun toMap(): Map<DiscordLocale,String> }
class MessageTemplate(langDir: File, defaultLocale: DiscordLocale, componentIdPrefix: String? = null) {
  fun buildCreate(messageId, locale?, substitutor?): MessageCreateBuilder
  fun buildEdit(messageId, locale?, substitutor?): MessageEditBuilder }
```

- `Localizer` flattens **raw YAML keys** (`basic-calculate.name`). v3 `StringLocalizer` flattened **Kotlin property names** of the typed data class via reflection (`basicCalculate.name`). Plugins that kept v3 camelCase key constants silently get empty localization maps. Missing keys no longer fail loudly; they become `""`. The spec promised "fails explicitly on missing keys".
- **It is likely that no register.yaml loads at all.** `Localizer.kt:44` decodes with `Yaml.default.decodeFromString(JsonElement.serializer(), …)`. kotlinx's `JsonElement` serializer only works with a `JsonDecoder` ("This serializer can be used only with Json format"), and KAML's decoder is not one. The exception is caught at `:52`, so **every plugin ends up with empty localizations, whatever its key style**. This is high confidence from the kotlinx contract but was not executed. Supporting evidence: main's v2 `MessageCreator` converts YAML nodes to `JsonElement` by hand (`main:Core/.../messagecreator/v2/MessageCreator.kt:153-167`), which suggests the author knew about this limitation.
- `MessageTemplate` reads `lang/<locale>/message/*.y(a)ml` with a **new strict schema** (`title: String`, `color`, `thumbnail`, `image`, `components: [{buttons|string_select|entity_select}]`, `style: "PRIMARY"`, `id: String`). Component ids are built as `"$componentIdPrefix:$id"`. The shipped v3 YAML uses `title: {text}`, `image_url`, `color_code`, YAML-tagged `!ButtonsComponent`, `uid:` maps, integer styles and `model_key` models, so **every v3 message file fails to parse**, gets logged, and the next `buildCreate()` throws `Message not found`. Not supported at all: modal templates, Components V2 (`is_components_v2`), `model_key` models, embed timestamp, title URL. The spec said the "format stays" and "modal templates" would be supported.
- **Template-built component ids cannot be parsed back by `ComponentId`**, even after rewriting the YAML. `buildComponentId` produces `"$prefix:$id"` (e.g. `ticket@:a:create;…`), but `ComponentId.parse` requires the `:` at index 1 of every segment (`util/ComponentId.kt:72`), so it throws "Invalid segment format". v3 also dropped embed URLs that did not render to http(s) (`main:…/v1/builder/MessageBuilder.kt:127,151,179`). B passes them straight to `EmbedBuilder`, so a leftover `%key%` in an icon URL throws.

### 1.13 Placeholders

```kotlin
class Substitutor(mapper = mutableMapOf(), lazyMapper = mutableMapOf(), delimiterStart = "%", delimiterEnd = "%") {
  fun parse(content: String): String; fun put(k, v); fun putAll(vararg pairs); fun putLazy(k, supplier) }
fun Substitutor.withUser(user) / withMember(member?) / withGuild(guild?) / withCommand(event) / withBot(bot)
```

Keys still provided: `user_*` (id, name, mention, avatar_url, is_bot, created_unix/iso), `member_*` (id, display_name, nickname, avatar_url, roles_count, roles_mentions, roles_names, joined_unix/iso), `guild_*` (id, name, member_count, icon_url, owner_id), `command_name`, `full_command_name`, `command_string`, `channel_id`, `channel_name`, `subcommand_name`, `bot_id`, `bot_name`.
Dropped compared with v3: `member_fixed_name`, `language`, `channel_category_name`, every `component_*` key, the `putGuild/putUser/putMember/putEvent/putTextChannel` families (`guild_name_upper`, `guild_owner_mention`, `user_global_name`, `member_nickname_or_name`, `event_timestamp_*`, `channel_mention`, …), prefix support, `"-"` none-values, and v3's per-user persistent substitutor (`Placeholder.update`). Some defaults changed: `member_roles_mentions` is now comma-joined; `guild_icon_url` is `""` instead of `"-"`; `member_nickname` falls back to the effective name. Missing keys render literally as `%key%`.

### 1.14 Component ids (B:`util/ComponentId.kt`)

```kotlin
class ComponentId(prefix: String, idKeys: Map<String, FieldType>, maxLength: Int = 100) {
  enum class FieldType { STRING, INT_HEX, LONG_HEX }
  fun build(vararg fields: Pair<String, Any>): String      // "{prefix}a:{v};b:{v}"  (a,b,… by idKeys order)
  fun parse(componentId: String): Map<String, Any> }
```

The wire format matches v3 `ComponentIdManager`: prefix plus single-letter keys assigned in key order, `;` separators, hex for INT/LONG. Differences: no Substitutor pass on values, values may contain `:`, and no non-empty or type checks. Old persistent buttons still parse **only if** a plugin kept the same prefix and the same key order (checked per plugin in §2.3).

### 1.15 Storage

```kotlin
class JsonFile<T : Any>(file: File, serializer: KSerializer<T>, defaultInstance: T? = null, json: Json = JsonFile.json) {
  var data: T; fun save(); fun update(block: (T) -> T); fun delete() }      // prettyPrint, ignoreUnknownKeys, encodeDefaults
class GuildJsonFile<T : Any>(directory: File, serializer: KSerializer<T>, defaultInstance: () -> T, json: Json = ...) {
  operator fun get(guildId: Long|String): JsonFile<T>; fun remove(guildId) }   // <dir>/<guildId>.json, lazy, cached
class DatabaseProvider(config: BotConfig.DatabaseConfig) { suspend fun start(); fun database(name): MongoDatabase; suspend fun stop() }
class Collection<T : Any>(collection: MongoCollection<T>) { suspend get/upsert/delete/findAll/count/contains/clear }   // _id = String key
class GuildCollection<T : Any>(database, collectionPrefix, codec: Class<T>) { fun forGuild(guildId): Collection<T> } // "<prefix>_<guildId>"
```

- `JsonFile` differences from v3 `JsonFileManager`: the file is no longer created on init. A parse error falls back to the default, and the next `save()` **overwrites the corrupt file** (v3 behaved the same, but logged with the exception). Not `@Synchronized`, and `GuildJsonFile`'s cache is a plain map, while handlers now run on `Dispatchers.Default` (race risk). Output is pretty-printed instead of compact. `GuildJsonFile` no longer preloads every `<guildId>.json` at startup.
- Mongo: the embedded server keeps v3's behaviour (flapdoodle, `V8_2`, env `XS_MONGODB_PORT|XS_MONGODB_DB_PATH|XS_MONGODB_INSTANCE`, random free port with 8 retries, `./mongodb-data`). It can now also connect to an external server via `database.embedded=false`. The `database.port` key is ignored. **`Collection<T>` stores `T` as the document itself, so it cannot read v3 documents** (`{_id, value, timestamp}` with `{items, itemTypeName}` list wrappers). In practice only NtustManager and NtustCourse touch Mongo on B, and both carry TODOs (§2.3).

### 1.16 Builtins and dashboard

- `StatusChanger`: format `TYPE;text;delayMs`. STREAMING no longer takes a URL. After a reload it is dead (cancelled scope).
- `ConsoleLogger`: has `logCommand/logButton/logModal`, but **nothing calls them**, so forwarding interactions to Discord channels (the `console_loggers` config) is silently gone. v3 registered it as a listener.
- `AppEmoji`: caches application emojis but is not reachable by plugins (private field). v3 exposed it as an `object`.
- Dashboard: `B:Core/.../dashboard/CoreDashboardBackend.kt` is now `class DashboardServer { fun start() = log("placeholder"); fun stop() {} }`. The real v3 web dashboard (core config view/save with a masked token, plugin list, enable toggle, plugin YAML edit, per-plugin reload) is **not started**. The `:WebDashboard` module is still compiled into Core (`implementation(project(":WebDashboard"))`) but unused.

### 1.17 CLI flags (B:`util/Arguments.kt`)

| Flag | main | B |
|---|---|---|
| `-t, --token` | override token | override via `getKoin().declare(...)` |
| `-l, --level` (main) / `-l, --log-level` (B) | log level | **renamed**: `--level` is now an unknown option, and Clikt `main()` prints usage and exits |
| `-N, --no-online` | skips JDA build (offline mode: DB, dashboard, console still run) | **parsed but ignored** (always connects) |
| `-I, --ignore-update` | no-op (UpdateChecker hard-disabled with `|| true`) | parsed, ignored (UpdateChecker deleted) |
| `-Flang, --force-renew-lang-resources` | overwrite exported `lang/` | **parsed but ignored** |
| `--[no-]auto-defer-interactions` | toggles auto-defer (slash and message-context) | toggles auto-defer (slash and all components) |

### 1.18 Console (B:`cli/ConsoleManager.kt`)

JLine `LineReader`, prompt `"> "` (was `"console > "`), completer `reload|stop|exit|shutdown`, unknown commands produce a warning. Differences: Ctrl-C or **any** read exception ends the console loop without stopping the bot, leaving a headless process (v3 logged ^C and kept reading, and stopped on ^D). `stop` calls `bot.stop()` and then `finally` calls `bot.stop()` again. That is harmless because `unloadAll` empties the map.

### 1.19 Logging

`Core/src/main/resources/logback.xml` is unchanged on B and still references `tw.xinshou.discord.core.logger.JLineAppender` and `...HighlightingCompositeConverter`. On B those classes were renamed to `JLineLogbackAppender` (an `OutputStreamAppender` with no encoder configured) and `HighlightingCompositeConverterEx`. **Logback cannot create the CONSOLE appender**, so console output is lost and only `log/output.log` keeps working *(unverified at runtime; class names verified)*. `jansi.passthrough` is no longer set. Interaction log lines dropped the option values (`/fullCommandName` instead of `commandString`).

---

## 2. Diff vs main: externally observable behaviour

### 2.1 Core-level behaviour changes (affect every plugin)

| # | Area | main (v3.4) | B (v4) |
|---|---|---|---|
| C1 | Core config file | `general_settings.bot_token`, `builtin_settings.status_changer_settings.activity_messages`, `builtin_settings.console_logger_settings[].{guild_id,channel_id,log_type,format}` | `bot_token`, `status_changer.activities`, `console_loggers[].{guild_id,channel_id,log_types,format}`, new `database.{embedded,connection_string,port,data_path}`, `auto_defer_replies` (unused). KAML is strict on both refs, so with the renamed schema **a v3 `config.yaml` fails to parse on B**, and there is no migration |
| C2 | Token placeholder | `ODgAAAAAAAAAAADkx.GBBBBI.V6CC…9mfsU` | `YOUR_BOT_TOKEN_HERE` |
| C3 | First run without config.yaml | exports default and logs | crashes (default resource not found, §1.11) |
| C4 | CLI | `--level`, `--no-online` works, `-Flang` works | `--log-level`; `--no-online` and `-Flang` ignored; Clikt exits on unknown flags |
| C5 | Gateway intents | GUILD_MEMBERS + SCHEDULED_EVENTS + GUILD_EXPRESSIONS + plugin intents | GatewayIntent.DEFAULT (no GUILD_MEMBERS/PRESENCES/MESSAGE_CONTENT unless a plugin asks) + plugin intents. **Member join/leave events are lost**, and many extra non-privileged intents are enabled |
| C6 | Caches | createDefault minus ACTIVITY/VOICE_STATE/CLIENT_STATUS/ONLINE_STATUS, plus plugin flags; member cache OWNER+VOICE+plugins | createLight: all CacheFlags off except plugin ones; member cache NONE unless plugins ask (VOICE). EMOJI, STICKER, MEMBER_OVERRIDES, ROLE_TAGS etc. are now off |
| C7 | Voice | DAVE via `JDaveSessionFactory` (`ff1b68f`) | no DAVE configured *(voice may fail to connect where DAVE is required)* |
| C8 | Auto-defer | slash and message-context only | slash plus **all component/modal interactions** (`deferEdit`); message-context no longer deferred |
| C9 | Subcommands | each plugin routed `fullCommandName` itself | registry miss, so never handled |
| C10 | Plugin init timing | `load()` after JDA ready | `onLoad()` before JDA exists |
| C11 | Plugin resources | `lang/` exported to `plugins/<Name>/lang/…`; plugin `config.yaml` exported from the plugin jar | Only BasicCalculator, BotInfo and _Example even try to export `lang/` (via `PluginContext.fileGetter`, which is bound to the Core jar and also strips the `lang/` prefix). Every other plugin never exports `lang/`, so fresh installs have no localizations and no message templates, and only pre-existing v3 `plugins/<Name>/lang/` trees are read. Every plugin loads its config via `ConfigLoader.load(..., "/config.yaml")`, which resolves to Core's `config.yaml` |
| C12 | Message/modal templates | v1/v2 schema (`uid` maps, `!ButtonsComponent`, `model_key`, Components V2) and modal YAML | New strict schema, and v3 YAML cannot be parsed. Of the shipped files only `content:`-only templates survive (e.g. 11 WelcomeByeGuild files and Giveaway's result texts). No modal templates; B plugins hard-code English modals with no max lengths. Template component ids `"$prefix:$id"` cannot be parsed by `ComponentId`. `model_key` runtime models are no longer injected (no live previews, no per-giveaway buttons) |
| C13 | Placeholders | large key set (see §1.13) | reduced key set; unknown keys render literally |
| C14 | Cross-plugin classes | dependency-aware, child-first sandbox classloader | Isolated, parent-first `URLClassLoader`. Only code that actually imports another plugin's classes breaks: Economy's Sheets backend (unreachable, since `MODE = Mode.Json` is a constant) and ChatLogger→SQLiteAPI (§2.3). MusicPlayer shades lavaplayer/lavasrc into its own jar, so it is unaffected; AudioAPI's opus-java/tink were never imported. Parent-first loading now prefers Core's copies of shared libraries (e.g. jsoup, commons-io). Missing hard dependencies are no longer enforced |
| C15 | Plugin validation | coreApi == `Version.CORE_API`, semver check, missing dependency fails the plugin, cycle fails those plugins | coreApi vs hard-coded "4.0"; missing dependencies not detected; a cycle aborts startup |
| C16 | Reload | stop+start incl. new JDA, re-reads `config.yaml` | stop+start incl. new JDA; **core config not re-read; StatusChanger dead afterwards** |
| C17 | Console logger | forwards slash/button/modal to configured channels | dead code |
| C18 | Web dashboard | started (Ktor, live config apply) | stub, not started |
| C19 | Logging | JLine-aware colored console appender | console appender class missing (§1.19) |
| C20 | Console | prompt `console > `, ^C keeps running, ^D stops | prompt `> `, any read exception silently ends console input |
| C21 | Startup listeners | plugin listeners added after ready (miss Ready/GuildReady) | added before ready (receive Ready/GuildReady) |
| C22 | Mongo document shape | `{_id, value, timestamp}` (+ list wrapper) | raw `T` documents; external Mongo supported |
| C23 | Interaction log text | `[CMD] user: <commandString with options>` | `[CMD] user: /<fullCommandName>` |
| C24 | Raw JDA events in plugins | every `listener=true` plugin object was registered with JDA | Only objects returned by `listeners()` are registered. **ChatLogger, DynamicVoiceChannel, Giveaway, MusicPlayer, Ticket and VoiceLogger declare `object Event : ListenerAdapter(), Plugin` and override `on…` methods but never return themselves from `listeners()`, so those handlers never fire**: message logging, voice logging, dynamic voice channels, MusicPlayer autocomplete, and guild-leave cleanup are all dead (`B:Plugins/*/Event.kt`; only AutoRole, TicketAddons and WelcomeByeGuild override `listeners()`) |
| C25 | Plugin load failure | an exception in any plugin's `load()` propagated out of `PluginLoader.run()` and stopped the whole bot | `discoverAndLoad` catches `Exception` per plugin and skips it (more robust). `Error`s such as `ExceptionInInitializerError` still escape, as do cycles |
| C26 | Localizer | typed `register.yaml` decoding, camelCase keys, NPE on missing key | KAML into `JsonElement` very likely throws for every file, so all command localizations are empty (§1.12) |

### 2.2 Pure refactors (no externally observable change on their own)

- Package and file moves (`builtin/*` flattened, `mongodb/CacheDbServer` → `database/DatabaseProvider` with identical embedded semantics and env vars).
- Moshi replaced by kotlinx-serialization for JSON. The format is the same *when* property names are unchanged and no `@Json(name=)` was used; the output is pretty-printed now.
- `ComponentIdManager` → `ComponentId` (same wire format).
- `GlobalUtil` → `JdaExtensions` (`isCommand/hasPrefix` with the *non-inverted* polarity). No plugin uses them, so this is dead code.
- Version bump to 4.0 (coreApi `4.0`), Kotlin 2.2.21 → 2.3.10, jda-ktx 0.13.0, Koin 4.2.0, mongodb-driver-kotlin-coroutine + bson-kotlinx 5.6.2. Gradle wrapper, build-logic, settings and Web-Dashboard sources are unchanged.
- IDE run configs (`.run/*.xml`) updated to `--log-level`. `.gitignore` adds `DevServer.bak/`.

### 2.3 Per-plugin behaviour (summary table, details below)

Resources (`info.yaml`, `config.yaml`, `lang/**`) and plugin build files are byte-identical on both refs, and all `ConfigSerializer` classes are unchanged. Existing v3 `plugins/<Name>/config.yaml` files therefore still load; only fresh installs hit C11. Every change listed below comes from the Kotlin sources plus the Core changes in §2.1.

| Plugin | Verdict | What users would see on B (beyond C3/C11 fresh-install failure and lost localizations) |
|---|---|---|
| AudioAPI | pure refactor | nothing; its library-provider role (opus-java, tink) is moot |
| GoogleSheetAPI | pure refactor | nothing; classes unreachable from Economy (whose Sheets mode is dead anyway) |
| SQLiteAPI | pure refactor (code) | same code, but its classes can no longer be reached by ChatLogger (C14) |
| _Example | behaviour change | `/example-command` never replies (v3 template); it teaches the broken patterns (ConfigLoader default, `fileGetter.export("lang/")`) |
| AutoRole | behaviour change | never assigns roles: GUILD_MEMBERS missing, so `GuildMemberJoinEvent` never arrives |
| BasicCalculator | behaviour change | `/basic-calculate` never answers (v3 templates); zh-TW name "告訴我" lost |
| BotInfo | behaviour change | `/bot-info` (still global) never answers; member totals may go stale without GUILD_MEMBERS *(unverified)* |
| ChatLogger | behaviour change | non-functional: the `setting` subcommand is never dispatched and the message listeners are unregistered. Settings inert after restart. SQLiteAPI classes are invisible, so `onUnload` can raise `NoClassDefFoundError` and abort `stop()` |
| DynamicVoiceChannel | behaviour change | inert: `bind`/`unbind` are subcommands (never dispatched) and the voice listener is unregistered. Generated-room tracking moved from Mongo to memory |
| Economy | behaviour change | balances change and **save** but every reply fails, so an admin who retries applies the change twice. 8 of 9 commands lose localization; leaderboard formatting regressed; legacy `data.json` migration changed |
| Feedbacker | behaviour change | forms cannot be sent or answered (`replyModal` after auto-defer). Forms still pending from v3 are **deleted on submit without being posted** |
| Giveaway | behaviour change | the creation wizard never appears, results are never shown, and auto-draw is silent. Join silently toggles (a second click un-joins) |
| IntervalPusher | nearly pure refactor | the first heartbeat is sent before the gateway connects, as "up" with `ping=-1` |
| MusicPlayer | behaviour change | commands mutate player state but never reply; panel buttons unrouted; autocomplete dead; voice likely fails without DAVE. `/queue` list, progress bar and many pre-checks removed |
| NtustCourse | behaviour change | subscriptions are in memory only (v3 wrote Mongo `NtustCourse.generated_cache`); stricter API JSON parsing |
| NtustManager | behaviour change | Mongo cache replaced by memory, so **every restart or reload re-posts all current announcements** (and re-spends Gemini quota). Announcements during the pre-JDA window are lost |
| SimpleCommand | behaviour change | all 5 commands delete their ephemeral reply and post nothing; zh-TW names lost |
| Ticket | behaviour change | the wizard is dead, existing panels cannot open tickets, and lock/delete/save are broken. Transcripts lose thread content; the UI is English-only |
| TicketAddons | behaviour change | the "not online" notice is never sent (template parse failure); presence status unreliable *(unverified)* |
| VoiceLogger | behaviour change | inert: the `setting` subcommand is never dispatched and the voice listeners are unregistered. Saved settings would stay inert after a restart even if wired (`ChannelData(null, …)`) |
| WelcomeByeGuild | behaviour change | welcome/bye messages dead (GUILD_MEMBERS; embed templates unparseable); bind/unbind still work on upgraded installs |

**Only the three API plugins are pure refactors at the code level** (AudioAPI, GoogleSheetAPI, SQLiteAPI), and IntervalPusher nearly so. All 17 other plugin modules change user-visible behaviour. Command names, option sets and component-id wire formats were preserved everywhere, so already-posted Ticket, Giveaway, Feedbacker, VoiceLogger and ChatLogger components still parse. The exception is MusicPlayer, whose prefix changed from `musicplayer@` to empty. The default English descriptions were shortened in Economy and MusicPlayer.

#### 2.3.A Ticket, TicketAddons, Feedbacker

- **Ticket**
  - **Commands.** `/create-ticket` and `/add-ticket message_id:STRING` (guild, admin) are unchanged. Localization keys `createTicket.*` don't match YAML `create_ticket.*`.
  - **Custom ids are unchanged.** Prefix `ticket@`, keys `a=action b=sub_action c=color_index d=user_id(LONG_HEX) e=msg_id f=btn_index`, so panels and buttons posted by v3 still parse:
    - panel: `ticket@a:press;f:<i>`
    - channel buttons: `ticket@a:{lock|unlock|save|delete};d:<hexUser>;e:<panelMsgId>;f:<i>`
    - save select: `ticket@a:save;b:select-channel;…`
    - submit modal: `ticket@a:submit;e:<msgId>;f:<i>`, input `reason`
    - wizard: `ticket@a:create;b:<step>[;c:1..4]`
    - Changed: preview modal `b:prev` → `b:preview-reason`.
  - **Auto-defer breaks every component path:**
    - Panel press: `replyModal` fails, so no one can open a ticket.
    - Lock/unlock: the permission override is applied, but the button never flips.
    - Delete: the chain starting with `deferEdit` fails at step 1, so the channel is never deleted.
    - Save: the channel-picker `reply` fails.
    - Wizard: every step fails.
  - **Templates.** All 7 message templates fail to parse, so `/create-ticket` and `/add-ticket` throw "Message not found". The 7 modal YAMLs are ignored; modals are hard-coded English with no max lengths, and reason/image became SHORT. Live preview (`tt@embed-demo`/`tt@btn-demo` models) and the customised panel are gone.
  - **Removed:** transcript thread flattening (`main Ticket.kt:518-689,719-754`), bot permission pre-checks, the category-exists check, and all zh-TW UI text (now English). `onGuildLeave` cleanup is dead (C24).
  - **Storage compatible:** `plugins/Ticket/data/<guildId>.json` = `{"<panelMsgId>":[{"reasonTitle","adminIds":[Long],"categoryId"}]}`.
  - **v3 bugs to fix in the port:**
    - The zh-TW btn-text modal id `modify-btn-content` never matches its handler.
    - Lock/unlock has no permission check.
    - `btn_index` drifts when buttons are added to existing messages.
    - The colour placeholder suggests "0x…" but the parser needs "#RRGGBB".
    - `embeds[0]` throws on messages without embeds.
- **TicketAddons.** Logic is identical and the listener *is* registered via `listeners()`. The only template, `not-online.yaml` (`title:{text}`), fails to parse, so nothing is ever sent. Without GUILD_MEMBERS, `retrieveMemberById` comes back without presence, so the user may always read as OFFLINE *(unverified)*. v3 bug: the guild filter `!isFromGuild && guild.id != cfg` never filters (it should use `||`).
- **Feedbacker**
  - `/feedbacker member:USER submit-channel:CHANNEL(TEXT)` (runtime ADMINISTRATOR check) is unchanged.
  - Ids `feedbacker@a:submit_star;b:<user>;d:<channel>;c:<1-5>` and modal `feedbacker@a:submit_form;c:<n>;d:<channel>` are unchanged, so old star buttons parse.
  - On B the admin path throws at `ask-message` (v3 template), and the star click's `replyModal` fails after auto-defer.
  - **Data loss:** a modal opened before the upgrade fails at its `deferEdit` chain on submit, but `event.message?.delete()` still runs, so the feedback is lost.
  - The modal is hard-coded English ("Feedback Form", required) instead of the zh-TW YAML (optional, max 1024).

#### 2.3.B Giveaway, Economy, GoogleSheetAPI

- **Giveaway**
  - **Command.** `/create-giveaway` (guild, admin) is unchanged.
  - **Ids are unchanged.** `giveaway@` with `a=action b=sub_action c=giveaway_id`: posts use `giveaway@a:{participate|draw|reroll};c:<16-hex>`, the wizard uses `giveaway@a:create;b:<step>`. Old posts still route.
  - **Modal text-input ids changed.** The single-field modals now use `value` instead of `title`/`description`/`end-time`/`sponsor`/`thumbnail`; `prize-name` and `winner-count` are kept. Modals are hard-coded English with no max lengths, and the description input became SHORT.
  - **Broken by auto-defer:** every `replyModal`, every ephemeral feedback `reply`, and the explicit `deferEdit`.
  - **Side effects still happen.** Join toggles and saves; draw and reroll draw and save, but nothing is shown.
  - **Templates.** `create-giveaway.yaml` and `giveaway-post.yaml` fail to parse, so `/create-giveaway` throws. The `ga@*` placeholders are never supplied.
  - **Removed:** the post embed builder (status, participants, prizes, winners), join/draw/reroll button models, `refreshMessage` (posts freeze; Join is never disabled), the draw-result reply, and `announceAutoDrawResult`. The auto-draw scheduler only marks giveaways ended and saves.
  - **Storage** (`plugins/Giveaway/data/<guildId>.json`, GiveawayInstance fields) is compatible. `onGuildLeave` is dead (C24).
  - **v3 behaviour to keep in the port:**
    - Join is a toggle; participant replies use the creator's `localeTag`.
    - Draw: creator or admin, after `endAt`, once. Reroll: admin only, after the draw.
    - Winner policies ALLOW_DUPLICATE and UNIQUE_ACROSS_PRIZES.
  - **v3 bugs to fix:** end time is parsed in the host timezone; the wizard relies on a 15-minute interaction token; the scheduler races with JDA threads.
- **Economy**
  - **Commands.** Nine flat guild commands: `balance [member]`, `top-money`, `top-cost`, and `add|remove|set-money|cost member value`. Admin is gated by config `admin_id`. Only `balance.*` keys still match; the other 8 commands lose localization. B also shortened their default English descriptions.
  - **Replies.** All 10 v3 templates fail to parse, so every reply throws, but value commands **persist before replying**. Retries double-apply.
  - **Leaderboard.** The row is hard-coded `"%index%. %name_mention% - %economy_board%"`, replacing the YAML `"%index%.\t%name_mention%\n%economy_board% 元\n\n"`.
  - **Button.** The `economy@` button now fails (`deferReply` after auto-defer).
  - **Storage.** `plugins/Economy/data/<guildId>.json` = `{"<userId>":{"cost":Int,"money":Int}}` is compatible. The legacy `data.json` is now always moved to `data.legacy.bak`; v3 migrated it into `<guildId>.json` when the bot was in exactly one guild.
  - **Concurrency.** Handlers now run concurrently with unsynchronized maps and file writes.
  - **v3 notes for the port:**
    - remove-money means spend (money −v, cost +v); negatives are allowed.
    - Every query saves a zero record.
    - The shipped config hard-codes two admin user IDs; don't ship that.
    - Values are 32-bit with no min/max.
    - Sheets mode is dead and buggy (`queryAll` swaps money and cost); don't port it.
- **GoogleSheetAPI:** pure refactor (only `Event` changed). The port should use a service account rather than installed-app OAuth on `port`.

#### 2.3.C MusicPlayer, AudioAPI, DynamicVoiceChannel, VoiceLogger

- **MusicPlayer**
  - **Commands.** 11 flat guild commands, unchanged: `join`, `disconnect`, `pause`, `resume`, `stop`, `queue`, `shuffle`, `now-playing`, `play query (autocomplete, max 500)`, `skip [count 1..50]`, `volume level 0..100 (autocomplete)`.
  - **Replies.** All 7 templates fail to parse, so each command acts, then never replies. The error wrapper "❌ 處理指令時發生錯誤…" was removed.
  - **Autocomplete** is dead (C24).
  - **Buttons.** v3 ids were `musicplayer@a:{previous|pause-resume|skip|loop|disconnect}`; the prefix came from v3's `name.lowercase()+"@"` fallback, since info.yaml has no `component_prefix`. On B the prefix is `""`, `components()` returns empty, and clicks are only auto-deferred. Old panels are dead.
  - **No DAVE.** `ff1b68f` says Discord rejects non-DAVE voice connections, so expect join/leave cycling.
  - **lavaplayer** is shaded into MusicPlayer's own jar, so the classloader change does not break it.
  - **Removed:** the `/queue` track list embed, the emoji progress bar and application-emoji lookup, scheme-less link detection, and many pre-checks (already paused/playing, `/stop` with nothing playing, the skip limit, shuffle needing ≥2 tracks, empty playlist, stage channel, connect failure). Hard-coded zh-TW strings became English.
  - **Kept:** history/Previous (5 s rule, max 240), single-track loop, shuffle after the current index, multi-skip, volume, one panel per user (5 s refresh, 60 s auto-delete).
  - **v3 bugs to fix:**
    - Button error paths edit the hook before acknowledging.
    - Panel lifetime is keyed on the interaction id, so it is never extended.
    - Scheduled futures leak.
    - Idle auto-leave is dead code.
    - Emoji `lateinit`s throw if application emojis are missing.
- **AudioAPI:** pure refactor; nothing imports its libraries.
- **DynamicVoiceChannel**
  - **Commands.** `/dynamic-voice-channel bind channel format-name-1 format-name-2` and `unbind channel` (admin) are subcommands, so they are never dispatched. Localization keys `dynamicvc.*` don't match the YAML.
  - **Events.** `GuildVoiceUpdate` and `GuildLeave` are never delivered (C24), so no rooms are created or cleaned up.
  - **Storage, bindings:** `plugins/DynamicVoiceChannel/data/<guildId>.json` = `[{"categoryId","defaultName","formatName1","formatName2"}]` is compatible.
  - **Storage, generated rooms:** v3 tracked them in Mongo, database `DynamicVoiceChannel`, collection `generated_cache` (MemoryCacheDb: `{_id:"<voiceChannelId>", value:<ownerId Int64>, timestamp}`). B keeps an in-memory map (the TODO) and ignores the old documents, so rooms created before a restart become orphans.
  - **Removed:** startup validation and pruning of bindings. `depend_plugins: SQLiteAPI` is unused on both refs; v3 still required it.
  - **v3 behaviour to keep:** a binding is keyed by (categoryId, lobby name). On the first join the lobby is cloned to position 0 and the original is renamed with format-name-1 (`%dvc@custom_name%` = the display name before " - "). The joiner gets MANAGE_CHANNEL and MANAGE_PERMISSIONS. Tracked rooms are deleted when they empty.
  - **v3 bugs to fix:**
    - format-name-2 is unused.
    - `addData` appends duplicates.
    - `removeGuild` never matches.
    - The channel option is not restricted to voice channels.
- **VoiceLogger**
  - **Command.** `/voice-logger setting` is a subcommand, so it is never dispatched.
  - **Ids are unchanged:** `voice-logger@a:{toggle_btn|modify_allow_btn|modify_block_btn|delete_btn|modify_allow_menu|modify_block_menu}`. B registers handlers, but `editMessage` and `deferEdit` chains fail after auto-defer.
  - **Templates.** All 10 fail to parse. `placeholder.yaml` (allow/block list formats) is no longer read, and `%channel_name%` is no longer supplied.
  - **Storage.** `plugins/VoiceLogger/setting/<guildId>.json` = `{"<listenChannelId>":{"allow_mode","allow":[Long],"block":[Long]}}` is compatible, but B builds `ChannelData(null, …)` at init, so saved settings never match after a restart. Voice events are not delivered at all (C24).
  - **v3 behaviour to keep:**
    - The listen channel is the one where `setting` ran.
    - ALLOW mode logs only listed channels, with categories expanding to their children; BLOCK mode logs everything except the listed ones.
    - A switch is logged if either side matches.
    - Status events split into new, update and delete.
  - **v3 bugs to fix:**
    - The switch template uses an unsupplied key.
    - `?: return` skips the remaining listen channels.
    - Init mutates the map while iterating it.
    - The audit log `it[0]` throws when there are no entries.

#### 2.3.D WelcomeByeGuild, SimpleCommand, AutoRole, BotInfo, BasicCalculator, _Example

- **WelcomeByeGuild**
  - **Commands.** `welcome-channel-bind [channel]`, `welcome-channel-unbind`, `bye-channel-bind [channel]`, `bye-channel-unbind` (admin; flat, so they dispatch). Keys `welcomeChannelBind.*` don't match `welcome_channel_bind`.
  - **Events.** The listener is registered, but join/remove need GUILD_MEMBERS, so there are no welcome/bye messages. Even with the intent, the `welcome`/`bye` embed templates fail to parse.
  - **Placeholders.** The B substitutor factory reimplements only part of the `wbg@` keys. The shipped templates use 4 keys B no longer sets: `wbg@user_effective_name`, `wbg@user_avatar_url`, `wbg@guild_icon_url`, `wbg@guild_rules_channel_mention`. Unset channel ids now render "-" instead of "0".
  - **Storage.** `plugins/WelcomeByeGuild/data/<guildId>.json` = `{welcomeChannelId, byeChannelId}` is compatible. Bind/unbind (`content:`-only templates) still work on upgraded installs.
- **SimpleCommand.** 5 fixed flat commands with no options (admin default permission): `cub-none-card`, `tsib-none-card`, `ctcb-none-card`, `ctcb-remit`, `chpytwtp-remit`. B queues `hook.deleteOriginal()` before building the (unparseable) template, so the ephemeral reply vanishes and nothing is posted. v3 posted a public embed in the default zh-TW locale; the templates contain bank account data.
- **AutoRole.** Config `guilds[{guild_id, role_ids}]` is unchanged. The join listener never fires (GUILD_MEMBERS). B improves role resolution (lazy, from `event.jda`). v3 note: `modifyMemberRoles(member, roles)` *replaces* the whole role set; the port should add roles instead.
- **BotInfo.** `/bot-info` stays global; the `bot-info.yaml` template fails to parse. v3 leaked the counts into the global substitutor; B keeps them local.
- **BasicCalculator.** `/basic-calculate formula` never answers.
  - Both refs share the `bc_answer_round` bug (`split('.', limit = 1)`).
  - v3 evaluator quirks to port deliberately (identical on B):
    - Implicit multiplication (`2(3)`, and even `2 3` → 6).
    - Unary minus gets binary precedence (`2*-3` = -3).
    - `^` is left-associative and its exponent is truncated.
    - Division runs at scale 10, the result at 5 decimals HALF_UP.
    - ArithmeticException goes unanswered.
    - `9^999999999` is a DoS.
- **_Example.** Matches the B README skeleton (`object Event : Plugin`, `PluginContext.onLoad()`, `commands()`). It shows none of `components()`, `listeners()`, ComponentId, placeholders, Koin or `onUnload`, and it uses the broken resource patterns.

#### 2.3.E NtustManager, NtustCourse, IntervalPusher, ChatLogger, SQLiteAPI

- **NtustManager** (no commands, components or lang; config keys `enabled`, `fetch-interval` ≥60, `api-keys`, `prompt` unchanged)
  - **Persistence dropped.** v3 used Mongo database `NtustManager`, collection `current_announcement_lists`: `{_id:"<AnnouncementType>", value:{items:[{type,url,title}], itemTypeName:"…AnnouncementLink"}, timestamp}`. It also kept `announcement_data`: `{_id:"<TYPE>_<id|url>", value:{link,title,content,releaseDate,fetchedTimestamp}, timestamp}`, which was write-only. B holds everything in an in-memory `ConcurrentHashMap` (TODO). `DatabaseProvider` is imported but unused.
  - **Visible effect: every start or reload re-posts all announcements on all 18 boards.** Each one also goes through Gemini again, burning API quota.
  - **Timing.** The scheduler starts inside `onLoad` with initial delay 0, i.e. before JDA exists. The JDA lookup (Koin) or `getGuildById(...)!!` fails, the item is still marked as seen, and that announcement is silently lost.
  - **Unchanged logic:** parser, Gemini service (gemini-2.5-flash, temp 0.1, 10 req/min per rotating key, retry backoff 1/5/15/30 min), HtmlMinifier, URL rules, message splitting (1950/1980). The LOC drop is mostly comments and the cache rewrite.
  - **Port notes:**
    - Persist the per-board URL sets and seed them silently on first run; don't mark failures as seen.
    - Keep the scraping rules: the `【處本部】` filter, the board-specific columns, `div#Dyn_2_3.M23` → `div.M23`, and title-plus-link only for non-NTUST URLs.
    - Guild and channel IDs are hard-coded in `AnnouncementTypes.kt`.
    - v3 dashboard reload double-schedules the task.
- **NtustCourse**
  - `/course-add id`, `/course-remove id`, `/course-list` (flat, guild) are unchanged and dispatch fine.
  - v3 kept registrations in Mongo `NtustCourse.generated_cache`, `{_id:"user_record_map", value:{"<courseId>":{"<channelId>":["<userId>"]}}, timestamp}`. B keeps them in memory, so they are lost on restart. v3 probably never read them back either, because Moshi rejects `HashMap` *(inferred)*.
  - CourseApi moved from Moshi to kotlinx; the API's `OnleyNTUST` typo is kept. kotlinx no longer coerces an unquoted number into a String field (`Restrict2`), so monitoring could stop silently *(unverified)*.
  - Port notes: `Available` re-notifies on every ~1.5 s poll; semester "1142" and the date gate are hard-coded; v3 `/course-remove` drops every user subscribed to that course in the channel.
- **IntervalPusher.** Nearly a pure refactor. The pushers start in `onLoad`, so the first heartbeat goes out as "up" with `%ping%`=-1 before the gateway connects (v3 started after ready). Port notes: a 404 permanently stops that pusher; 521 only warns.
- **ChatLogger: non-functional on B**
  - **Command.** `/chat-logger setting` is a subcommand, so it is never dispatched. Keys `chatLogger.*` don't match `chat-logger.*`.
  - **Events.** The message listeners are unregistered (C24), so nothing is logged at all.
  - **Ids are unchanged** (`chat-logger@a:{toggle_btn|modify_allow_btn|modify_block_btn|delete_btn|modify_allow_menu|modify_block_menu}`), but the handlers' `deferEdit`/`editMessage` calls fail after auto-defer.
  - **Templates.** All 6 fail to parse. `placeholder.yaml` (allow/block formats) is no longer read.
  - **SQLite schema is unchanged:** `plugins/ChatLogger/data/<guildId>.db`, one table per channel `'<channelId>'(message_id INT PK, user_id INT, message TEXT, update_count INT)`.
  - **Settings** `plugins/ChatLogger/setting/<guildId>.json` = `{"<listenChannelId>":{"allow_mode","allow","block"}}` are compatible but inert after a restart (`ChannelData(null, …)`).
  - **Removed:** startup pruning. The Delete button no longer really deletes (the cached `JsonFile` resurrects it).
  - **Classloader.** `DbManager` uses SQLiteAPI's `SQLiteFileManager`, which B's isolated loader cannot see. When `data/*.db` exist, `onUnload` raises `NoClassDefFoundError`/`ExceptionInInitializerError` (an `Error`, not an `Exception`). That escapes `unloadAll`, aborting `BotApplication.stop()` before JDA shuts down, so a console `reload` probably ends the process *(sequence unverified)*.
  - **Bot filter.** B skips all bots and webhooks; v3 skipped only its own messages.
  - **v3 bugs to fix in the port:**
    - With `log_all=false`, new channels never start logging.
    - Fields over 1024 characters throw.
    - User text runs through StringSubstitutor (placeholder injection, infinite-loop error).
    - `return` inside `forEach` aborts the remaining sends.
    - Connection keys mismatch, so DBs are never closed or deleted.
    - A new channel's allow/block mode flips after restart.
- **SQLiteAPI.** Same code (`Class.forName("org.sqlite.JDBC")` in `onLoad`). It is a pure refactor in itself, but as a shared API it no longer works under B's classloader. A Python port can use stdlib `sqlite3`/`aiosqlite` instead.

---

## 3. Implementation vs spec (`main:docs/specs/2026-04-07-v4-core-refactor-design.md`; the branch still has it under `docs/superpowers/specs/`)

### 3.1 Implemented as specified (or close)

- Dependency upgrades (§2): Kotlin 2.3.10, jda-ktx, Koin, coroutine Mongo driver, Moshi removed, JDA 6.4.1 kept, version 4.0.
- Package structure (§3.1): every listed file exists (plus `JsonFile.kt`, `LocaleUtil.kt`, `builtin/*`, dashboard stub).
- "Removed from Core" list (§3.2): all removed. MessageCreator **v2 and ModalCreator** were removed as well.
- `BotApplication` with start/stop/reload = stop+start (§3.4). `Plugin` interface (§4.1), plus `var config` and `listeners()`. `PluginConfig` (§4.2).
- `ComponentRegistry` by prefix (§5.2) and a central listener (§5.3). `DatabaseProvider`/`Collection`/`GuildCollection`/`DatabaseConfig` (§6). `Localizer`/`LocaleMap`/`MessageTemplate` classes (§7). Builder-style `Substitutor` (§8).

### 3.2 Not implemented or deviating

| Spec item | Status on B |
|---|---|
| §1/§4 "Koin module-based plugins, no reflection, ServiceLoader or Koin instantiation" | Reflection (`INSTANCE`/constructor); no plugin defines Koin modules |
| §1 "natural hot-reload via load/unloadKoinModules" | Only a full restart; `reloadPlugin`/`reloadAll`/`onReload` are dead code |
| §3.3 "start services (injected)" | `BotApplication` and `ConsoleManager` are built manually |
| §4.3 step 3 "validate coreApi compatibility" | Against a hard-coded `"4.0"` fallback, not `Version.CORE_API` |
| §4.3 step 5c "onLoad after Koin module installed, **JDA ready**" | onLoad runs before JDA is built |
| §5.1 dispatch keyed by `fullCommandName` | Keyed by top-level name, so subcommands break; DSL `slashCommand("economy","balance")` missing |
| §5.3 defer only slash commands in central listener | InteractionLogger also defers every component |
| §7.1 "fails explicitly on missing keys" | Silent empty strings |
| §7.2 MessageTemplate supports **modal templates**; §11 "YAML templates format stays" | No modal templates; incompatible schema; resources not migrated |
| §8 placeholder rewrite | Done, but most keys dropped |
| §9.3 `xs-plugin` adds Koin compileOnly | Not changed (plugins get Koin transitively via Core `api`) |
| §10 checklist: `class XxxPlugin : Plugin` | Plugins remain `object Event : Plugin` |
| §10 `.complete()` → `.await()` | jda-ktx `await()` is used nowhere; Core uses blocking `awaitReady()` |
| §10 `CacheDbManager` → `DatabaseProvider.collection<T>()` | No `collection<T>()` helper; DynamicVoiceChannel went in-memory; Ntust* have TODOs |
| §11 "info.yaml format unchanged" | `prefix`, `depend_jars`, `soft_depend_jars` dropped (strict parse) |
| §12 "Plugin business logic changes out of scope" | Violated: large feature deletions (§2.3) |
| §1 Dashboard "skeleton only" | First a Ktor skeleton (6cf69b8), then replaced by a no-op stub (a454196) |

### 3.3 Half-finished parts and TODOs

- TODOs added: `B:Plugins/DynamicVoiceChannel/.../DynamicVoiceChannel.kt:23` ("MongoDB cache replacement - using in-memory map for now"), `B:Plugins/NtustCourse/.../NtustCourse.kt:22` ("Migrate MongoDB cache access to v4 DatabaseProvider pattern"), `B:Plugins/NtustManager/.../AnnouncementCacheManager.kt:12` ("Migrate from old CacheDbManager to v4 DatabaseProvider"). Pre-existing: `MusicPlayer/.../HistoryIndexManager.kt:175`. Main's `Ticket/.../StepData.kt:124` TODO disappeared together with the file content.
- Wired but unused: `ConsoleLogger.log*`, `AppEmoji`, `BotConfig.autoDeferReplies`, `DatabaseConfig.port`, `Arguments.noOnline/ignoreUpdate/forceRenewLangResources`, `PluginRegistry.reloadAll/reloadPlugin`, `Plugin.onReload`, `JdaExtensions.*`, `Localizer.has`, `GuildCollection` (unused by plugins), `koin-ktor`/`koin-test` catalog entries, the `:WebDashboard` dependency.
- History: the whole rewrite was written on 2026-04-07 between 20:46 and 21:40 (Core rewrite, then "resolve all compilation errors", then "migrate all 22 plugins", then "resolve all compilation errors across plugins"), with review fixes on 04-08. Only the README was touched in July. "22 plugins" is a miscount: `settings.gradle.kts` includes 21 plugin modules (18 feature, including `_Example`, plus 3 API).

### 3.4 Compile and runtime risks

- **Compile**: commits `a454196` and `a13079a` claim all compilation errors were fixed. Gradle was not run here, so a clean build is *(unverified)*. Plugin-specific compile concerns are in §2.3.
- **Runtime (Core)**, by severity:
  1. Subcommand dispatch (C9).
  2. Plugin `ListenerAdapter` overrides never registered (C24).
  3. Component auto-defer vs modals and replies (C8); no flag setting fixes it.
  4. Core-resource shadowing in `ConfigLoader` and `FileGetter`; no lang export (C3, C11).
  5. v3 YAML unparseable by `MessageTemplate`; template ids unparseable by `ComponentId`; no modal templates (C12).
  6. `Localizer` KAML→`JsonElement` failure (C26).
  7. Missing `GUILD_MEMBERS` intent (C5).
  8. No DAVE (C7).
  9. `onLoad` before JDA/Koin JDA (C10): NtustManager loses posts, IntervalPusher sends a fake heartbeat.
  10. Isolated classloaders (C14): ChatLogger `NoClassDefFoundError` in `onUnload` can abort `stop()`.
  11. `logback.xml` class names (C19).
  12. StatusChanger dead after reload (C16).
  13. The core config schema changed with no migration (C1).
  14. Data races: handlers on `Dispatchers.Default` mutate plain maps (`GuildJsonFile.cache`, plugin state).
  15. `JsonFile` overwrites corrupt files with defaults, and a deleted-but-cached `JsonFile` resurrects data (ChatLogger, VoiceLogger, DynamicVoiceChannel).
  16. Koin module and classloader leak when `onLoad` throws.
  17. A cycle in `depend_plugins` aborts startup.
- **Persistence regressions:** DynamicVoiceChannel generated rooms, NtustCourse subscriptions and the NtustManager seen-announcement lists all moved from Mongo to memory (TODOs). Settings for VoiceLogger and ChatLogger are loaded with a null guild and are inert after a restart.

### 3.5 Tests

None on either ref: no `src/test` directories and no `testImplementation` dependencies. `koin-test` is declared in `libs.versions.toml` but never used.

---

## 4. `CLAUDE.md` and `PROJECT_CONTEXT.md` (both added on B in `a454196`, 2026-04-07)

Both files entered the branch inside "fix(Core): resolve all compilation errors". They were apparently untracked local files swept in by that commit *(unverified)*. Neither exists on main. Their content describes **v3**, not the code on the branch.

### 4.1 `B:CLAUDE.md` (64 lines): key content

- **Build**: `./gradlew` (default task `build`, outputs to `./DevServer/`), `./gradlew :Core:build`, `./gradlew :PluginName:build`, `-PoutputPath=/path`. Core shadow jar goes to `DevServer/`, plugin jars to `DevServer/plugins/`. Version = root major/minor/snapshot + module `version.patch`. "Java 21 toolchain is required".
- **Runtime flow**: `MainKt.main()` → `CacheDbServer` → `BotLoader.start()` → `PluginLoader.preLoad()` (scan jars, info.yaml, aggregate intents) → JDA → `PluginLoader.run()` (`load()`, collect commands, register) → every slash command auto-`deferReply(true)` via `InteractionLogger`.
- **Plugin contract**: entry must be a Kotlin `object` (`INSTANCE`); extend `PluginEvent`/`PluginEventConfigure<C>`; override `load()/unload()/reload()/guildCommands()/globalCommands()` and JDA listener methods; route with `GlobalUtil.checkCommandString(event, "name")`.
- **Conventions**: package prefixes `tw.xinshou.discord.plugin` / `tw.xinshou.discord`. Resources `info.yaml`, `config.yaml` (exported to `plugins/<name>/`), `lang/`. Convention plugins `xs-plugin`, `xs-plugin-shadow`, `xs-jvm-conventions` (token expansion `${author} ${name} ${coreApi} ${version}`). New-plugin steps (module, `version.patch`, settings include, info.yaml `main`, `compileOnly(project(...))` + `depend_plugins`).
- **Data layer**: `CacheDbManager` → `MemoryCacheDb`/`DirectCacheDb`; `JsonFileManager`/`JsonGuildFileManager`; `MessageCreator`/`ModalCreator` + `Placeholder`; `ComponentIdManager`. Catalog: JDA 6.x, Kotlin 2.2.x, kotlinx-serialization, KAML, Moshi, embedded Mongo, Ktor.

### 4.2 `B:PROJECT_CONTEXT.md` (358 lines, zh-TW, "analysis date 2026-02-15", derived from code)

Mermaid diagrams of the Core/Plugin relationship and the startup sequence. The build-logic description (toolchain 21, version generation, info.yaml expansion, jar manifest). Dependency isolation (compileOnly vs `depend_plugins`, kept in sync by hand). Core details: `PluginLoader` steps, a **single shared ClassLoader** with resource remapping, lifecycle (`BotLoader.reload()` = PluginLoader.reload + SettingsLoader + StatusChanger, "does not rebuild JDA"), event dispatch (JDA broadcast, each plugin filters), data flow (config export, `lang/` export, `StringLocalizer`, `CacheDbServer` with Memory/Direct cache, JSON managers, templates, `ComponentIdManager`), key interfaces, rules for new plugins, a plugin catalogue (3 API + 17 feature plugins), and a "limitations" list.

### 4.3 Staleness

| Statement | vs main (v3.4 code) | vs B (v4 code) |
|---|---|---|
| CLAUDE: "Java 21 toolchain is required"; PROJECT_CONTEXT: toolchain 21 | **Stale**: toolchain 25 since `19ca8b5` (2026-04-07) | **Stale** (25) |
| CLAUDE: `./gradlew :PluginName:build` | Likely wrong: project paths are `:Plugins:<Name>` / `:Plugins:API:<Name>` (see `compileOnly(project(":Plugins:API:AudioAPI"))`) *(unverified without Gradle)* | same |
| CLAUDE: runtime flow (`CacheDbServer` → `BotLoader` → `PluginLoader.preLoad/run`, auto-defer slash) | Accurate (omits dashboard start and `--no-auto-defer-interactions`) | **Stale**: `DatabaseProvider` → `BotApplication` → `PluginRegistry`; onLoad before JDA; components also deferred |
| CLAUDE: `PluginEvent`/`PluginEventConfigure<C>`, `load/unload/reload/guildCommands/globalCommands`, `GlobalUtil.checkCommandString` | **Accurate** (`main:Core/.../plugin/PluginEvent.kt`, `util/GlobalUtil.kt`) | **Stale**: files deleted; `Plugin` interface instead |
| CLAUDE: entry must be Kotlin `object` | Accurate | Stale-ish: object **or** no-arg class |
| CLAUDE: data layer (CacheDbManager, JsonFileManager, MessageCreator/ModalCreator, ComponentIdManager); catalog "Kotlin 2.2.x, Moshi" | Accurate | **Stale**: DatabaseProvider/Collection, JsonFile, MessageTemplate (no modals), ComponentId; Kotlin 2.3.10, no Moshi, plus Koin/jda-ktx |
| CLAUDE: config.yaml "exported to plugins/<name>/config.yaml" | Accurate | Broken in code (§1.11) |
| PROJECT_CONTEXT: single shared `ClassLoader`, `ClassLoader.addJar`, `findResource` remap | **Stale**: per-plugin `PluginSandboxClassLoader` with dependency loaders since `9d5d604` (2026-02-17) | **Stale**: per-plugin plain `URLClassLoader` |
| PROJECT_CONTEXT: `BotLoader.reload()` does not rebuild JDA | **Stale**: reload = stop()+start(), rebuilds JDA since `494607f` (2026-02-17) | Stale (BotApplication full restart) |
| PROJECT_CONTEXT: coreApi/version not validated | **Stale**: validated since `9d5d604` | Partly (coreApi vs hard-coded "4.0", no version check) |
| PROJECT_CONTEXT: `prefix`/`component_prefix` unused by Loader | **Stale**: loader sets both (normalised `name.lowercase()+"@"`) | `prefix` dropped; `component_prefix` used only for deregistration |
| PROJECT_CONTEXT: `settings.gradle.kts` includes Core + 20 plugin modules; catalogue lacks WelcomeByeGuild | **Stale**: 21 plugin modules (WelcomeByeGuild added `3c9a69c`, 2026-02-21) plus WebDashboard | same |
| PROJECT_CONTEXT: `MessageCreator` at `builtin/messagecreator/MessageCreator.kt` | **Stale path**: `…/messagecreator/v1|v2/MessageCreator.kt`, `…/modal/ModalCreator.kt` | Deleted |
| PROJECT_CONTEXT: `UpdateChecker` disabled by `|| true` | Accurate | UpdateChecker deleted |
| PROJECT_CONTEXT: `run()` uses `pluginQueue.values.reversed()` (dependents load first) | Accurate | Different: topological order (dependencies first) |
| PROJECT_CONTEXT: InteractionLogger defers every slash command | Accurate (configurable since 2026-02-17) | Stale: also defers components |
| PROJECT_CONTEXT: no dashboard mentioned | Stale (dashboard since `1e54508`, 2026-02-16) | Dashboard is a stub |
| Branch README: "JDK 21 以上" / Java 21+ badge | Stale (25) | Stale (25) |
| Branch README: first run generates `config.yaml` | True on main | **False on B** (crash, §1.11) |
| Branch README: `--ignore-update` skips the version check; `-N` offline; `-Flang` re-exports | `-N` and `-Flang` true; the version check is disabled anyway | Flags parsed but do nothing |
| Branch README: `auto_defer_replies` config | n/a | Key never read |
| Branch README: Web-Dashboard "網頁管理介面" | True | Not started on B |

### 4.4 README vs CLAUDE.md: which describes which code?

- **Branch `README.md` matches the branch code.** `object Event : Plugin { override lateinit var config: PluginConfig; override fun PluginContext.onLoad(); override fun commands(): List<CommandHandler> }` is exactly `B:Core/.../plugin/Plugin.kt`, and every B plugin is written as `object Event : Plugin` (e.g. `B:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/Event.kt`). It was rewritten on 2026-07-19 (`1a608df`) against B (CLI table with `--log-level`, new config schema).
- **`CLAUDE.md` (and `PROJECT_CONTEXT.md`) match main's code.** `PluginEvent`/`PluginEventConfigure<C>`, `load()/unload()/reload()/guildCommands()/globalCommands()` and `GlobalUtil.checkCommandString` exist only on main (`main:Core/src/main/kotlin/core/plugin/PluginEvent.kt`, `main:Core/src/main/kotlin/core/util/GlobalUtil.kt`). They were deleted on B by `6cf69b8`/`6e7d9dd`. CLAUDE.md was committed onto B *after* the Core rewrite (`a454196`) without being updated, which is why the branch contradicts itself.
- For the Python port: treat CLAUDE.md/PROJECT_CONTEXT.md as (partly stale) documentation of the **v3 baseline**, and the branch README as documentation of the abandoned v4 design.

---

## 5. Lessons for the Python 3.14 + discord.py design

The baseline contract is **main**: its commands, custom_ids, YAML files, config keys, data files and DB documents. v4 is useful as a picture of the code shape the author wanted, and as a list of traps.

### 5.1 Worth carrying over (with the discord.py mapping)

| v4 idea | Why keep it | Python / discord.py form |
|---|---|---|
| Plugin declares its surface (`commands()`, `components()`, `listeners()`, `onLoad/onUnload`) instead of each plugin being a global listener that filters every event | Removes v3's `checkCommandString` boilerplate and inverted-boolean bugs | One `commands.Cog` per plugin (`app_commands` commands/groups, `@commands.Cog.listener()`, `async cog_load/cog_unload`). Extensions loaded with `await bot.load_extension()` in `setup_hook`; `reload_extension()` gives the per-plugin hot reload v4 never reached |
| Exact command-path dispatch (`fullCommandName`) | v4 got the idea right but keyed it wrong | `app_commands.CommandTree` already dispatches groups/subcommands. Add a test asserting that every command path in the tree has a callback |
| Prefix-routed component registry | Persistent buttons must survive restarts | `discord.ui.DynamicItem` (discord.py ≥ 2.4) with a regex `template` + `bot.add_dynamic_items(...)`. Keep the **v3 wire format** `{prefix}{a}:{v};{b}:{v}` (letters in v3 `idKeys` order; hex for INT/LONG) so already-posted Ticket/Giveaway/Feedbacker/VoiceLogger buttons keep working. Write one codec with round-trip tests against real v3 ids |
| Typed config models with defaults (`@Serializable`) | Validation and self-documentation | pydantic v2 (or msgspec) models per plugin and for Core. Unknown keys **warn**, not crash. Explicit migration from v3 Core config (`general_settings`/`builtin_settings`). Export defaults with `importlib.resources` from the *plugin's own* package, only when the file is missing; honour `--force-renew-lang-resources` |
| `JsonFile` / `GuildJsonFile` abstraction | v3 data is already per-guild JSON | One store class: `asyncio.Lock` per file, atomic write (tmp + `os.replace`), and never overwrite a file that failed to parse (rename it `.corrupt`). Field names = v3 Moshi names (Kotlin property names unless `@Json(name)`), compact JSON |
| `DatabaseProvider` with embedded/external switch | Production may want an external DB | Python has no practical embedded Mongo. Either an external MongoDB (PyMongo async API / Motor) that **reads v3 documents** `{_id, value, timestamp}` incl. `{items, itemTypeName}` list wrappers, or SQLite (`aiosqlite`) plus a one-time importer from `mongodb-data`. Decide per plugin (only DynamicVoiceChannel, NtustCourse, NtustManager use Mongo on main) |
| `Localizer` flattening raw YAML keys | Simpler than v3 reflection over typed classes | `app_commands.Translator` fed from `lang/<locale>/register.yaml`. **Fail at startup** if a name/description key is missing or violates Discord's name rules; never fall back to `""` |
| Builder-style `Substitutor` | Readable call sites | Keep the builder, but implement the **full v3 key set** (incl. `member_fixed_name`, `language`, `channel_category_name`, `component_*`, guild/user/member/event families with prefixes and `"-"` none-values) and commons-text semantics (`%key%`, `$` escape, unknown key left as-is) |
| Plugin manifest + topological order | Explicit dependencies and intents | Keep a manifest (name, version, intents, depends/soft-depends). Do the topological sort *and* v3's missing-dependency check; a cycle fails only the plugins involved. "API plugins" (SQLiteAPI, GoogleSheetAPI, AudioAPI) become ordinary library dependencies |
| External DB and per-guild collections in Core | Good separation | Keep it optional. Core should not force a DB on plugins that only need JSON |

### 5.2 Problematic or over-engineered: do not copy

1. **DI container (Koin).** No plugin defined a module. The only uses were service-locator lookups (`get<JDA>()`), and those broke because JDA was registered after `onLoad`. Python: pass a small frozen `BotContext` (bot, core config, data paths, db, logger) to each plugin. No container.
2. **Classloader isolation and "API plugins".** v3 needed a dependency-aware sandbox loader; v4 simplified it and broke ChatLogger→SQLiteAPI (and Economy's dormant Sheets backend). MusicPlayer survived only because it shades its own audio libraries. Python has a single import system, so model these as normal dependencies.
3. **Central auto-defer of every component** (`deferEdit`). It makes `send_modal` and ephemeral follow-ups impossible. Copy **v3**: defer only slash and message-context commands (configurable), or better, let each handler choose, plus a helper that defers if the handler has not responded within about 2s.
4. **Rewriting the template schema without migrating the shipped YAML**, then parsing it strictly. The v3 YAML (`!ButtonsComponent` tags, `uid` maps, `model_key` models, `title: {text,url}`, `image_url`, `color_code`, `timestamp`, Components V2, `modal/*.yaml`) *is* the contract. Implement that schema (PyYAML/ruamel custom tag constructors) and add golden tests that render every shipped YAML in en-US and zh-TW.
5. **Silent degradation**: empty localization strings, `%key%` leaks, `"Message not found"` at click time, CLI flags and config keys that are parsed and ignored. Validate everything at startup and fail loudly per plugin.
6. **"Reload" = full gateway reconnect**, which also leaks cancelled scopes (StatusChanger) and keeps a stale core config. Use `reload_extension` per plugin, re-read config, and cancel/recreate `tasks.loop`s in `cog_unload/cog_load`.
7. **Running plugin init before the client is ready while plugins need it.** In discord.py, register cogs and commands in `setup_hook`, and gate cache-dependent work with `await bot.wait_until_ready()` or `on_ready`.
8. **Two listener styles at once.** v4 kept `object Event : ListenerAdapter()` overrides that were never registered (C24). With Cogs there is one way to listen; add a test that every plugin's expected events are subscribed.
9. **Intents implied by builder presets.** Compute `discord.Intents` explicitly. Base = v3 (members, guild_scheduled_events, emojis_and_stickers, plus guilds), then the union of plugin needs (voice_states, guild_messages, message_content, presences). Document the privileged ones.
10. **Big-bang "architecture-only" migration that deleted business logic.** Port plugin by plugin with parity tests: slash-command definition snapshots (names, options, localizations, default permissions, guild vs global), custom_id codec round-trips, template rendering, and storage read/write against copies of production data files.
11. **Config/logging resources that reference code by name** (logback.xml → renamed classes). Configure logging in code (`logging.config.dictConfig`) under test.

### 5.3 v3 behaviour to preserve in the port (surfaced by this comparison)

- Core config keys and defaults (§2.1 C1). CLI `--token/-t`, `--level/-l` (also accept `--log-level`), `--no-online/-N` (start DB, dashboard and console without connecting), `--force-renew-lang-resources/-Flang`, `--[no-]auto-defer-interactions`. `--ignore-update` is a no-op on main.
- Gateway: GUILD_MEMBERS + SCHEDULED_EVENTS + GUILD_EXPRESSIONS + plugin intents; member cache OWNER+VOICE+plugin policies. **Voice E2EE (DAVE)**: v3 enabled it on 2026-04-07. discord.py added DAVE support in 2.7.0 per its changelog, so pin ≥ 2.7 for MusicPlayer.
- Plugin `load()` after the gateway is ready. Guild commands pushed to all guilds and on guild join; global commands registered separately.
- Console logger forwarding (`console_loggers`). Note v3's bug: modal events are logged with `cl_type` "BTN". StatusChanger `TYPE;text;delayMs` (v3 STREAMING misuses field 3 as both URL and delay; fix it).
- Web dashboard (v3 `CoreDashboardBackend`: masked core config view/save, plugin list, enable toggle, plugin YAML edit, per-plugin strict reload) if production uses it.
- Embedded-Mongo env vars `XS_MONGODB_PORT`, `XS_MONGODB_DB_PATH`, `XS_MONGODB_INSTANCE` (only relevant if Mongo stays).
- Per-plugin "keep" and "fix in the port" notes (main semantics and main bugs found during the comparison) are in §2.3.A–E. Notable items:
  - Ticket transcript flattening.
  - Giveaway winner policies.
  - VoiceLogger and ChatLogger allow/block semantics.
  - The BasicCalculator evaluator quirks.
  - AutoRole replacing the whole role set.
  - Economy remove-money meaning spend.
  - The NtustManager scraping rules.
  - DynamicVoiceChannel room lifecycle.
  - MusicPlayer history and panel rules.
