## Context

v3's IntervalPusher (`Plugins/IntervalPusher`, 3 Kotlin files, 206 lines) has no commands, text,
components or storage. `Event` (`PluginEventConfigure`, registered as a listener without handlers)
reads `config.yaml` (`enabled`, `listeners[].url`, `listeners[].interval`,
`ConfigSerializer.kt:5-15`) and, when enabled, starts one `IntervalPusher` per listener in a shared
`SupervisorJob` scope (`Event.kt:14-31`); `reload()` stops them all and starts the new config's
(`:33-48`), `unload()` stops them and cancels the scope (`:50-54`). Each pusher's coroutine
(`IntervalPusher.kt:55-128`) replaces `%ping%` with JDA's REST ping (`:29-52`), sends a GET with
Java's `HttpClient` (connect timeout 10 s, request timeout 30 s, no redirects), logs by status code
(2xx debug, 404 warning and stop, 521 warning, other error), logs network and other errors, and
waits `interval` seconds after each attempt. The inventory is
`docs/porting/analysis/inventory/IntervalPusher.md`; its section 12 lists the behavior to preserve
and five probable bugs.

## Goals / Non-Goals

**Goals:** v3's pushes (first at once, fixed delay, `%ping%`, the status-code table, 404 stops one
listener, independent listeners, reload restarts); v3's config shape; the defects fixed; the first
background loop and the first outgoing HTTP in a plugin, with test helpers that later ports reuse.

**Non-Goals:** placeholders other than `%ping%`, other methods, headers or authentication,
following redirects, reading the response body, commands to manage listeners.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/interval_pusher/`: `__init__.py` (metadata and
  `setup`), `config.py` (the config model), `pusher.py` (one listener's loop: the ping, the request
  and the status handling), `cog.py` (one task per listener) and `config.yaml`. Entry point
  `IntervalPusher = "xincord.plugins.interval_pusher"`.
- `INTENTS = discord.Intents.none()`: the plugin handles no gateway event (v3 registered a listener
  without handlers). `DEPENDS` and `SOFT_DEPENDS` are empty. No `lang/` and no `DEFAULT_LOCALE`:
  v3 had no text. No component IDs and no storage: v3 kept nothing but the config.
- The bundled `config.yaml` lists no listeners (`listeners: []`) and shows an example in a comment,
  `https://status.example.com/api/push/<token>?status=up&msg=OK&ping=%ping%` every 60 seconds.
  v3's file held one listener on the owner's status domain with a placeholder token; an enabled
  plugin would have pushed there.
- v3's `info.yaml` keys `author`, `coreApi` and `version` have no counterpart, as for _Example.
  v3 logged `IntervalPusher is disabled.`, `loaded.` and `unloaded.`; the core logs loads and
  unloads, and a plugin missing from `plugins` is never imported.
- `xincord-plugins` declares `aiohttp>=3.14.4`, the version installed with discord.py 2.7.1 (which
  requires `aiohttp>=3.7.4,<4`), because the plugin imports it; no new package is installed.

### Config

`Config(Model)` has a required `listeners: tuple[Listener, ...]`, as v3's `listeners` had no
default. `Listener` keeps v3's keys and order:

