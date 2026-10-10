## MODIFIED Requirements

### Requirement: The URL carries the REST ping
Before each push to a URL that contains `%ping%`, the plugin SHALL measure the bot's REST ping, the
round trip of a `GET /users/@me` request to Discord in whole milliseconds, and replace every
`%ping%` with it, or with `-1` when the request fails, which logs a warning unless it repeats. A
URL without `%ping%` SHALL be pushed as written, without the request.

#### Scenario: Ping in the URL
- **WHEN** the URL holds `%ping%` twice and the ping is 42 milliseconds
- **THEN** both become `42`

#### Scenario: Failed ping
- **WHEN** the request to Discord fails or times out
- **THEN** `%ping%` becomes `-1` and a warning is logged

#### Scenario: No placeholder
- **WHEN** the URL has no `%ping%`
- **THEN** it is pushed as written and Discord is not asked

#### Scenario: Measured round trip
- **WHEN** a `GET /users/@me` request to Discord takes 42.4 milliseconds
- **THEN** the ping is 42

### Requirement: The status code decides what follows
A 2xx status SHALL be logged at debug level. Any other outcome SHALL be a failed push, logged with
the URL's origin unless it repeats: a 404, Uptime Kuma's answer for an unknown or paused push
token, and a 521, Cloudflare's answer when the monitor is offline, as warnings; any other status, a
network error or a timeout as an error; any other exception as an error with its traceback. No
failure SHALL stop the listener: it keeps pushing until the plugin unloads.

#### Scenario: Success
- **WHEN** the monitor answers a push with 200
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
the request time, as in v3. Listeners SHALL be independent: one that waits for a monitor or fails
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

## ADDED Requirements

### Requirement: Logs show only the URL's origin
The plugin's log lines SHALL show a listener's URL only as its origin: its scheme, its host and its
port if the URL gives one, without the user info, the path, the query or the fragment, which can
carry the push token. An http or https URL in an error's text or traceback SHALL be cut to its
origin in the same way.

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

### Requirement: A failure is logged when it starts, changes or ends
A listener SHALL log a failed push or ping at its level only when it is that step's first failure
since the listener started or the step last worked, or when its kind (the status code or the
error's type) differs from the step's previous failure; a repeat SHALL be logged at debug level.
The first push that works after failed ones SHALL log one info line with their number, and the
first ping that works after failed ones one info line.

#### Scenario: Repeated failure
- **WHEN** a listener's pushes answer 500 three times
- **THEN** one error is logged, and the two repeats only at debug level

#### Scenario: Another kind of failure
- **WHEN** a listener's pushes answer 500, then 500, then cannot connect, then answer 404
- **THEN** three failures are logged at their levels: the first 500, the connection error and the
  404

#### Scenario: Pushing works again
- **WHEN** a listener's pushes answer 500 twice, then 200, then 500
- **THEN** an info line says that pushing works again after 2 failed pushes, and the last 500 is
  logged as an error again

#### Scenario: Ping fails repeatedly
- **WHEN** the ping fails at three pushes in a row with the same error, then works
- **THEN** one warning is logged, and one info line when the ping works again
