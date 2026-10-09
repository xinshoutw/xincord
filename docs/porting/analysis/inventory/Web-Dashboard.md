# Web-Dashboard — porting inventory (branch `main`)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Kotlin sources: `Web-Dashboard/src/main/kotlin/webdashboard/` (abbreviated `wd/`); Core adapter: `Core/src/main/kotlin/core/dashboard/CoreDashboardBackend.kt` (abbreviated `CDB`); frontend: `Web-Dashboard/frontend/` (`fe/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Gradle project | `:WebDashboard` with `projectDir = Web-Dashboard` (`settings.gradle.kts:84-86`); plugins `xs-jvm-conventions`, `application`, `kotlin("plugin.serialization")` (`Web-Dashboard/build.gradle.kts:4-8`); `gradle.properties` `version.patch=0` |
| Kotlin (module) | 4 files / 500 lines (426 non-blank): `Main.kt` (145), `api/DashboardBackend.kt` (42), `api/DashboardRoutes.kt` (230), `model/DashboardModels.kt` (83) |
| Kotlin (Core adapter) | `CoreDashboardBackend.kt` 355 lines (308 non-blank) |
| Frontend (tracked) | 12 files under `fe/src` / 1,325 lines (`App.tsx` 955; shadcn-style `components/ui/*` 294; `main.tsx` 14; `index.css` 56; `lib/utils.ts` 6) + configs: `package.json`, `package-lock.json`, `vite.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `tsconfig.json`, `tsconfig.node.json`, `components.json`, `index.html`, `.gitignore`. Untracked locally (not on `main`): `pnpm-lock.yaml`, `pnpm-workspace.yaml`. |
| Purpose | Local web UI + JSON API for editing the bot's **configuration files**: Core `config.yaml` built-ins (status-changer messages, console-logger targets), plugin `enabled` flags (instant toggle + hot reload), and raw plugin `config.yaml` text (save + hot reload). It is not a per-guild/end-user dashboard. |
| README | `Web-Dashboard/README.md` (env vars, build modes, runtime behavior) |

## 2. Architecture & lifecycle

- **Embedded in the bot process** (same JVM). `Core/build.gradle.kts:59` has `implementation(project(":WebDashboard"))`; Core's shadow jar therefore contains the Ktor server, its classes and the built frontend (resources under `dashboard/`).
- Dependency inversion: the module defines `interface DashboardBackend` (`wd/api/DashboardBackend.kt:8-22`); Core implements it as `object CoreDashboardBackend` (`CDB:29`) and passes it in.
- Startup: Core `main()` → `CacheDbServer.start()` → `DashboardServer.start(backend = CoreDashboardBackend)` → `BotLoader.start()` → console loop (`Core/src/main/kotlin/core/Main.kt:24-27`); shutdown in `finally` → `DashboardServer.stop()` (grace 700 ms, timeout 2,500 ms) (`Main.kt:34`, `wd/Main.kt:80-89`). The dashboard is up **before** JDA logs in; in `--no-online` (`-N`) mode it runs alone as a config editor ("config-only" mode).
- Server: Ktor 3.2.3 `embeddedServer(Netty, host, port)`, `start(wait = false)`; guarded by `@Synchronized` and an "already started" check (`wd/Main.kt:54-78`).
- Runtime config from env (`wd/Main.kt:33-46`): `XSBOT_DASHBOARD_ENABLED` (default enabled; only the literal `false`, case-insensitive, disables), `XSBOT_DASHBOARD_HOST` (default `127.0.0.1`), `XSBOT_DASHBOARD_PORT` (default `21100`; non-integer ⇒ 21100). No config-file setting.
- Installed Ktor plugins (`wd/Main.kt:104-145`): `CallLogging`; `Compression` (gzip); `ContentNegotiation` with kotlinx JSON (`prettyPrint=true`, `ignoreUnknownKeys=true`, `encodeDefaults=true`); `CORS` (methods GET/PUT/OPTIONS, header Content-Type, allowed origins `http://<host>:<port>`, `http://localhost:5173`, `http://127.0.0.1:5173`); `StatusPages` catching `Throwable`.
- Standalone mode: `wd/Main.kt:91-102` (`./gradlew :WebDashboard:run`, main class `tw.xinshou.discord.webdashboard.MainKt`, `build.gradle.kts:14-16`) uses `UnavailableDashboardBackend` — every config endpoint answers 409 "Dashboard backend is not configured." (UI preview only).
- Background jobs: none (besides Netty). State: `DashboardServer.engine/backend` (`wd/Main.kt:51-52`), in-memory static asset cache (`ConcurrentHashMap`, `wd/api/DashboardRoutes.kt:29`).

