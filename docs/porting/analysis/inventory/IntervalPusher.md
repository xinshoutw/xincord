# IntervalPusher — porting inventory (branch `main`)

All paths are relative to `Plugins/IntervalPusher/src/main/kotlin/intervalpusher/` unless prefixed.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/IntervalPusher` (`build.gradle.kts`, convention `xs-plugin`, not shaded: `IntervalPusher-3.4.0-SNAPSHOT.jar`) |
| Kotlin files / LOC | 3 files / 206 physical lines: Event 55, IntervalPusher 136, config/ConfigSerializer 15 |
| Package | `tw.xinshou.discord.plugin.intervalpusher` |
| Entry | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (Event.kt:10) |
| Listener flag | `true`, but **no listener methods are overridden**. The registration has no effect. |

**Purpose:** a heartbeat or uptime pusher.
- For each configured listener it sends an HTTP GET to a URL every `interval` seconds.
- The default URL is an Uptime Kuma *push monitor* URL (`https://status.xinshou.tw/api/push/<token>?status=up&msg=OK&ping=%ping%`).
- `%ping%` is replaced with the bot's current Discord **REST** ping in ms.

**info.yaml** (expanded):
- `author: xinshoutw`, `name: IntervalPusher`, `coreApi: "3.4"`, `version: "3.4.0-SNAPSHOT"`.
- `main: "tw.xinshou.discord.plugin.intervalpusher.Event"`.
- Defaults: `prefix` = name; `component_prefix` = `intervalpusher@` (Core logs a "too long" warning).
- No intents, cache flags, member-cache policies or dependencies.

---

## 2. Lifecycle

`Event` holds `coroutineScope = CoroutineScope(Dispatchers.IO + SupervisorJob())`, created once per object instance, and `pushers: MutableList<IntervalPusher>` (Event.kt:11-12).

**load()** (14-31):
1. `super.load()` reads or exports `plugins/IntervalPusher/config.yaml` (kaml, strict).
2. Stop all existing pushers and clear the list.
3. If disabled, warn `IntervalPusher is disabled.` and return.
4. For each `listeners[i]`, build `IntervalPusher(url, interval, coroutineScope)`, call `.start()`, and add it to the list.
5. Log `IntervalPusher loaded.`.

**reload()** (33-48): the same as load: re-read the config, stop and clear, return if disabled, otherwise start new pushers. It does not log "loaded". This is clean: reload fully applies the new config.

**unload()** (50-54): stop all pushers, `coroutineScope.cancel()`, log `IntervalPusher unloaded.`. It does not call `super.unload()`.
- After `cancel()`, the same object can no longer launch jobs.
- Core's full restart path (`BotLoader.reload` → `stop()`/`start()`) recreates the plugin class loaders, which produces a fresh `Event` instance (PluginLoader.kt:287-298, ClassLoader.kt:60-66). So this is not hit in practice.

**Per-listener job** (`IntervalPusher.start()`, IntervalPusher.kt:55-128):
- If `job?.isActive`, warn `IntervalPusher is already running!` and return.
- Otherwise `job = scope.launch(Dispatchers.IO) { loop }` and log `IntervalPusher started.`. The loop:
  ```
  while active:
      try:
          url = originUrl.replace("%ping%", restPingMs)          # all occurrences; "-1" if ping fails
          resp = GET url  (connect timeout 10 s, request timeout 30 s, redirects NOT followed)
          2xx  -> debug "Successfully queried URL: <url>."
          404  -> warn "Status Monitor refused the connection! (Code: 404)!" + warn "Breaking the heartbeat loop!" + stop()
          521  -> warn "Status Monitor is OFFLINE! (Code: 521)!"          (Cloudflare origin down)
          other-> error "Query URL <url> failed, code: <code>!"
      except IOException as e:  error "Query URL <originUrl> internet error: <msg>!"
      except Exception as e:    error "Query URL <originUrl> failed: <msg>!"
      delay(interval * 1000 ms)                       # fixed DELAY after each attempt
  ```
- **The first push happens immediately** on start.
- The period is `interval` plus the request time, because the delay is fixed and runs after each attempt; it is not a fixed rate.
- `stop()` (131-135) calls `job?.cancel()` and logs `IntervalPusher stopped.`.

**REST ping** (40-52) calls `jdaBot.restPing.queue(...)`. JDA times a `GET /users/@me` round trip (ms, Long). Any failure becomes `"-1"` (29-37).

**In-memory state:** the `pushers` list, plus `job` per pusher. Nothing is persisted.

---

## 3. Slash commands & context menus

None.

## 4. Components

None.

## 5. Events

None. Despite `listener=true`, no handlers are overridden.

---

## 6. Configuration (`plugins/IntervalPusher/config.yaml`)

`ConfigSerializer` is in config/ConfigSerializer.kt:5-15. The shipped default is `src/main/resources/config.yaml`.

