## Why

On 2026-10-10 the owner decided three things about UptimeHeartbeat (`HANDOFF.md` section 6). The
port kept v3's behavior: a 404 stops a listener until the plugin reloads or the bot restarts
(`listener N stopped: ...`), failure lines show the URL, whose path or query carries the push
token, and a listener that fails at every push logs a line at every push.

1. A failed push never stops a listener. Whatever fails (an HTTP error status, a redirect, a
   timeout, a connection error, an unexpected exception), the listener keeps pushing at its
   interval until the plugin unloads.
2. Logs show only the endpoint's host: the scheme and the host, plus the port if one is given,
   never the path or the query.
3. Logs stay useful without flooding: a listener failing every minute must not write a warning
   every minute forever.

## What Changes

- No failure stops a listener: a 404 is a failed push like the others, logged as a warning, and
  the loop waits `interval` seconds and pushes again until the plugin unloads.
- Log lines show a listener's URL only as its origin (scheme, host and port if given; no user
  info, path, query or fragment): the failure lines, the 404 and 521 lines (which now name it) and
  the debug line of a push that worked. URLs inside an error's text or traceback are cut to their
  origin too: aiohttp's connect timeout and its error for a malformed answer name the whole URL.
- A failure is logged at its level when it is the first since the listener started or the push
  last worked, or of another kind than the failure before (another status code or error type);
  repeats go to the debug level. The first push that works after failed ones logs one info line
  with their number. The REST ping's failures follow the same rule, with one info line when the
  ping works again.
- The bundled `config.yaml`'s comment describes this instead of the 404 stop.

Kotlin sources (v3's behavior that changes):
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:29-37`
  (the failed ping's warning)
- `XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123`
  (the status handling, the 404 stop, the URLs in the log lines, the delay)

Out of scope: following redirects (a 3xx stays a failed push, as in v3 and the port; that question
stays open in the review queue); backing off or changing the interval while a monitor fails; the
core's own messages, such as a YAML syntax error in `config.yaml`, which quotes PyYAML's snippet of
the line; a reminder while a failure lasts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-uptime-heartbeat`: no failure stops a listener; log lines show URLs as origins only; a
  failure is logged when it starts, changes kind or ends (two new requirements, three modified).

## Impact

`packages/xincord-plugins/src/xincord/plugins/uptime_heartbeat/` (`pusher.py`, a new `logs.py`,
`cog.py` docstrings, the bundled `config.yaml` comment) and its tests. No core change, no new
package and no config key: `xincord-plugins` also declares yarl, which aiohttp installs, since
`logs.py` imports it. Operators see different log lines (listed in `design.md`), and a
listener whose token is wrong or whose monitor is paused keeps sending one request per interval.