## 3. HTTP endpoints

All JSON bodies are kotlinx-serialized DTOs from `wd/model/DashboardModels.kt`. Error mapping for backend calls (`wd/api/DashboardRoutes.kt:211-230`): `NoSuchElementException` → 404, `IllegalArgumentException` → 400, `IllegalStateException` → 409, each with `SaveResponseDto{ok:false, message}`; anything else is rethrown to `StatusPages`.

| # | Method & path | Request | Success response | Errors / notes |
|---|---|---|---|---|
| 1 | `GET /api/v1/health` | — | 200 `HealthDto{status:"ok", serverTime:<epoch ms>, mode:"live"\|"config-only"\|"unconfigured", recommendedBaseUrl:"http://<host>:<port>"}` | `mode` = "live" iff `BotLoader.jdaBot` was ever initialized (`CDB:36`, `:315`; stays "live" after a stop) |
| 2 | `GET /api/v1/config/core` | — | 200 `CoreConfigDto{general:{tokenMasked}, builtins:{statusMessages:[String], consoleTargets:[{guildId:Long, channelId:Long, logTypes:[String], format:String}]}}` | `tokenMasked` = `•` × token length (`CDB:337-342`); exports default `config.yaml` if missing (`CDB:232-238`) |
| 3 | `PUT /api/v1/config/core` | `CoreConfigDto` (must include `general.tokenMasked`, ignored) | 200 `{ok:true, message:"Core config saved to config.yaml and applied immediately.", updatedAt}` | Rewrites `builtin_settings` only (status messages trimmed, blanks dropped; targets mapped 1:1, **no validation**), keeps `general_settings.bot_token`; re-encodes whole file with kaml (comments lost); atomic write; `BotLoader.reloadCoreSettingsStrict()` (re-read settings, restart StatusChanger, reload ConsoleLogger); on exception: restore previous text, re-apply, 409 `Failed to apply core settings. Changes were rolled back. <cause>` (`CDB:43-84`) |
| 4 | `GET /api/v1/config/plugins` | — | 200 `[PluginConfigDto]` sorted by lowercase name | Names = union of `info.yaml` names from every `plugins/*.jar`, loaded plugins, and `plugins/<dir>/config.yaml` dirs (`CDB:86-130`). Fields: `name, enabled` (from top-level `enabled:` line; **true if absent**), `category:"Plugin"` (constant), `description` (info.yaml or "No description found in info.yaml."), `dependencies`(=dependPlugins), `intents`(=requireIntents), `author, version, requireIntents, requireCacheFlags, requireMemberCachePolicies, dependPlugins, softDependPlugins, loaded, canToggle` (has top-level enabled line), `configPath` (`plugins/<name>/config.yaml` or null), `hasWebEditor` (config exists) |
| 5 | `PUT /api/v1/config/plugins/{pluginName}` | `PluginToggleRequestDto{enabled:Boolean}` | 200 `{ok:true, message:"Plugin '<n>' set to enabled=<b> and reloaded."}` or `"... It will apply when plugin loads."` (not loaded) or `"Plugin '<n>' already enabled=<b>."` | 400 invalid name (regex `^[A-Za-z0-9._-]+$`, `CDB:34`, `:249-257`); 404 no config.yaml; 409 no top-level `enabled` line, or reload failed (file restored + plugin reloaded again: `Failed to reload plugin '<n>'. Changes were rolled back. <cause>`). Edit = regex replace of first `^enabled\s*:\s*(true\|false)\s*(#.*)?$` line with `enabled: <b>` (drops a trailing comment) (`CDB:33`, `:132-160`, `:208-224`) |
| 6 | `GET /api/v1/config/plugins/{pluginName}/yaml` | — | 200 `PluginYamlDto{name, yaml (raw text), path (absolute filesystem path), loaded, hasEnabledFlag}` | 400/404 as above (`CDB:162-177`) |
| 7 | `PUT /api/v1/config/plugins/{pluginName}/yaml` | `PluginYamlUpdateRequestDto{yaml:String}` | 200 `"Plugin '<n>' config saved and reloaded."` / `"... It will apply when plugin loads."` / `"No changes for plugin '<n>'."` | 400 empty body after trim; 404; 409 reload failure with rollback. Writes `trim(yaml) + "\n"` atomically; **no YAML/schema validation before writing** — validation only happens through the plugin's `reload()` when the plugin is loaded (`CDB:179-206`) |
| 8 | `GET /assets/{...}` | — | classpath `dashboard/assets/<rest>` with content type by extension, `Cache-Control: public, max-age=31536000, immutable` | 404 if missing; successful lookups cached forever in memory (`DashboardRoutes.kt:41-76`) |
| 9 | `GET /src/{...}` | — | 410 text/plain `Development path '/src/*' is not available in production bundle.` | (`DashboardRoutes.kt:33-39`) |
| 10 | `GET /{...}` (SPA fallback) | — | classpath `dashboard/index.html`, `Cache-Control: no-store…`, `Pragma: no-cache` | Paths under `/api/`, `/assets/`, `/src/` ⇒ 404; missing bundle ⇒ 200 "Dashboard bundle not found" page; dev-entry index ⇒ 503 "Invalid dashboard bundle" (`DashboardRoutes.kt:159-202`) |

