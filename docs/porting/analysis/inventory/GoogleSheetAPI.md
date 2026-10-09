# GoogleSheetAPI — porting inventory (branch `main`)

All paths are relative to `Plugins/API/GoogleSheetAPI/src/main/kotlin/api/google/sheet/` unless prefixed.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/API/GoogleSheetAPI` (Gradle `:Plugins:API:GoogleSheetAPI`, `build.gradle.kts`, convention `xs-plugin-shadow` → shaded jar `GoogleSheetAPI-3.4.0-SNAPSHOT.jar`). There is **no shared `Plugins/API/build.gradle.kts`**; `Plugins/API/build/` is only build output. |
| Kotlin files / LOC | 3 files / 66 physical lines: Event 5, SheetsService 41, config/ConfigSerializer 20 |
| Package | `tw.xinshou.discord.plugin.api.google.sheet` |
| Entry | `object Event : PluginEvent(false)` (Event.kt:6), an empty body with no overrides and no config |
| Listener flag | `false` |

**Purpose:** a **library-carrier plugin**.
- It ships the Google API client, OAuth and Sheets v4 libraries in its shaded jar.
- It exposes `SheetsService`, a helper that runs the OAuth installed-app flow and returns an authorized `Sheets` client. Dependent plugins use it through the Core plugin class-loader delegation.
- The plugin itself does nothing at runtime.

**info.yaml** (expanded):
- `author: xinshoutw`, `name: GoogleSheetAPI`, `coreApi: "3.4"`, `version: "3.4.0-SNAPSHOT"`.
- `main: "tw.xinshou.discord.plugin.api.google.sheet.Event"`.
- Defaults: `component_prefix` = `googlesheetapi@` (Core logs a "too long" warning).
- No intents, cache flags, member-cache policies or dependencies.

---

## 2. Lifecycle

`load()`, `unload()` and `reload()` are all Core defaults (core/plugin/PluginEvent.kt:23-39):
- They export `lang/` only if present, which it is not.
- They log `GoogleSheetAPI loaded with default.` and `GoogleSheetAPI unloaded with default.`.

There are no background jobs and no state in the plugin itself.

`SheetsService` state is per instance and lazy (SheetsService.kt:16-25):

| Field | Value |
|---|---|
| `httpTransport` | `GoogleNetHttpTransport.newTrustedTransport()` |
| `jsonFactory` | `GsonFactory.getDefaultInstance()` |
| `scopes` | `[SheetsScopes.SPREADSHEETS]` = `https://www.googleapis.com/auth/spreadsheets` |
| `credential` | the OAuth flow, below |
| `sheets` | `Sheets.Builder(transport, json, credential).setApplicationName("SheetsDSL").build()` |

**OAuth flow** (`credential()`, SheetsService.kt:27-41):
1. `GoogleAuthorizationCodeFlow.Builder(transport, json, clientId, clientSecret, scopes)` with:
   - `setDataStoreFactory(FileDataStoreFactory(File(pluginDirFile, "tokens")))`. The token store lives in the **caller's** plugin directory, for example `plugins/Economy/tokens/StoredCredential`.
   - `setAccessType("offline")`, which gives a refresh token.
2. `LocalServerReceiver.Builder().setPort(config.port).build()`. Port `-1` means pick a free port (library behavior). The redirect URI is `http://localhost:<port>/Callback`.
3. `AuthorizationCodeInstalledApp(flow, receiver).authorize("user")`, with credential ID **`"user"`**.
   - If no stored credential exists, it tries to open a desktop browser, otherwise prints the URL to stdout.
   - It then **blocks the calling thread** until the redirect arrives.
   - Kotlin `by lazy` is synchronized, so concurrent first accessors also block.

---

## 3. Slash commands & context menus

None.

## 4. Components

None.

## 5. Events

None.

---

## 6. Configuration

The plugin has **no `config.yaml`**. `ConfigSerializer` (config/ConfigSerializer.kt:6-20) is a DTO that consumers construct themselves:

| Field | YAML name (if decoded) | Type | Validation |
|---|---|---|---|
| `clientId` | `client_id` | String | non-blank |
| `clientSecret` | `client_secret` | String | non-blank |
| `port` | `port` | Int | `port == -1 \|\| port > 0` |

The only consumer, Economy, builds it as `ConfigSerializer(config.clientId, config.clientSecret, config.port)` from its **own** `config.yaml`. That file has keys `client_id`, `client_secret`, `port` (default 8888), and requires `port in 1..65535` (Plugins/Economy/src/main/kotlin/economy/config/ConfigSerializer.kt:9-14,38).

---

## 7. Localization & templates

None.

---

## 8. Persistence

- OAuth tokens live under `<consumer plugin dir>/tokens/`.
  - `FileDataStoreFactory` writes a Java-serialized `StoredCredential` file.
  - **This format is not portable to Python**, so the port requires a one-time re-authorization.
