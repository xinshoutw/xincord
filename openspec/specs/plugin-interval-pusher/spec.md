# plugin-interval-pusher Specification

## Purpose
Each configured listener pushes an HTTP GET to its URL, typically an Uptime Kuma push monitor, at a
fixed delay, with the bot's REST ping in the URL.

## Requirements

### Requirement: The plugin installs as IntervalPusher
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `IntervalPusher`, pointing to `xincord.plugins.interval_pusher`, with no dependencies and
no intents. It SHALL bundle a default `config.yaml` that lists no listeners, which its first load
writes to `plugins/IntervalPusher/`, and no lang files.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `IntervalPusher` enabled
- **THEN** it returns `IntervalPusher` from `xincord.plugins.interval_pusher` with no dependencies
  and no intents

#### Scenario: First load creates the config
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/IntervalPusher/config.yaml` holds the bundled default, which lists no
  listeners, and no `lang` directory is written

### Requirement: The config lists the URLs to push
`config.yaml` SHALL have a required `listeners` list whose entries have a `url`, an http or https
URL with a host once `%ping%` is a number, and an `interval` in whole seconds from 1 to 2147483647.
A v3 config file SHALL load unchanged, with a warning that names its `enabled` key. An invalid file
SHALL disable only this plugin, with an error that names the key.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's, with `enabled: true` and one listener whose URL ends in
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
`%ping%` with it, or with `-1` and a warning when the request fails. A URL without `%ping%` SHALL be
pushed as written, without the request.

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

### Requirement: Each push is one GET request
Each push SHALL be one GET request to the URL that follows no redirect, limited to 10 seconds to
connect and 30 seconds in all, as in v3; only the response's status code SHALL be used.

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
A 2xx status SHALL be logged at debug level. A 404, Uptime Kuma's answer for an unknown or paused
push token, SHALL stop that listener with a warning until the plugin reloads or the bot restarts. A
521, Cloudflare's answer when the monitor is offline, SHALL log a warning; any other status, a
network error or a timeout SHALL log an error that names the URL. Except after a 404, the listener
SHALL keep pushing.

#### Scenario: Success
- **WHEN** the monitor answers a push with 200
- **THEN** nothing is logged above debug level, and the listener keeps pushing

#### Scenario: Not found
- **WHEN** the monitor answers a push with 404
- **THEN** a warning says that the listener stops, and it pushes no more

#### Scenario: Monitor offline
- **WHEN** the monitor answers a push with 521
- **THEN** a warning says that the monitor is offline, and the listener keeps pushing

#### Scenario: Other status
- **WHEN** the monitor answers a push with 500 or 302
- **THEN** an error names the URL and the status, and the listener keeps pushing

#### Scenario: Network error
- **WHEN** a push cannot connect or times out
- **THEN** an error names the URL, and the listener keeps pushing

#### Scenario: Unexpected error
- **WHEN** a push fails in another way
- **THEN** the error is logged with its traceback, and the listener keeps pushing

### Requirement: Each listener pushes at once, then after a fixed delay
Each listener's loop SHALL push as soon as it starts, then wait `interval` seconds after each
attempt, however long the attempt took, so that the period is the interval plus the request time,
as in v3. Listeners SHALL be independent: one that waits for a monitor or stops after a 404 SHALL
not delay or stop the others.

#### Scenario: First push at once
- **WHEN** a listener's loop starts
- **THEN** it pushes before it waits

#### Scenario: Fixed delay
- **WHEN** each push of a listener whose interval is 60 seconds takes 30 seconds
- **THEN** its pushes start at 0, 90 and 180 seconds

#### Scenario: Independent listeners
- **WHEN** one listener's monitor does not answer and another's answers 404
- **THEN** a third listener still pushes, and only the second one's loop ends

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
- **WHEN** the plugin loads while the bot is ready, as after `/xincord reload IntervalPusher`
- **THEN** each listener pushes at once

#### Scenario: Unloaded during a push
- **WHEN** the plugin unloads while a push or a ping waits for an answer
- **THEN** the loops end, and the plugin logs no warning or error

#### Scenario: Reload
- **WHEN** the plugin unloads and loads again with a changed config
- **THEN** the old listeners' loops have ended, and the new listeners push at once