So: **7 API endpoints** (4 GET, 3 PUT) + 3 static/SPA routes. `OPTIONS` handled by CORS. No DELETE/POST.

Atomic writes: temp file `<name>.tmp` in the same directory + `Files.move(REPLACE_EXISTING, ATOMIC_MOVE)` with non-atomic fallback (`CDB:259-278`). All backend operations are serialized by one `ReentrantLock` (`CDB:32`).

Hot-reload side effects (`core/base/BotLoader.kt:133-159`): `reloadPluginStrict(name)` → `plugin.reload()` → rebuild command lists → `jdaBot.updateCommands()` (global) **and** `guild.updateCommands()` for **every guild** — on every toggle/save of any loaded plugin, even plugins without commands. This is the only code path that ever calls plugin `reload()` hooks.

## 4. Auth model

**None.** No login, sessions, API tokens, Discord OAuth2, CSRF tokens, or role checks on any route. Protection relies on: default bind to `127.0.0.1`, and the CORS allow-list (Ktor rejects disallowed cross-origin requests with 403; JSON PUTs need a preflight that disallowed origins fail).

## 5. Frontend

- Stack: React 18.3 + TypeScript 5.9 + Vite 7 (`@vitejs/plugin-react-swc`) + Tailwind CSS 3.4 (+ postcss/autoprefixer) + shadcn/ui-style components on Radix primitives (separator, slot, switch, tabs) + `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react` (`fe/package.json`). Resolved in `package-lock.json` (lockfile v3, 198 packages): react/react-dom 18.3.1, vite 7.3.1, tailwindcss 3.4.19, typescript 5.9.3, @vitejs/plugin-react-swc 3.11.0, lucide-react 0.554.0, tailwind-merge 3.4.1, postcss 8.5.6. Single component `App.tsx`; no router, no state library, plain `fetch` to relative `/api/v1/...`. Dark theme forced (`fe/src/main.tsx:7-8`). Fonts loaded from Google Fonts at runtime (`fe/src/index.css:1`). `index.html` `lang="zh-Hant"`, title `XsDiscordBot Dashboard`.
- Build: Gradle `frontendInstall` (`npm ci`) → `frontendBuild` (`npm run build` → `fe/dist`) → `frontendDistCheck` (fails if `dist/index.html` missing or still the dev entry) → `processResources` copies `fe/dist` into the jar under `dashboard/` (`Web-Dashboard/build.gradle.kts:73-167`). Root `build` depends on `:WebDashboard:build` (`build.gradle.kts:63-66`). `-Pfrontend.skipNpm=true` uses an existing `dist`; npm discovery: `-Pfrontend.npmExecutable`, `NPM_EXECUTABLE`, `NVM_BIN`, `~/.nvm/versions/node/*`, `~/.volta/bin/npm`, `/opt/homebrew/bin/npm`, `/usr/local/bin/npm`, `npm`/`npm.cmd` (`build.gradle.kts:24-56`).
- Dev: `npm run dev` on `127.0.0.1:5173` (strictPort) proxying `/api` to `VITE_DASHBOARD_API_TARGET` or `http://127.0.0.1:21100` (`fe/vite.config.ts:5-28`).
- UI (mixed zh-Hant/English copy): header "XsDiscordBot 控制面板" with a Connected/Offline badge (click = refresh). Tab **Core Settings**: Status Changer rows (Type select PLAYING/STREAMING/LISTENING/WATCHING/COMPETING/CUSTOM_STATUS, Message, Delay ms; Add/Remove; serialized as `TYPE;content;delay`, `fe/src/App.tsx:117-147`), Console Logger targets (Guild ID, Channel ID, Format, log-type chips command/button/modal; Add/Remove), "Save Core Changes" (enabled only when dirty). Tab **Plugin Controls**: list split into "Instant Toggle" (has `enabled` flag; switch sends PUT immediately with optimistic update + rollback, `App.tsx:476-507`) and "Manual-Only Plugins"; detail card with author/version/description, a synthesized read-only "Info YAML" (`App.tsx:206-223`, not the real info.yaml), raw YAML textarea with "Reload YAML"/"Save YAML" (`App.tsx:509-526`). The masked token is fetched but never displayed.

