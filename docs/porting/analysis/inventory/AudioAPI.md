# AudioAPI: porting inventory (branch `main`, HEAD 3a59607)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`.

- `core:` = `Core/src/main/kotlin/core/`
- `log:` = `DevServer/log/output.log` (a real run on 2026-04-07)

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/API/AudioAPI` |
| Kotlin files / LOC | **1 file, 6 lines (3 code lines)**: `src/main/kotlin/api/audioapi/Event.kt` |
| Purpose | A "library plugin" with **no behaviour**. It (a) bundles `club.minnced:opus-java:1.1.1` and `com.google.crypto.tink:tink:1.20.0` into its shadow jar as `api` dependencies (`build.gradle.kts:5-8`), (b) contributes voice-related gateway, cache and member-cache requirements through `info.yaml`, and (c) acts as a load gate: MusicPlayer declares it in `depend_plugins`. README describes it only as "音頻處理功能" (audio processing), at `README.md:101`. |
| Entry object | `object Event : PluginEvent(false)` (`Event.kt:6`), package `tw.xinshou.discord.plugin.api.audioapi` |
| Listener flag | `false`, so it is **not** registered as a JDA listener |
| info.yaml | `author/name/coreApi/version` are Gradle-expanded (`name` = `AudioAPI`) · `main: tw.xinshou.discord.plugin.api.audioapi.Event` · `require_intents: [GUILD_VOICE_STATES]` · `require_cache_flags: [VOICE_STATE]` · `require_member_cache_policies: [VOICE]` · no depend/soft-depend plugins or jars · no `prefix` (defaults to `AudioAPI`) · no `component_prefix` (Core default `audioapi@`, unused) |
| Other resources | None: no `config.yaml`, no `lang/`, no images |
| Gradle | `id("xs-plugin-shadow")` (a shadow jar written to `<outputPath>/plugins/AudioAPI-<ver>.jar`); `gradle.properties`: `version.patch=0` |

## 2. Lifecycle
- `load()` is the inherited default (`core:plugin/PluginEvent.kt:23-29`). It exports `lang/` only if the resource exists, which it does not here, then logs INFO `AudioAPI loaded with default.`
- `unload()` and `reload()` are inherited defaults: a log line and a no-op lang export.
- Order quirk (Core): AudioAPI is ADDed to the plugin queue before MusicPlayer (log:439, log:449), but `PluginLoader.run()` iterates the queue in reverse, so **AudioAPI.load() runs after MusicPlayer.load()** (log:674, log:757). This is harmless here because AudioAPI's load does nothing.
- No background jobs. No in-memory state.

## 3. Slash commands and context menus
None. `guildCommands()` and `globalCommands()` return the default `null`.

## 4. Components
None.

## 5. Events
None (`listener = false`).

## 6. Configuration
None. There is no `config.yaml` and therefore no `enabled` flag; the plugin is always "loaded".

## 7. Localization and templates
None.

## 8. Persistence
None.

## 9. External dependencies
- `api("club.minnced:opus-java:1.1.1")` is the Opus encoder/decoder JNI wrapper and its natives.
- `api("com.google.crypto.tink:tink:1.20.0")` provides AEAD crypto, including the XChaCha20-Poly1305 mode that JDA voice transport can use.
- No HTTP endpoints, credentials or plugin dependencies.
- **Consumer:** only MusicPlayer, through `compileOnly(project(":Plugins:API:AudioAPI"))` (`Plugins/MusicPlayer/build.gradle.kts:12`) and `depend_plugins: [AudioAPI]` (`Plugins/MusicPlayer/src/main/resources/info.yaml:10-11`). **No MusicPlayer source imports opus or tink classes.**

### Classloader analysis: is AudioAPI functionally redundant?
1. **Visibility.** Each plugin gets a `PluginSandboxClassLoader` whose parent is Core's loader (`core:plugin/ClassLoader.kt:40-45,69-96`).
   - `net.dv8tion.jda.*`, `kotlin.*` and `tw.xinshou.discord.core.*` are resolved **parent-first**.
   - Everything else is resolved child-first, then from dependency plugins' loaders, then from the parent.
   - JDA therefore lives in Core's loader and **cannot see** classes that exist only inside AudioAPI's plugin loader. Parents never delegate down to children.
   - So AudioAPI's shaded opus-java and tink are visible only to plugins that declare AudioAPI as a dependency (MusicPlayer). MusicPlayer never touches them.
2. **Where JDA gets them.** Core declares `api(libs.jda)` with no excludes (`Core/build.gradle.kts:62`). JDA's audio dependencies (opus-java and tink) are therefore expected to arrive transitively inside Core's shadow jar.
   - **Evidence:** the `DevServer/Core-4.0.2-SNAPSHOT.jar` built from a different branch contains `com/google/crypto/tink/**`, `club/minnced/opus/**` (API classes only, no `libopus` natives), JDAVE classes, and `natives/{linux-x86-64,linux-aarch64,win-x86-64,darwin}/libdave.*`.
   - This was not verified for a `main` build of Core 3.4.x.
3. **Opus natives are not needed** for MusicPlayer's send path: lavaplayer provides pre-encoded Opus (`AudioPlayerSendHandler.isOpus() = true`), so JDA performs no encoding.
- **Conclusion (high confidence, not runtime-proven on `main`):** AudioAPI's only effective contributions are its `info.yaml` requirements (which MusicPlayer duplicates) and its role as a hard load dependency. Its bundled libraries appear unused at runtime.

## 10. Discord requirements
- Intent: `GUILD_VOICE_STATES` (not privileged).
- Cache flag: `VOICE_STATE`. Core disables it by default in `core:base/BotLoader.kt:62-67`, and the plugin requirement re-enables it at `core:base/BotLoader.kt:74`.
- Member cache policy: `VOICE`, which is already part of Core's default `OWNER`+`VOICE`.
- No bot permissions and no rate-limit-sensitive operations.

## 11. Concurrency
None.

## 12. Bugs, quirks, dead code, TODOs, hard-coded values
- **Probably vestigial** (§9 analysis). Its bundled opus-java and tink are likely unreachable by JDA and unused by MusicPlayer.
- Its `info.yaml` requirements duplicate MusicPlayer's own.
- The jar is shaded, so it duplicates classes that Core probably already contains. That costs jar size and could cause version skew between Core's tink and AudioAPI's tink 1.20.0 if a plugin ever used both.
- No TODOs. The only hard-coded values are the two dependency versions.
- Behaviour to preserve: none user-visible. Only the requirement "voice intents and caches are enabled when music is installed" matters.

## 13. Testability
- Nothing to unit-test.
- A port-level acceptance check could assert that, with the music feature enabled, the bot's intents include `voice_states`, member caching includes voice, and the voice runtime dependencies are importable or present: PyNaCl, davey, libopus and FFmpeg (or a Lavalink node).

## 14. Porting assessment
**Difficulty: Low.** Do not port it as a plugin.
- Fold its effects into the Python core and plugin manifest instead:
  - the music plugin's manifest declares `intents.voice_states = True` and `MemberCacheFlags.voice = True`;
  - packaging declares `discord.py[voice]>=2.7` (PyNaCl and davey for DAVE), plus system FFmpeg and libopus for the native-voice option, or a Lavalink ≥ 4.2 node for the Lavalink option.
- If the Python plugin system keeps `depend_plugins` semantics, a placeholder `AudioAPI` manifest entry could keep existing dependency declarations valid.
- Risk: none functional. The only real "dependency" to reproduce is a correct voice runtime: DAVE through davey (discord.py ≥ 2.7.0) or a DAVE-capable Lavalink node.
