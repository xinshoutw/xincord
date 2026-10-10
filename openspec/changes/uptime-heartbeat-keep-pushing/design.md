## Context

UptimeHeartbeat (`xincord.plugins.uptime_heartbeat`, v3's IntervalPusher, ported in
`port-interval-pusher` and renamed in `rename-plugins`) runs one loop per listener: push the URL
with `%ping%` replaced, log the outcome, wait `interval` seconds. It kept v3's handling
(`IntervalPusher.kt:99-123`): a 404 ends the loop with `UptimeHeartbeat listener N stopped: ...`
until the plugin reloads or the bot restarts; other statuses, network errors and unexpected
exceptions are logged and the loop goes on; failure lines show the URL, push token included, and
the debug line of a push that worked shows it with the ping; every failed push logs a line.

On 2026-10-10 the owner decided (`HANDOFF.md` section 6, and the task of this change): no failure
stops a listener; logs show only the endpoint's scheme, host and port; a listener failing every
minute must not log a warning every minute forever, with the policy chosen here and listed in the
review queue.

aiohttp 3.14.4's error texts, checked with a scratch probe on 2026-10-10: a connection that does
not complete within the connect limit (here a TLS handshake that never answers) raises
`ConnectionTimeoutError` with `Connection timeout to host https://127.0.0.1:<port>/api/push/<token>?...`;
a malformed answer raises `ClientResponseError` with `400, message="Bad status line: ...",
url='http://127.0.0.1:<port>/api/push/<token>?...'` (without the URL's user info); a refused
connection and a failed DNS lookup raise `ClientConnectorError` with `Cannot connect to host
<host>:<port> ssl:default [...]`; the 30-second total limit raises a bare `TimeoutError`.
`InvalidUrlClientError`'s text is the URL. So hiding the URL from the plugin's own lines is not
enough: the error texts that follow them name it too.

## Goals / Non-Goals

**Goals:** the three decisions, test-first; log lines that still tell the operator which listener
failed, where it pushes and why; no push token, user info, path or query in any line the plugin
logs.

**Non-Goals:** following redirects (a 3xx stays a failed push; the question stays open in the
review queue); backing off or changing the interval while a monitor fails; a reminder while a
failure lasts; the core's messages (see Risks).

## Decisions

### Modules

- `logs.py` (new, pure, tested without discord.py): `origin(url)`, `redact(text)` and `Failures`.
- `pusher.py`: `Pusher.run` loops until it is cancelled; `Pusher.push` returns nothing; each
  `Pusher` has a `Failures` for its pushes and one for its pings; `Pusher.endpoint` is the origin
  of the configured URL. The status handling moves from `follow` into `push`.
- `cog.py`: unchanged but for its docstrings; the bundled `config.yaml`: its comment.

### No failure stops a listener

`Pusher.run` logs its start line, then `while True: await self.push(); await self.sleep(interval)`.
The loop ends only when the plugin unloads and cancels it (`cog_unload`), as before. A 404,
Uptime Kuma's answer for an unknown or paused push token, is a failed push logged as a warning: a
paused monitor that is resumed finds the next push. A 521 stays a warning, other statuses (3xx
included) and network errors stay errors, any other `Exception` an error with its traceback.
`asyncio.CancelledError` is still not caught.

### Origins

- `origin(url)`: the scheme in lower case, `://`, and the authority (up to the first `/`, `?` or
  `#`) without its user info (everything up to the last `@`): `https://status.example.com`,
  `http://127.0.0.1:3001`, `https://[::1]:3001`. It uses string operations only and never raises;
  `urlsplit(...).port` would raise for a port that `%ping%` replaced with `-1`. `Pusher.endpoint`
  is the origin of the configured URL, so a listener's lines always show the same text, a
  `%ping%` in the authority included.
- `redact(text)`: every `https?://` URL in the text (any case), up to the next whitespace, becomes
  its origin; quotes that end the match are kept, so `url='<url>'` stays quoted. Cutting the whole
  run of non-space characters, rather than stopping at a quote, leaves nothing of a path that holds
  one.
- A network error's text is `redact(describe(error))`. An unexpected error's traceback is
  formatted with `traceback.format_exception(error)`, redacted and logged as part of the message:
  `logger.exception` would let the handler print the exception's text as it is. The record has no
  `exc_info`.
- The debug line of a push that worked names the origin and the status code; v3's showed the URL
  with the ping and the token.

### Failures logged when they start, change or end

`Failures` is a small mutable dataclass: `kind` (the previous failure's status code or exception
type; None while the step works) and `count` (failures since the step last worked). `add(kind)`
counts a failure and returns whether it is new: the first, or of another kind than the previous
one. `clear()` returns the count and resets both.

- A new failure is logged at its level; a repeat is logged at debug level with the same text, so
  that `--level DEBUG` still shows every attempt.
- The first push that works after failed ones logs, at info level,
  `UptimeHeartbeat listener 1: pushing to https://status.example.com works again after 3 failed
  pushes` (`1 failed push` for one), then its debug line.
- The REST ping follows the same rule with its own `Failures` (a failed ping does not fail the
  push, which carries `-1`): the first failure or a new kind logs the warning, repeats go to debug,
  and the first ping that works logs `UptimeHeartbeat listener 1 measures the REST ping again`.
- Kinds are fine-grained: each status code and each exception type. A 500 followed by a 502 is
  logged twice; a refused connection whose text names another address is not logged again.
- The state belongs to the `Pusher`: a reload builds a new cog, so the first failure after a reload
  is logged again.

### Log lines

| Outcome | Level when new | Line |
|---|---|---|
| start (unchanged) | info | `UptimeHeartbeat listener 1 started (every 60 s)` |
| 2xx | debug | `UptimeHeartbeat listener 1 pushed to https://status.example.com (code 200)` |
| 2xx after failures | info | `UptimeHeartbeat listener 1: pushing to https://status.example.com works again after 3 failed pushes` |
| 404 | warning | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 404 (the status monitor refused the push)` |
| 521 | warning | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 521 (the status monitor is offline)` |
| other status | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 500` |
| `aiohttp.ClientError`, `OSError` (timeouts) | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed: <error text, URLs cut>` |
| other `Exception` | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed`, a newline and the traceback, URLs cut |
| failed ping (unchanged) | warning | `UptimeHeartbeat listener 1 could not measure the REST ping, so %ping% is -1: <error>` |
| ping works after failures | info | `UptimeHeartbeat listener 1 measures the REST ping again` |

A repeated failure logs its line at debug level.

### Bundled config.yaml

The comment's last sentence, `A 404 answer stops that listener until the plugin reloads or the bot
restarts.`, becomes `A failed push never stops a listener. The log shows only each url's scheme,
host and port, and logs a failure when it starts or changes, then once when pushing works again.`
An operator's existing `plugins/UptimeHeartbeat/config.yaml` keeps its old comment.

### Tests (xfail-first)

- `tests/plugins/uptime_heartbeat/test_logs.py`: `origin`, `redact` and `Failures`, against stubs
  (`raises=NotImplementedError`).
- `test_pusher.py`: the lines with origins, a token that no line holds at debug level, loops that
  go on after each kind of failure, repeats, changes of kind, the lines when pushing and the ping
  work again. These run through `Pusher.push` and `Pusher.run`, which work already, so their
  markers have no `raises` and they fail on their assertions. `Fakes` takes `pings`, a sequence
  like `answers`, instead of `ping_ms`.
- `test_request.py`: a local TCP server answers garbage; aiohttp's real `ClientResponseError`
  reaches the log with the origin only.
- `test_lifecycle.py`: of three listeners, the one answered 404 keeps its loop after the warning.

## v3 behaved differently

- v3 behaved differently: a 404 stopped the listener until a reload or restart (`Breaking the
  heartbeat loop!`); every failure now keeps the listener pushing at its interval until the plugin
  unloads (the owner's decision of 2026-10-10).
- v3 behaved differently: the failure lines and the debug line showed the URL with its push token;
  the lines now show only its origin (scheme, host, port), and URLs in error texts and tracebacks
  are cut the same way.
- v3 behaved differently: every failed push and every failed ping logged a line, so a monitor that
  stayed down for a day logged 1440 errors per listener at a 60-second interval; a failure is now
  logged when it starts or changes kind, repeats go to the debug level, and one info line says when
  pushing or the ping works again.

## User-visible changes (for the owner)

The plugin still shows nothing in Discord. Changes in the log and in the bundled `config.yaml`:

1. A listener keeps pushing after a 404 (an unknown or paused push token) and after any other
   failure; `UptimeHeartbeat listener N stopped: ...` is gone.
2. Log lines show a listener's URL only as its origin, `https://status.example.com` (scheme, host,
   port if given; never the user info, path or query), and the 404 and 521 lines now name it.