## 6. What it lets users do (relevant to this scope)

- Toggle `enabled` for WelcomeByeGuild, AutoRole, BotInfo, _Example (all have a top-level `enabled:`), which runs each plugin's `reload()` and re-uploads commands.
- Edit their `config.yaml` (e.g. AutoRole `guilds` mapping) with hot reload and rollback on reload failure.
- It cannot edit lang/message templates, per-guild data (e.g. WelcomeByeGuild `data/*.json`), the bot token, intents, or view logs/guilds.

## 7. Maturity

**Functional MVP, not hardened.** The backend is wired into Core startup, endpoints are complete for the stated features, writes are atomic with rollback, and the UI is polished. WIP signs: no auth, no tests, constant `category`, duplicated DTO fields (`dependencies`/`dependPlugins`, `intents`/`requireIntents`), unused `mode`/`recommendedBaseUrl`/`tokenMasked` in the UI, standalone mode is a stub, and the v4 design spec marks the dashboard "Deferred (skeleton only)" (`docs/specs/2026-04-07-v4-core-refactor-design.md:20`).

## 8. Persistence

Reads/writes `./config.yaml` (Core) and `./plugins/<name>/config.yaml` (CWD-relative, `CDB:226-230`); reads `info.yaml` from every `./plugins/*.jar` on each list call (`CDB:280-313`). No database.

## 9. External dependencies

Ktor 3.2.3 (`server-core`, `netty`, `call-logging`, `content-negotiation`, `serialization-kotlinx-json`, `cors`, `status-pages`, `compression`), kotlinx-serialization-json 1.9.0, logback (`Web-Dashboard/build.gradle.kts:169-180`, `gradle/libs.versions.toml:29-30`, `:88-96`). Frontend runtime fetch of Google Fonts. Node/npm at build time.

## 10. Discord requirements

None directly. Indirect: each plugin toggle/save triggers a global command overwrite plus one guild command overwrite per guild (rate-limit sensitive for bots in many guilds); console-target saves restart the ConsoleLogger; status saves restart the presence-rotation thread.

## 11. Concurrency

- Ktor handlers execute blocking file I/O, lock waits and `synchronized(lifecycleLock)` plugin reloads on Ktor/Netty threads (acceptable for low traffic).
- Single `ReentrantLock` serializes backend calls; `BotLoader` reload paths synchronize on `lifecycleLock`. `PluginLoader.pluginQueue` (plain `LinkedHashMap`) is read by `listPlugins`/`getPluginYaml` without `lifecycleLock` while a console `reload` may be clearing it.
- Plugin `reload()` runs on a Ktor thread concurrently with JDA event handling; plugins' state swaps are mostly non-volatile vars (see plugin reports).

## 12. Bugs, quirks, security concerns