| Key | Type | Code default | Shipped default | Validation / use |
|---|---|---|---|---|
| `enabled` | Boolean | `false` | `false` | Gates load and reload. |
| `listeners` | List<Listener> | **none, so the key is required even when disabled** | one listener (below) | One pusher per entry. |
| `listeners[].url` | String | required | `"https://status.xinshou.tw/api/push/xxxxxxxxxx?status=up&msg=OK&ping=%ping%"` | `%ping%` is the only placeholder. It is replaced literally with the plugin's own `String.replace`, not Core placeholders. **The URL is not validated.** |
| `listeners[].interval` | Int (seconds) | required | `60` | **Not validated.** `0` or a negative value makes `delay()` return immediately, so the loop hammers the URL. |

- Missing keys or unknown keys (kaml strict mode) throw from `load()` and abort the whole bot startup (cross-cutting, see the summary).
- When the plugin is disabled, no HTTP and no ping happen.

---

## 7. Localization & templates

None. There is no `lang/`, MessageCreator or Core placeholder. The plugin produces no Discord output.

## 8. Persistence

None.

## 9. External dependencies

- **Gradle:** none beyond Core.
- **HTTP:** one GET per listener per interval to the configured URL, typically an Uptime Kuma push endpoint.
  - Java `HttpClient`, one per pusher, connect timeout 10 s, request timeout 30 s.
  - No custom headers or auth.
  - **No redirect following**: a 3xx response lands in the "other" branch and logs an error.
  - The response body is read as a String and ignored.
- **Discord REST:** one `GET /users/@me` per iteration, made only to measure `%ping%`. It is done even if the URL has no `%ping%`.
- **Plugin dependencies:** none.

---

## 10. Discord requirements

- No intents, cache flags, member cache or channel permissions are needed.
- The only Discord interaction is the REST ping. It adds a negligible amount to the global REST rate limit (one call per interval per listener).

---

## 11. Concurrency

- Each pusher is one coroutine in a shared `SupervisorJob` scope on `Dispatchers.IO`, so one failing pusher does not cancel the others.
- HTTP uses `sendAsync`, bridged through `suspendCancellableCoroutine`; cancellation cancels the future (93-95). The ping uses JDA `queue` with the same bridge.
- The `pushers` list and the `job` field are not synchronized. Load, reload and unload are serialized by Core's `lifecycleLock` for the reload paths (BotLoader.kt:113-138).
- **Cancellation quirk:** `buildUrl` catches `Exception`, which includes `CancellationException`. If `stop()` lands during the ping wait, the iteration continues with `ping=-1`, the HTTP bridge throws `CancellationException`, and the generic catch logs a spurious `Query URL … failed: …!` before the following `delay` ends the loop (IntervalPusher.kt:29-37, 118-123).

---

## 12. Bugs, quirks, dead code, hard-coded values

**Behavior to preserve:**
1. The first push is immediate, then there is a fixed delay of `interval` seconds after each attempt.
2. `%ping%` is the Discord REST ping in ms (an integer), or `-1` on failure. Every occurrence is replaced.
3. **404 permanently stops that listener** until the next reload or restart. Uptime Kuma returns 404 for an unknown or inactive push token. Other listeners keep running.
4. 521 logs a warning and continues. Any other non-2xx status logs an error and continues. Network errors and invalid URLs log an error and retry next interval.
5. Reload restarts all listeners from the new config.

**Probable bugs or gaps:**
1. `interval` is not validated: values ≤ 0 produce a busy loop (ConfigSerializer.kt:13, IntervalPusher.kt:123).
2. The URL is not validated. `URI.create` failures repeat as error logs every interval.
3. A spurious error log on stop (§11).
4. `listener=true` is unnecessary (Event.kt:10).
5. A stopped pusher (after a 404) stays in `pushers`. This is harmless.

**Hard-coded:** connect timeout 10 s (IntervalPusher.kt:21), request timeout 30 s (70), and the status-code handling table.

---

## 13. Testability

**Pure:**
- `build_url(template, ping: int | None) -> str` (the replace-all, and `-1` on failure).
- `classify(status_code) -> {ok, stop, warn_offline, error}`.
- Config validation, including the proposed `interval >= 1`.

**With doubles:**
- A fake HTTP server or respx returning 200, 404, 521, 500 and a timeout.
- A fake ping provider (success or exception).
- A fake clock and sleep to assert: immediate first call, fixed delay, stop on 404, independent listeners, and reload replacing tasks.

---

## 14. Porting assessment

**Difficulty: Low.**

**Suggested discord.py mapping:**
- A `commands.Cog` that, in `cog_load`, spawns one `asyncio.Task` per listener running `while True: try: …; except Exception: log; await asyncio.sleep(interval)`. Do not swallow `asyncio.CancelledError`.
- In `cog_unload`, cancel and await the tasks. Reload means unloading and loading again.
- HTTP: `aiohttp`/`httpx` with `timeout=httpx.Timeout(30, connect=10)` and `follow_redirects=False` for parity.
- `%ping%`:
  - discord.py has no REST ping. To keep the semantics, time a cheap REST call, e.g. `t0=perf_counter(); await bot.http.request(Route('GET','/users/@me')); ms=int((perf_counter()-t0)*1000)`.
  - Alternatively, use `round(bot.latency*1000)`, the gateway heartbeat latency. That is a **behavior change** and must be flagged in the spec.

**Risks:**
- The ping semantics differ between JDA and discord.py.
- Fixed delay vs fixed rate if `tasks.loop` is used: `tasks.loop` schedules from iteration start.
