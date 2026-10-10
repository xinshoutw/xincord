## Why

Decision C1 ports IntervalPusher after WelcomeByeGuild, and F3 lists it as in use. v3's
IntervalPusher (`Plugins/IntervalPusher`, 3 Kotlin files, 206 lines) is a heartbeat pusher with no
commands, text, components or storage: for each configured listener it sends an HTTP GET to a URL,
typically an Uptime Kuma push monitor, every `interval` seconds, with `%ping%` replaced by the
bot's Discord REST ping. It is the first port with a background loop and outgoing HTTP.

## What Changes

- New plugin package `xincord.plugins.interval_pusher`, registered as `IntervalPusher`, with no
  intents beyond discord.py's defaults, no lang files and a bundled `config.yaml` that lists no
  listeners, with an example in a comment (v3 shipped one listener on the owner's status domain).
- `config.yaml` keeps v3's shape (`listeners[].url`, `listeners[].interval`), so v3 files load
  unchanged and v3's `enabled` key only warns. Two v3 defects are fixed at load: an `interval` below
  1 second (a busy loop in v3) and a `url` that is not an http or https URL (an error at every push
  in v3) disable the plugin with an error that names the key.
- One loop per listener starts when the bot is ready, or at once when the plugin loads into a ready
  bot, and nothing is pushed during an offline check (`--no-online`). Each loop pushes at once,
  then waits `interval` seconds after each attempt, as v3's fixed delay.
- `%ping%` becomes the round trip of a `GET /users/@me` request in whole milliseconds (JDA's REST
  ping; discord.py has none), or `-1` when it fails; the ping is measured only for URLs that use it.
- Each push is a GET that follows no redirect, with v3's 10-second connect and 30-second request
  limits, through aiohttp (installed with discord.py, now declared by `xincord-plugins`). A 2xx
  status continues; a 404 stops that listener until a reload or restart; a 521 logs a warning;
  any other status and network errors log an error; the loop goes on in each of those cases.
- Unloading the plugin cancels the loops without the spurious error v3 logged on stop; a reload
  restarts them from the new config.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-54`
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:15-136`
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/config/ConfigSerializer.kt:5-15`
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/resources/config.yaml:1-4`
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/resources/info.yaml:1-8`

Out of scope: other placeholders in the URL (v3 replaced `%ping%` only); custom headers,
authentication or methods other than GET (v3 had none); following redirects (v3 did not); the
response body (v3 read it and ignored it); the gateway latency as `%ping%`; the Web Dashboard's
reload path (B13).

## Capabilities

### New Capabilities

- `plugin-interval-pusher`: the IntervalPusher plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/interval_pusher/` and its entry point in
`packages/xincord-plugins/pyproject.toml`, which also declares `aiohttp` (already installed with
discord.py; `uv.lock` records the new direct dependency); tests under
`tests/plugins/interval_pusher/`, with a local HTTP server from `aiohttp.test_utils` standing for
the status monitor. No core changes. When enabled with listeners, the bot sends one HTTP request per
listener per interval to the configured URLs and one `GET /users/@me` to Discord for each push whose
URL uses `%ping%`.
