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

- `logs.py` (new, pure, tested without discord.py): `origin(url)`, `private_parts(url)`,
  `redact(text, *urls)` and `Failures`.
- `pusher.py`: `Pusher.run` loops until it is cancelled; `Pusher.push` returns nothing and hands
  each outcome to `Pusher.failed` or `Pusher.worked`, which log it (v3's status handling, in
  `follow` until now); each `Pusher` has a `Failures` for its pushes and one for its pings;
  `Pusher.endpoint` is the origin of the configured URL.
- `xincord-plugins` declares `yarl>=1.25.1`, the version installed with aiohttp, because `logs.py`
  imports it (as it declares aiohttp).
- `config.py`: the models hide their input in validation errors, and an unreadable URL gets a fixed
  message. `cog.py`: the loops' `sleep` is an attribute that tests replace. The bundled
  `config.yaml`: its comment.

### No failure stops a listener

`Pusher.run` logs its start line, then `while True: await self.push(); await self.sleep(interval)`.
The loop ends only when the plugin unloads and cancels it (`cog_unload`). A 404, Uptime Kuma's
answer for an unknown or paused push token, is a failed push logged as a warning: a paused monitor
that is resumed finds the next push. A 521 stays a warning, other statuses (3xx included) and
network errors stay errors, any other `Exception` an error with its traceback.
`asyncio.CancelledError` is still not caught. A failed ping, whatever its error, puts `-1` in the
URL and the push goes on, as in v3, whose `buildUrl` caught every `Exception`; an error outside
Discord's, aiohttp's and the network's adds its traceback to the warning.

### Origins and private parts

- `origin(url)`: the scheme in lower case, `://`, and the authority (up to the first `/`, `?` or
  `#`) without its user info (everything up to the last `@`): `https://status.example.com`,
  `http://127.0.0.1:3001`, `https://[::1]:3001`. It uses string operations only and never raises;
  `urlsplit(...).port` would raise for a port that `%ping%` replaced with `-1`. `Pusher.endpoint`
  is the origin of the configured URL, so a listener's lines always show the same text, a
  `%ping%` in the authority included.
- `private_parts(url)`: what logs must not show of a URL, longest first: its user info, its path,
  query and fragment together, without the fragment, and each alone, as written and as yarl encodes
  them (what aiohttp sends).
- `redact(text, *urls)`: every `https?://` URL in the text (any case), up to the next whitespace,
  becomes its origin, and the quotes that end it stay, so `url='<url>'` stays quoted; cutting the
  whole run of non-space characters, rather than stopping at a quote, leaves nothing of a path that
  holds one. Then every private part of `urls` is replaced with `...` wherever it appears: a
  server's malformed answer can quote the request line (`b'GET /api/push/<token>?... HTTP/1.1'`)
  or a `Location` with the path, and aiohttp puts that into its error.
- A network error's text is `redact(describe(error), <configured URL>, <pushed URL>)`. An
  unexpected error's traceback is formatted with `traceback.format_exception(error)` and redacted
  the same way, then logged as part of the message: `logger.exception` would let the handler print
  the exception's text as it is. The record has no `exc_info`.
- The debug line of a push that worked names the origin and the status code; v3's showed the URL
  with the ping and the token.