Security (highest first):
1. **No authentication/authorization** on any endpoint; any local process (or anyone on the network if `XSBOT_DASHBOARD_HOST=0.0.0.0`, which emits no warning) can read every plugin config (may contain other plugins' API keys/credentials), rewrite configs, toggle plugins, and trigger reloads.
2. **DNS rebinding**: no Host-header allow-list; a malicious web page opened on the bot host can rebind its domain to 127.0.0.1 and become "same origin" (Ktor CORS treats origin == Host as allowed), gaining full read/write API access.
3. **Path traversal to the Core config**: `normalizePluginName` accepts `..` (dots allowed by `^[A-Za-z0-9._-]+$`), and `pluginConfigFile("..")` = `plugins/../config.yaml` = Core `config.yaml`, which holds the bot token in plaintext (`CDB:34`, `:230`, `:249-257`). If the HTTP layer delivers a `{pluginName}` of `..` (e.g. percent-encoded `%2E%2E` from a non-browser client; I did not verify Ktor 3.2.3's dot-segment handling at runtime), `GET …/plugins/%2E%2E/yaml` would disclose the token (defeating the masking in endpoint 2) and `PUT …/yaml` would overwrite Core config without reload/rollback (`applyPluginReload` returns false for unknown names).
4. Raw plugin YAML is written without validation when the plugin is not loaded; since plugin `load()` exceptions abort Core startup (`core/base/PluginLoader.kt:147-152`), a bad save can prevent the next bot start.
5. Core-config save performs no validation (guild/channel ID 0, empty format, unknown log types, arbitrary activity strings accepted).
6. Token masking leaks token length (`CDB:341`); YAML GET leaks absolute filesystem paths.
7. Google Fonts request from the admin's browser (privacy/offline).

Correctness bugs:
8. **Snowflake precision loss**: console-target `guildId`/`channelId` are JSON numbers parsed into JS `number` (`fe/src/App.tsx:30-35`, `:655-672`); Discord IDs (~8.6e17–1.3e18) exceed 2^53, so they are rounded (e.g. `858672865355890708` → `858672865355890700`). Any core save (even after editing only a status message) writes the rounded IDs back, silently breaking console-logger targets. Fix: serialize IDs as strings.
9. `StatusPages` handler responds with `mapOf("ok" to false, "message" to …)` (`wd/Main.kt:134-144`); a `Map<String, Any>` with mixed Boolean/String values is, to my understanding, not serializable by Ktor's kotlinx converter, so unexpected errors (including malformed JSON bodies from `call.receive`) most likely end up as a bare 500 instead of the intended JSON (not verified at runtime).
10. **Dashboard bind failure prevents bot start**: `DashboardServer.start()` runs before `BotLoader.start()` inside the same `try` (`Core/src/main/kotlin/core/Main.kt:21-31`); a port conflict on 21100 throws and the application terminates.
11. Status rows: content may contain `;` in the UI parser (first/last separator, `App.tsx:121-142`) but Core `StatusChanger` splits on every `;` (`core/builtin/statuschanger/StatusChanger.kt:54`), so such entries break; delay has no server-side lower bound (UI `min=1000` is not enforced on change) ⇒ presence update spam; STREAMING entries cannot carry a URL (the third field is forced numeric, while Core uses it as URL and as sleep time).
12. Cannot remove the last status message / console target in the UI (buttons disabled at length ≤ 1).
13. `enabled` toggle drops trailing comments on that line; Core save re-encodes `config.yaml` and loses all comments.
14. Every toggle/save re-uploads all commands for all guilds.
15. `mode` reports "live" forever once JDA was initialized, even after shutdown.

## 13. Testability

Backend logic that is pure/extractable: enabled-flag detection/replacement regex; plugin-name validation (add explicit `..` rejection test); plugin list merge/sort; core-config DTO ↔ YAML mapping (token preserved, blanks dropped); atomic write + rollback orchestration (inject a failing reloader); error → HTTP status mapping. HTTP tests with an in-process test client (aiohttp `TestClient` / FastAPI `TestClient`) and a fake bot/plugin manager; frontend can be tested separately (or kept as-is).

## 14. Porting assessment & Python options

Difficulty: **Medium** to port the backend faithfully (7 endpoints, reload/rollback semantics, plugin metadata), **Low** if dropped.

Options:
1. **Drop for the first Python release**: configs are files; provide an admin-only `/reload` (or console command) that reloads a plugin/config. Lowest risk.
2. **In-process `aiohttp.web`** (aiohttp is already a discord.py dependency): start `web.AppRunner` + `web.TCPSite` from `setup_hook`, serve the existing React `dist/` as static files, keep the `/api/v1` JSON contract, implement reload with `bot.reload_extension()` + command sync, guard with an `asyncio.Lock`. Must add: authentication (startup-generated admin token or Discord OAuth2 with an owner allow-list), Host-header allow-list (anti DNS-rebinding), plugin-name allow-list from discovered plugins (no path joins on user input), YAML parse + schema validation before writing, IDs as strings (small frontend change), optional sync-throttling of command uploads.
3. FastAPI/uvicorn in the same event loop (`uvicorn.Server(...).serve()` as a task) — nicer validation/OpenAPI, extra dependencies.
4. Separate process + IPC for reloads — most complex; not recommended.

Risks: config-write races with a running bot, command-sync rate limits, preserving rollback semantics, and the security hardening listed above (the current Kotlin behavior should not be replicated as-is).
