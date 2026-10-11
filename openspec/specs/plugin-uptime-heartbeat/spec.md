# plugin-uptime-heartbeat Specification

## Purpose
Each configured listener pushes an HTTP GET to its URL, typically an Uptime Kuma push monitor, at a
fixed delay, with the bot's REST ping in the URL.

## Requirements

### Requirement: The plugin installs as UptimeHeartbeat
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `UptimeHeartbeat`, pointing to `xincord.plugins.uptime_heartbeat`, with no dependencies and
no intents. It SHALL bundle a default `config.yaml` that lists no listeners, which its first load
writes to `plugins/UptimeHeartbeat/`, and no lang files.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `UptimeHeartbeat` enabled
- **THEN** it returns `UptimeHeartbeat` from `xincord.plugins.uptime_heartbeat` with no dependencies
  and no intents

#### Scenario: First load creates the config
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/UptimeHeartbeat/config.yaml` holds the bundled default, which lists no
  listeners, and no `lang` directory is written

### Requirement: The config lists the URLs to push
`config.yaml` SHALL have a required `listeners` list whose entries have a `url`, an http or https
URL with a host once `%ping%` is a number, and an `interval` in whole seconds from 1 to 2147483647.
A config file with an `enabled` key SHALL load, with a warning that names the key. An invalid file
SHALL disable only this plugin, with an error that names the key.

#### Scenario: Config file with an enabled key
- **WHEN** `config.yaml` holds `enabled: true` and one listener whose URL ends in
  `ping=%ping%` and whose interval is 60
- **THEN** the plugin loads with that listener, and logs a warning that names `enabled`

#### Scenario: Default config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it has no listeners

#### Scenario: Invalid entries
- **WHEN** `listeners` is missing, an `interval` is 0, negative or 2147483648, or a `url` is not an
  http or https URL with a host (another scheme, no scheme, no host, a space, a bad port)
- **THEN** the plugin does not load, and the error names `listeners`, `listeners.0.interval` or
  `listeners.0.url`

### Requirement: The URL carries the REST ping
Before each push to a URL that contains `%ping%`, the plugin SHALL measure the bot's REST ping, the
round trip of a `GET /users/@me` request to Discord in whole milliseconds, and replace every
`%ping%` with it. When the measurement fails in any way, `%ping%` SHALL become `-1`, with a warning
unless the failure repeats, and the URL SHALL still be pushed. A URL without `%ping%` SHALL be
pushed as written, without the request.

#### Scenario: Ping in the URL
- **WHEN** the URL holds `%ping%` twice and the ping is 42 milliseconds
- **THEN** both become `42`

#### Scenario: Failed ping
- **WHEN** the request to Discord fails or times out
- **THEN** `%ping%` becomes `-1` and a warning is logged

#### Scenario: Unexpected ping error
- **WHEN** measuring the ping raises an unexpected error
- **THEN** `%ping%` becomes `-1`, the URL is pushed, and a warning shows the traceback

#### Scenario: No placeholder
- **WHEN** the URL has no `%ping%`
- **THEN** it is pushed as written and Discord is not asked

#### Scenario: Measured round trip
- **WHEN** a `GET /users/@me` request to Discord takes 42.4 milliseconds
- **THEN** the ping is 42

### Requirement: Each push is one GET request
Each push SHALL be one GET request to the URL that follows no redirect, limited to 10 seconds to
connect and 30 seconds in all; only the response's status code SHALL be used.

#### Scenario: Status code
- **WHEN** the monitor answers a push with 204
- **THEN** the push's status is 204, and the monitor received one GET with the URL's path and query

#### Scenario: Redirect
- **WHEN** the monitor answers a push with a 302 to another path
- **THEN** the push's status is 302, and the other path is not requested

#### Scenario: Limits
- **WHEN** the plugin opens its HTTP session
- **THEN** the session allows 10 seconds to connect and 30 seconds per request

### Requirement: The status code decides what follows
A 2xx status SHALL be logged at debug level. Any other outcome SHALL be a failed push, logged with
the URL's origin at its level unless it repeats: a 404, Uptime Kuma's answer for an unknown or
paused push token, and a 521, Cloudflare's answer when the monitor is offline, at warning level;
any other status, a network error or a timeout at error level; any other exception at error level
with its traceback. No failure SHALL stop the listener: it keeps pushing until the plugin unloads.

#### Scenario: Success
- **WHEN** the monitor answers a push with 200, and no failure came before
- **THEN** a debug line names the URL's origin and the status, nothing is logged above debug
  level, and the listener keeps pushing

#### Scenario: Not found
- **WHEN** the monitor answers a push with 404
- **THEN** a warning names the URL's origin and says that the status monitor refused the push, and
  the listener keeps pushing

#### Scenario: Monitor offline
- **WHEN** the monitor answers a push with 521
- **THEN** a warning names the URL's origin and says that the status monitor is offline, and the
  listener keeps pushing

#### Scenario: Other status
- **WHEN** the monitor answers a push with 500 or 302
- **THEN** an error names the URL's origin and the status, and the listener keeps pushing

#### Scenario: Network error
- **WHEN** a push cannot connect or times out
- **THEN** an error names the URL's origin and the error, and the listener keeps pushing

#### Scenario: Unexpected error
- **WHEN** a push fails in another way
- **THEN** the error is logged with its traceback, and the listener keeps pushing

### Requirement: Each listener pushes at once, then after a fixed delay
Each listener's loop SHALL push as soon as it starts, then wait `interval` seconds after each
attempt, whatever its outcome and however long it took, so that the period is the interval plus
the request time. Listeners SHALL be independent: one that waits for a monitor or fails
SHALL not delay or stop the others.

#### Scenario: First push at once
- **WHEN** a listener's loop starts
- **THEN** it pushes before it waits

#### Scenario: Fixed delay
- **WHEN** each push of a listener whose interval is 60 seconds takes 30 seconds
- **THEN** its pushes start at 0, 90 and 180 seconds

#### Scenario: Pushing goes on after a failure
- **WHEN** a listener's push answers 404 or another status that is not 2xx, or fails
- **THEN** the listener waits `interval` seconds and pushes again

#### Scenario: Independent listeners
- **WHEN** one listener's monitor does not answer and another's answers 404
- **THEN** a third listener still pushes, and no listener's loop ends

### Requirement: Pushing follows the bot's readiness and the plugin's lifetime
When the plugin loads, it SHALL start one loop per listener that waits until the bot is ready, so
that nothing is pushed or measured before the gateway is ready or during an offline check, and a
plugin loaded into a ready bot pushes at once. Unloading the plugin SHALL cancel the loops without
logging a warning or an error, and a reload SHALL start the loops of the new config.

#### Scenario: Before ready
- **WHEN** the plugin has loaded with listeners and the bot is not ready
- **THEN** nothing is pushed, and Discord is not asked for the ping

#### Scenario: Ready
- **WHEN** the bot becomes ready
- **THEN** each listener pushes once at once, with the measured ping in its URL

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads while the bot is ready, as after `/xincord reload UptimeHeartbeat`
- **THEN** each listener pushes at once

#### Scenario: Unloaded during a push
- **WHEN** the plugin unloads while a push or a ping waits for an answer
- **THEN** the loops end, and the plugin logs no warning or error

#### Scenario: Reload
- **WHEN** the plugin unloads and loads again with a changed config
- **THEN** the old listeners' loops have ended, and the new listeners push at once

### Requirement: Logs show only the URL's origin
The plugin's log lines SHALL show a listener's URL only as its origin: its scheme, its host and its
port if the URL gives one, without the user info, the path, the query or the fragment, which can
carry the push token. In an error's text or traceback, each http or https URL SHALL be cut to its
origin, and the listener URL's user info, path, query and fragment SHALL be removed wherever they
appear. A config error SHALL not show a listener's URL.

#### Scenario: Pushes that fail or work
- **WHEN** pushes to `https://status.example.com/api/push/<token>?status=up&ping=%ping%` fail in
  each way or work