3. A failure is logged when it starts or changes kind; repeats only at debug level; one info line
   when pushing works again, with the number of failed pushes, and one when the REST ping works
   again.
4. The debug line of a push that worked is `UptimeHeartbeat listener 1 pushed to
   https://status.example.com (code 200)` (was the whole URL, ping and token included).
5. An unexpected error's traceback is part of its error line's text.
6. The bundled `config.yaml`'s comment describes this instead of the 404 stop.

## Manual smoke checklist

With a bot token, `plugins: [UptimeHeartbeat]` and an Uptime Kuma push monitor. Steps 4 and 5 of
the port's checklist (`openspec/changes/archive/2026-10-10-port-interval-pusher/design.md`), which
expected a 404 to stop the listener and an error at every interval, are replaced by these:

1. Add a second listener with a wrong push token and reload: one warning names listener 2, the
   status host and code 404, and nothing more is logged for it at the default level while it keeps
   failing; with `--level DEBUG`, each of its pushes logs a debug line.
2. Pause the first monitor in Uptime Kuma: one warning with code 404 for listener 1. Resume it:
   within one interval, an info line says that pushing works again after the number of failed
   pushes, and the monitor turns up.
3. Point a listener at a closed port (`http://127.0.0.1:9/api/push/x`) and reload: one error at
   its first push and nothing more at the default level; the other listeners go on.
4. Point a listener at an address that does not answer (`https://10.255.255.1/api/push/x`) and
   reload: after 10 seconds, one error that names `https://10.255.255.1` twice
   (`Connection timeout to host https://10.255.255.1`) and not the path.
5. Search the log for the push tokens (`docker compose logs bot | grep -c <token>`): no line.

## Risks / Trade-offs

- A listener with a wrong token or a paused monitor sends one GET per interval for as long as the
  plugin runs, where v3 stopped after one 404; Uptime Kuma answers it at once.
- A lasting failure is logged once at the default level: the status monitor shows the bot as down,
  but the log's first line can rotate away (json-file, 10 MB x 3). A reminder at a long period is
  the alternative listed in the review queue.
- Redaction finds URLs by their `http://` or `https://`: a text that named the path without them
  would pass. aiohttp 3.14.4's texts name the URL with its scheme (Context), and `OSError` texts do
  not name it; the test with a malformed answer runs the real aiohttp. Check after upgrading
  aiohttp.
- The core reports a YAML syntax error in `config.yaml` with PyYAML's snippet of the faulty line
  (about 30 characters after the error), which can show the start of a listener's URL; that is the
  core's message about the operator's own file and stays as it is (review queue).