- `url: str`, checked at load by replacing `%ping%` with `0` and splitting it with
  `urllib.parse.urlsplit`: the scheme is `http` or `https` in any case, there is a host, no
  whitespace appears anywhere, and a port, if any, is a number from 0 to 65535. v3 took any string
  and failed at every push (`URI.create`, or `HttpClient`'s unsupported schemes); those URLs now
  disable the plugin at load with `listeners.<n>.url` named.
- `interval: int` from 1 to 2147483647 seconds. v3's `Int` refused larger values at load too, and
  accepted 0 and negatives, which made `delay()` return at once (a busy loop).

v3's `enabled` is not part of the model: a v3 file logs `unknown key enabled`. An invalid file
raises `ConfigError` in `setup`, so the core disables only IntervalPusher and logs the key.

### REST ping

`pusher.rest_ping(client, clock=time.perf_counter)` times
`client.http.request(Route("GET", "/users/@me"))` and rounds it to whole milliseconds, the request
that JDA's `getRestPing()` times. discord.py has no REST ping; `discord.http.Route` and
`HTTPClient.request` are the calls its own methods use. JDA started the clock just before sending;
discord.py's `request` also includes a rate-limit wait if one applies, which one request per push
does not trigger. `Pusher.url()` measures the ping only when the URL contains `%ping%`, then
replaces every occurrence (`str.replace`, as v3's). A failed measurement (`discord.DiscordException`,
`aiohttp.ClientError` or `OSError`, timeouts included) logs a warning and uses `-1`, as v3. The
gateway latency (`bot.latency`) is a different quantity, the heartbeat's round trip, and is not
used.

### Push request

`pusher.open_session()` creates an `aiohttp.ClientSession` whose `ClientTimeout` allows 10 seconds
to connect and 30 seconds per request (v3: `HttpClient` connect timeout 10 s, request timeout
30 s). Each listener's loop opens its own session, as each v3 pusher built its own `HttpClient`, and
closes it when the loop ends. `pusher.get_status(session, url)` sends
`session.get(url, allow_redirects=False)` and returns the status code without reading the body (v3
read it into a string and ignored it). A redirect is therefore a 3xx status, which v3's Java client
returned too. aiohttp rather than httpx: discord.py already depends on it.

### Status handling and logs

`Pusher.push()` makes one attempt and returns whether the loop goes on. Log lines name the plugin
and the listener by its position in `listeners`, from 1; URLs are logged as v3 logged them, push
tokens included. v3's levels are kept:

| Outcome | Level | Line | Loop |
|---|---|---|---|
| 2xx | debug | `IntervalPusher listener 1 pushed <url>` | goes on |
| 404 | warning | `IntervalPusher listener 1 stopped: the status monitor refused the push (code 404)` | ends |
| 521 | warning | `IntervalPusher listener 1: the status monitor is offline (code 521)` | goes on |
| other status | error | `IntervalPusher listener 1: pushing to <url> failed with code <status>` | goes on |
| `aiohttp.ClientError`, `OSError` (timeouts) | error | `IntervalPusher listener 1: pushing to <URL template> failed: <error>` | goes on |
| any other `Exception` | error, with the traceback | the same line | goes on |
| failed ping | warning | `IntervalPusher listener 1 could not measure the REST ping, so %ping% is -1: <error>` | pushes |

An error without a message is named by its type (aiohttp's total timeout raises a bare
`TimeoutError`). `asyncio.CancelledError` is not an `Exception`, so a cancelled loop logs nothing:
v3's `buildUrl` caught `CancellationException` and the next request logged a spurious failure.

### Loop

`Pusher(number, listener, get, ping, sleep).run()` logs
`IntervalPusher listener 1 started (every 60 seconds)` at info level, then runs
`while await self.push(): await self.sleep(interval)`: the first push at once and a fixed delay
after each attempt, so the period is the interval plus the request time, as v3's `delay` after each
iteration. `discord.ext.tasks.loop` is not used: it schedules from each start (a fixed rate).
`get`, `ping` and `sleep` are injected, so tests drive the loop with fakes and a fake clock; the cog
passes `get_status` on the listener's session, `rest_ping` on the bot and `asyncio.sleep`.

### Lifecycle

- `IntervalPusher.cog_load` creates one task per listener, named `IntervalPusher listener <n>`, and
  keeps them in `tasks`. Each task awaits `bot.wait_until_ready()`, opens its session and runs its
  `Pusher`. `setup` runs before the gateway connects, so the loops start at READY; under
  `--no-online` the bot never becomes ready and the loops are cancelled when the check unloads the
  plugins; a plugin loaded into a ready bot (a reload) pushes at once. v3 started its pushers at
  load, which v3's core ran after JDA was ready, so the first push comes at the same moment.
- `cog_unload` cancels the tasks and waits for them, so each session closes; discord.py unloads the
  extensions in `close` before it closes its own HTTP client.
- A reload (`/xincord reload`, the console or SIGHUP) unloads the cog and runs `setup` again with
  the new `config.yaml`, as v3's `reload()`; a listener stopped by a 404 starts again. A failed
  reload keeps the previous version running (core-reload).
- The loops start once per load: `on_ready` after a new gateway session changes nothing, and REST
  requests keep working while the gateway reconnects, so pushes go on as in v3.

### Tests

- `tests/plugins/interval_pusher/`: `test_plugin.py`, `test_config.py`, `test_pusher.py` (the ping,
  the status handling and the loop with fakes and a fake clock), `test_request.py` (a local HTTP
  server) and `test_lifecycle.py` (the cog loaded through the real entry point).
- `conftest.py`: `ready` (autouse) replaces `Bot.wait_until_ready` with an event that the test sets,
  standing for READY (the offline bot never logs in), and cancels the loops left running at
  teardown; `discord_requests` (autouse) records discord.py's REST requests instead of sending them.
- `tests/support/http_fakes.py`: `Monitor`, a local HTTP server (`aiohttp.test_utils.RawTestServer`)
  that answers each path with a configured status, can leave requests unanswered, and records the
  pushes; the `monitor` fixture runs it.
- No test sleeps in real time: the loop's delay goes through a fake `sleep`, and the cog tests wait
  for the monitor's requests (with a 5-second safety limit) and never reach the real delay.
- No golden data: v3 had no text, templates or component IDs.

### v3 behaved differently

- v3 behaved differently: an `interval` of 0 or less made `delay()` return at once, so the loop
  pushed without pause; such values now disable the plugin at load with `listeners.<n>.interval`
  named.
- v3 behaved differently: the URL was not checked, so a URL without a scheme, with another scheme or
  with a space failed at every push with an error log; it now disables the plugin at load with
  `listeners.<n>.url` named.
- v3 behaved differently: stopping a pusher while it waited for the ping logged a spurious `Query
  URL ... failed` error (`CancellationException` was caught); cancelling a loop now logs nothing.
- v3 behaved differently: the REST ping was requested at every push, even for URLs without
  `%ping%`; it is now requested only for URLs that use it.
- v3 behaved differently: the bundled `config.yaml` held a listener on the owner's status domain
  with a placeholder token; it now lists no listeners and shows an example on `status.example.com`.
- v3 behaved differently: a config without `listeners`, with a wrong type or with an unknown key
  stopped the whole bot (kaml strict mode), even when the plugin was disabled; an invalid file now
  disables only IntervalPusher, unknown keys warn, and a plugin that `plugins` does not list is not
  read (core-config, core-plugin-loading).
- v3 behaved differently: the log lines were `Status Monitor refused the connection! (Code: 404)!`,
  `Breaking the heartbeat loop!`, `IntervalPusher started.` and the like, without saying which
  listener; the lines are now English sentences that number the listener, at v3's levels.

Kept on purpose: the first push at once, the fixed delay, every `%ping%` replaced, `-1` for a
failed ping, no redirects, v3's timeouts, a 404 stopping only its listener until a reload or
restart, 521 and other statuses continuing, URLs in the logs, `listeners` required, independent
listeners.

## Risks / Trade-offs

- The ping uses `discord.http.Route` and `HTTPClient.request`, which discord.py does not document as
  public API (both unchanged since discord.py 1.x); if an upgrade changes them, the plugin fails to
  import or every push carries `-1` after a warning. Check the ping after upgrading discord.py.
- The period is the interval plus the ping and the request time, as in v3. discord.py retries a
  REST request that fails with a 5xx status, so a Discord outage can delay pushes by the retries;
  an Uptime Kuma monitor's heartbeat interval should leave room for that.
- Failure logs show the URL with its push token, as v3's did.
- One session per listener keeps one connection pool each; a few listeners cost nothing.

## Manual smoke checklist

With a bot token, `plugins: [IntervalPusher]` in `config.yaml` and an Uptime Kuma push monitor (or
another endpoint that shows the requests it receives):

1. Start the bot with the bundled config: the log lists `IntervalPusher` as loaded,
   `plugins/IntervalPusher/config.yaml` is the bundled default, and nothing is pushed.
2. Add the monitor's push URL with `ping=%ping%` and `interval: 60`, then run
   `/xincord reload IntervalPusher`: the log shows `IntervalPusher listener 1 started (every 60
   seconds)`, and the monitor turns up at once with a ping in milliseconds, then about every 60
   seconds.
3. Restart with `--level DEBUG`: each push logs `IntervalPusher listener 1 pushed <url>` with the
   ping, and the first push comes right after `Bot ready`.
4. Add a second listener with a wrong push token and reload: one warning with code 404 names
   listener 2, which pushes no more, while listener 1 goes on.
5. Point a listener at a closed port (`http://127.0.0.1:9/`) and reload: an error every interval,
   and the other listeners go on.
6. Set `interval: 0` or `url: status.example.com/push` and reload: the reload reports
   IntervalPusher as failed, the log names `listeners.0.interval` or `listeners.0.url`, and the
   previous listeners keep pushing.
7. Stop the bot (Ctrl+C, or `docker compose stop`): IntervalPusher logs no warning or error.
8. Run `xincord --no-online` with the listeners configured: it exits with 0 and the monitor
   receives nothing.

## User-visible changes

The plugin shows nothing in Discord. Copy: the comments of the bundled `config.yaml` and the
operator log lines (English).

1. The bundled `config.yaml` lists no listeners and shows an example in a comment (v3 shipped one
   listener on `status.xinshou.tw` with a placeholder token, disabled); a v3 file loads unchanged
   and warns `unknown key enabled`.
2. An `interval` below 1 or a `url` that is not an http or https URL with a host disables the plugin
   at load with the key named (v3: a busy loop, or an error at every push).
3. `%ping%` is measured only for URLs that contain it (v3 asked Discord at every push).
4. Stopping or reloading the plugin no longer logs a spurious error.
5. The log lines are new English sentences that number the listener; v3's levels are kept, and
   failures still show the URL with its push token.