- **THEN** the log lines name `https://status.example.com`, and none holds the token

#### Scenario: Port and user info
- **WHEN** a push to `http://user:secret@127.0.0.1:3001/api/push/<token>` fails
- **THEN** the log line names `http://127.0.0.1:3001`, and neither `secret` nor the token

#### Scenario: URL in an error's text
- **WHEN** aiohttp's connect timeout, or its error for a malformed answer, names the whole URL
- **THEN** the logged error names only the URL's origin

#### Scenario: URL in a traceback
- **WHEN** an unexpected error's message holds the whole URL
- **THEN** the logged traceback names only the URL's origin

#### Scenario: Answer that quotes the request
- **WHEN** a server's malformed answer quotes the request line, with the URL's path and query
- **THEN** the logged error shows neither the path nor the query

#### Scenario: Invalid URL in the config
- **WHEN** a listener's url has a space, or user info that makes its port unreadable
- **THEN** the plugin does not load, the error names `listeners.0.url`, and no log line holds the
  URL's path, query or user info

### Requirement: A failure is logged when it starts, changes or ends
A failed push or ping SHALL be logged at its level only when its kind (the status code or the
error's type) is new in the step's failure episode, which starts with a failure and ends once the
step has worked three times in a row; other failures SHALL be logged at debug level. The end of a
push episode SHALL log one info line with its number of failed pushes, and the end of a ping
episode one info line.

#### Scenario: Repeated failure
- **WHEN** a listener's pushes answer 500 three times
- **THEN** one error is logged, and the two repeats only at debug level

#### Scenario: Another kind of failure
- **WHEN** a listener's pushes answer 500, then 500, then cannot connect, then answer 404
- **THEN** three failures are logged at their levels: the first 500, the connection error and the
  404

#### Scenario: Alternating kinds
- **WHEN** a listener's pushes answer 502, 504, 502 and 504
- **THEN** two errors are logged: the first 502 and the first 504

#### Scenario: Pushing works again
- **WHEN** a listener's pushes answer 500 twice, then 200 three times, then 500
- **THEN** after the third 200 an info line says that pushing works again after 2 failed pushes,
  and the last 500 is logged as an error again

#### Scenario: Flapping
- **WHEN** a listener's pushes answer 500 and 200 in turn, three times each
- **THEN** one error is logged, and no info line

#### Scenario: Ping fails repeatedly
- **WHEN** the ping fails at three pushes in a row with the same error, then works three times
- **THEN** one warning is logged, and one info line when the ping works again