- The plugin has no Mongo, JSON or SQLite storage.
- The local, gitignored `Server/plugins/` directory has no `Economy/tokens` directory, which suggests the Sheets mode has never been used there. This is weak evidence.

---

## 9. External dependencies

**Gradle** (`build.gradle.kts:5-10`). These are `api(...)` dependencies, so consumers compile against them; they are shaded into this plugin's jar and loaded by dependents via class-loader delegation:

| Artifact | Version | Note |
|---|---|---|
| `com.fasterxml.jackson.core:jackson-databind` | 2.21.0 | not referenced by the code; probably a version pin |
| `com.google.api-client:google-api-client` | 2.8.1 | |
| `com.google.oauth-client:google-oauth-client-jetty` | 1.39.0 | |
| `com.google.apis:google-api-services-sheets` | v4-rev20251110-2.0.0 | |

**Services:**
- Google OAuth 2.0 (installed-app flow).
- Google Sheets API v4 (`https://sheets.googleapis.com`), called by consumers.

**API surface exposed to other plugins:**
```kotlin
// tw.xinshou.discord.plugin.api.google.sheet
class SheetsService(config: ConfigSerializer, pluginDirFile: File) {
    val sheets: com.google.api.services.sheets.v4.Sheets   // lazy; first access may block on OAuth
}
// tw.xinshou.discord.plugin.api.google.sheet.config
@Serializable data class ConfigSerializer(clientId: String, clientSecret: String, port: Int)
```
Plus the whole shaded Google client library, which consumers use directly, for example `com.google.api.services.sheets.v4.model.ValueRange`.

**Consumers** (grep of `Plugins/`):

| Consumer | How it depends | Calls used |
|---|---|---|
| **Economy** | `depend_plugins: [GoogleSheetAPI]` (Plugins/Economy/src/main/resources/info.yaml:11-12) + `compileOnly(project(":Plugins:API:GoogleSheetAPI"))` | `SheetImpl` (Plugins/Economy/src/main/kotlin/economy/storage/SheetImpl.kt:20-155), listed below |

Economy's `SheetImpl` uses:
- `SheetsService(ConfigSerializer(clientId, clientSecret, port), pluginDirectory).sheets.spreadsheets().values()`
- `.get(sheetId, "<label>!<range>").execute().values`
- `.batchGet(sheetId).setRanges(ranges).execute().valueRanges`
- `.append(sheetId, range, ValueRange().setValues(...)).setValueInputOption("RAW").execute()`
- `.update(sheetId, range, ValueRange(...)).setValueInputOption("RAW").execute()`

**`SheetImpl` is unreachable on `main`:** Economy hard-codes `private val MODE = Mode.Json` (Plugins/Economy/src/main/kotlin/economy/Event.kt:28). Economy still declares a **hard** dependency, so it fails to load if the GoogleSheetAPI jar is absent.

---

## 10. Discord requirements

None.

---

## 11. Concurrency

- `by lazy` (synchronized) around a blocking interactive OAuth call. The first `.sheets` access from a JDA event thread would block that thread until a human completes the browser flow.
- The Google client objects are shared and not otherwise synchronized.

---

## 12. Bugs, quirks, dead code, hard-coded values

- **Effectively dead on `main`:** the only consumer path is disabled by a hard-coded constant (above).
- The OAuth flow blocks and is interactive, which does not suit a headless bot host. It prints the auth URL to stdout and waits on `localhost:<port>`.
- The application name `"SheetsDSL"` and credential user ID `"user"` are hard-coded (SheetsService.kt:23, 40).
- `jackson-databind` is an unused direct dependency.
- `Economy.SheetImpl` itself has issues (for reference only):
  - it parses every cell with `.toString().toLong()`, which throws on blank or non-numeric cells;
  - it assumes the three ranges have equal length.

---

## 13. Testability

- No logic of its own is worth unit testing beyond the DTO validation (`client_id`/`client_secret` non-blank, `port == -1 or > 0`).
- If ported, put the OAuth and token storage behind an interface and fake the Sheets client in consumer tests.

---

## 14. Porting assessment

**Difficulty: Low. Recommendation: do not port now (YAGNI),** or port as an optional helper module rather than a plugin.

**If ported:**
- A plain Python module (`xsbot.api.google_sheets`) using `google-api-python-client` + `google-auth-oauthlib`:
  - `InstalledAppFlow.from_client_config(...).run_local_server(port=port or 0)`;
  - tokens saved as JSON (`Credentials.to_json()`) under the consumer's plugin directory.
- Expose an async-safe wrapper: run the blocking client calls in `asyncio.to_thread`.
- Prefer a non-interactive service-account option for headless hosts.

**Risks:**
- Token migration requires re-authorization.
- Interactive OAuth on a server.
- The only consumer is dead code. Keep or drop it together with Economy's Sheets mode.