- Config errors: `Config` and `Listener` set pydantic's `hide_input_in_errors`, so the validation
  error that the core chains to its `ConfigError` (and logs with its traceback) shows no
  `input_value`, which held up to 49 characters of the URL; `_push_url` raises a fixed message
  for a URL whose host or port cannot be read (urlsplit's error quoted the text after the last
  `:`, a password's end included), from None.

### Failures logged when they start, change or end

Each step of a listener (its pushes, its pings) has failure episodes. An episode starts with a
failure and ends once the step has worked three times in a row (`STEADY`). `Failures` keeps the
open episode: `kinds` (the kinds logged in it: status codes and exception types), `count` (its
failures) and `streak` (successes in a row since its last failure). `fail(kind)` counts a failure
and returns whether its kind is new in the episode; `succeed()` counts a success and returns the
episode's number of failures when that success ends it, else 0.

- A failure whose kind is new in the episode is logged at its level; any other at debug level,
  with the same text, so that `--level DEBUG` still shows every attempt.
- The end of a push episode logs, at info level, `UptimeHeartbeat listener 1: pushing to
  https://status.example.com works again after 3 failed pushes` (`1 failed push` for one), before
  the debug line of the push that ended it; the end of a ping episode logs `UptimeHeartbeat
  listener 1 measures the REST ping again`.
- A steady failure logs one line; kinds that alternate (502 and 504 from a proxy, 521 and 522 from
  Cloudflare, a refused connection and a connect timeout from a dead host) log one line each; a
  step that fails and works in turn logs its first failure and nothing more until it works three
  times in a row. The price: a recovery is announced two intervals after the first push that
  works.
- The state belongs to the `Pusher`: a reload builds a new cog, so a failure that lasts across a
  reload is logged again, and a recovery right after a reload logs no info line (the reload logs
  the listener's start line).

### Log lines

| Outcome | Level when new | Line |
|---|---|---|
| start (unchanged) | info | `UptimeHeartbeat listener 1 started (every 60 s)` |
| 2xx | debug | `UptimeHeartbeat listener 1 pushed to https://status.example.com (code 200)` |
| third 2xx in a row after failures | info | `UptimeHeartbeat listener 1: pushing to https://status.example.com works again after 3 failed pushes` |
| 404 | warning | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 404 (the status monitor refused the push)` |
| 521 | warning | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 521 (the status monitor is offline)` |
| other status | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed with code 500` |
| `aiohttp.ClientError`, `OSError` (timeouts) | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed: <error text, redacted>` |
| other `Exception` | error | `UptimeHeartbeat listener 1: pushing to https://status.example.com failed`, a newline and the traceback, redacted |
| failed ping (unchanged) | warning | `UptimeHeartbeat listener 1 could not measure the REST ping, so %ping% is -1: <error>` |
| unexpected ping error | warning | `UptimeHeartbeat listener 1 could not measure the REST ping, so %ping% is -1`, a newline and the traceback |
| third ping in a row after failures | info | `UptimeHeartbeat listener 1 measures the REST ping again` |

A failure whose kind is not new in its episode logs its line at debug level.

### Bundled config.yaml

The comment's last sentence, `A 404 answer stops that listener until the plugin reloads or the bot
restarts.`, becomes `A failed push never stops a listener. The log shows only each url's scheme,
host and port, and logs each kind of failure once until pushing has worked three times in a row,
then says that it works again.` An operator's existing `plugins/UptimeHeartbeat/config.yaml` keeps
its old comment.

### Tests (xfail-first)

- `tests/plugins/uptime_heartbeat/test_logs.py`: `origin`, `private_parts`, `redact` and
  `Failures`, against stubs (`raises=NotImplementedError`).
- `test_pusher.py`: the lines with origins, a token that no line holds at debug level, loops that
  go on after each kind of failure, repeats, changes and alternations of kind, flapping, the lines
  when pushing and the ping work again three times in a row, an unexpected ping error. These run
  through `Pusher.push` and `Pusher.run`, which work already, so their markers have no `raises` and
  they fail on their assertions. `Fakes` takes `pings`, a sequence like `answers`, instead of
  `ping_ms`.
- `test_request.py`: local TCP servers answer garbage, or quote the request line as their status
  line; aiohttp's real `ClientResponseError` reaches the log without the path, query or token.
- `test_config.py`: invalid URLs (a space, a password that hides the port) disable the plugin with
  `listeners.0.url` named, and no log line, tracebacks included, holds the token or the password.
- `test_lifecycle.py`: of three listeners, the one answered 404 reaches its next sleep, which the
  test replaces, and no loop ends.
- A scratch probe (not committed) ran pushers through aiohttp on 2026-10-10: a local monitor
  answering 404, 404, 200, 521, 521, 302 and 200 while the ping failed twice, a server answering
  garbage, a closed port, a TLS handshake that never answered (connect limit 0.3 seconds) and an
  unexpected error that named the URL. Each failure was logged once at its level and repeated at
  debug level, and the log held neither the token nor the user info (`Connection timeout to host
  https://127.0.0.1:<port>`, `url='http://127.0.0.1:<port>'`). It ran before the cross-review
  changed the episodes, so its recoveries came at the first push that worked.
- Packaging, checked on 2026-10-10: the wheel from `uv build --package xincord-plugins` lists
  `logs.py` with the other modules and `config.yaml`, and `docker compose run --rm -T bot
  --no-online` on a fresh image, with `plugins: [UptimeHeartbeat]` and one listener in a temporary
  `bot/`, exited 0 with `Plugins loaded: UptimeHeartbeat`, pushed nothing and printed no token;
  `docker compose down -v` and removing `bot/` cleaned up.

### Cross-review

A subagent reviewed the change on 2026-10-10 after the first push. Its findings and what was done:

- Medium: config errors still showed the URL (pydantic's `input_value` in the chained traceback,
  urlsplit's port error): fixed (Origins and private parts).
- Medium: the policy compared a failure with the previous one only, so alternating kinds and a
  step that failed and worked in turn logged at every push: fixed with episodes.
- Low: aiohttp texts that quote the server's answer (the parser's bad line, the partial response of
  `ServerDisconnectedError`) carried the path without a scheme: the private parts are removed.
- Low: a ping error outside `PING_ERRORS` skipped the push: every ping error now gives `-1`.
- Low: `test_independent_listeners` checked a task once, right after the 404 line: it now waits
  for that listener's next sleep.
- Low: a task that ends by a `BaseException` other than the unload's cancellation is not logged:
  unchanged, since no `Exception` ends a loop and asyncio's own errors end the bot; recorded under
  Risks.
- Low: wording in the delta and the audit: fixed.

### Audit

Every scenario of the delta has a test (`tests/plugins/uptime_heartbeat/`):

- The URL carries the REST ping: `test_ping_in_the_url`, `test_failed_ping`,
  `test_unexpected_ping_error`, `test_no_placeholder`, `test_measured_round_trip`.
- The status code decides what follows: `test_success`, `test_not_found`, `test_monitor_offline`,
  `test_other_status`, `test_network_error`, `test_unexpected_error`; that the listener keeps
  pushing: `test_first_push_at_once` after successes, `test_pushing_goes_on_after_a_404` and
  `test_every_attempt_is_followed_by_the_delay` after failures.
- Each listener pushes at once, then after a fixed delay: `test_first_push_at_once`,
  `test_fixed_delay`, `test_pushing_goes_on_after_a_404`,
  `test_every_attempt_is_followed_by_the_delay`, `test_independent_listeners`.
- Logs show only the URL's origin: `test_pushes_that_fail_or_work`, `test_port_and_user_info`,
  `test_url_in_an_errors_text`, `test_malformed_answer` (real aiohttp), `test_url_in_a_traceback`,
  `test_answer_that_quotes_the_request` (real aiohttp), `test_invalid_url_in_the_config`, and
  `test_origin`, `test_private_parts` and `test_redact` for the functions.
- A failure is logged when it starts, changes or ends: `test_repeated_failure`,
  `test_another_kind_of_failure`, `test_alternating_kinds`, `test_pushing_works_again`,
  `test_flapping`, `test_ping_fails_repeatedly`, and the `Failures` tests in `test_logs.py`.

## v3 behaved differently

- v3 behaved differently: a 404 stopped the listener until a reload or restart (`Breaking the
  heartbeat loop!`); every failure now keeps the listener pushing at its interval until the plugin
  unloads (the owner's decision of 2026-10-10).
- v3 behaved differently: the failure lines and the debug line showed the URL with its push token;
  the lines now show only its origin (scheme, host, port), and URLs in error texts and tracebacks
  are cut the same way.
- v3 behaved differently: every failed push and every failed ping logged a line, so a monitor that
  stayed down for a day logged 1440 errors per listener at a 60-second interval; each kind of
  failure is now logged once per episode, repeats go to the debug level, and one info line says
  when pushing or the ping has worked three times in a row again.
- v3 behaved differently: a failed ping pushed `-1` whatever the error; the port skipped the push
  after an error outside Discord's and the network's, and now pushes `-1` again.

## User-visible changes (for the owner)

The plugin still shows nothing in Discord. Changes in the log and in the bundled `config.yaml`:

1. A listener keeps pushing after a 404 (an unknown or paused push token) and after any other
   failure; `UptimeHeartbeat listener N stopped: ...` is gone.
2. Log lines show a listener's URL only as its origin, `https://status.example.com` (scheme, host,
   port if given; never the user info, path or query), and the 404 and 521 lines now name it.
3. Each kind of failure (status code, error type) is logged once per episode; repeats only at
   debug level; once pushing has worked three times in a row, one info line says that it works
   again, with the number of failed pushes, and one says when the REST ping works again.
4. The debug line of a push that worked is `UptimeHeartbeat listener 1 pushed to
   https://status.example.com (code 200)` (was the whole URL, ping and token included).
5. An unexpected error's traceback is part of its error line's text.
6. The bundled `config.yaml`'s comment describes this instead of the 404 stop.
7. A config error for an invalid `url` no longer quotes it: the line names `listeners.<n>.url`
   and says what is wrong, and a URL whose host or port cannot be read gets a fixed message.

## Manual smoke checklist

With a bot token, `plugins: [UptimeHeartbeat]` and an Uptime Kuma push monitor. Steps 4 and 5 of
the port's checklist (`openspec/changes/archive/2026-10-10-port-interval-pusher/design.md`), which
expected a 404 to stop the listener and an error at every interval, are replaced by these:

1. Add a second listener with a wrong push token and reload: one warning names listener 2, the
   status host and code 404, and nothing more is logged for it at the default level while it keeps
   failing; with `--level DEBUG`, each of its pushes logs a debug line.
2. Pause the first monitor in Uptime Kuma: one warning with code 404 for listener 1. Resume it:
   the monitor turns up at the next push, and after the third push in a row that works, an info
   line says that pushing works again after the number of failed pushes.
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
- Redaction cuts URLs by their `http://` or `https://` and removes the listener URL's private parts
  as written and as yarl encodes them; a server that quoted them in another form (the Basic
  authorization header made of the user info, a token alone) would pass. aiohttp 3.14.4's texts
  name the URL with its scheme (Context), and the tests with a malformed and a quoting answer run
  the real aiohttp. Check after upgrading aiohttp.
- A recovery is announced two intervals late, and a step that fails and works in turn stays quiet
  after its first failure; the status monitor shows both as they happen.
- A loop ends only by a `BaseException` other than `Exception`: the unload's cancellation, or
  KeyboardInterrupt and SystemExit, which stop the bot. Nothing logs such an end of one loop.
- The core reports a YAML syntax error in `config.yaml` with PyYAML's snippet of the faulty line
  (about 30 characters after the error), which can show the start of a listener's URL; that is the
  core's message about the operator's own file and stays as it is (review queue).
