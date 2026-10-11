## RENAMED Requirements

- FROM: `### Requirement: The config names the boards, the Gemini keys and the prompt`
- TO: `### Requirement: The config names the boards, the API keys and the prompt`

- FROM: `### Requirement: Gemini keys stay within the rate limit and failed attempts are retried`
- TO: `### Requirement: API keys stay within the rate limit and failed attempts are retried`

## MODIFIED Requirements

### Requirement: The config names the boards, the API keys and the prompt
`config.yaml` SHALL keep v3's keys: `fetch-interval` (60 to 9223372036854775807 seconds, 3600 by
default), `api-keys` (not empty, no blank key, not v3's example key) and `prompt` (holding
`{{page_url}}`, `{{base_url}}`, `{{now}}` and `{{html}}`); and add `boards` (unique names, http(s)
URLs, a layout, a positive `channel-id`, an optional `title-prefix`) and the model settings.
Errors SHALL never show a key.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's (`enabled`, `fetch-interval`, two keys and v3's prompt) with
  `boards` added
- **THEN** the plugin loads with v3's values and v3's model settings, and logs a warning that names
  `enabled`

#### Scenario: Bundled config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it does not load, the error names `api-keys` and each board's `channel-id`, and the
  file lists v3's 18 boards with their URLs, layouts and the student main office's title prefix

#### Scenario: Invalid values
- **WHEN** `fetch-interval` is 59, a key is blank, the prompt lacks `{{html}}`, a layout is
  unknown, two boards share a name, or a board's URL has no host
- **THEN** the plugin does not load, and the error names the key

#### Scenario: Example key
- **WHEN** `api-keys` holds v3's example key, with either `api-format`
- **THEN** the error names the key's position and asks for an API key without naming Gemini

#### Scenario: Keys stay hidden
- **WHEN** a config with keys fails to load
- **THEN** neither the error nor its chained validation error shows a key

### Requirement: Gemini turns an article into Markdown
With `api-format: gemini`, each attempt SHALL POST the filled prompt to
`<endpoint>/models/<model>:generateContent` with the key in the `x-goog-api-key` header, never in
the URL, `temperature` and `max-output-tokens` in `generationConfig` unless null, within the
timeouts, and take the text of the first candidate's parts, trimmed. An answer that is not 200,
has no text or is blank SHALL be a failed attempt.

#### Scenario: Request
- **WHEN** an attempt runs with v3's settings against a local server standing for Gemini
- **THEN** the server receives a POST to `/v1beta/models/gemini-2.5-flash:generateContent` with
  the key in the header, the prompt as the only text part and temperature 0.1, and no key in the
  URL

#### Scenario: Settings
- **WHEN** the endpoint has a path of its own, the model is another, `temperature` is 0.7 and
  `max-output-tokens` is 2048, or both are null
- **THEN** the request goes under that path for that model with `temperature` 0.7 and
  `maxOutputTokens` 2048, or without a `generationConfig`

#### Scenario: Timeouts
- **WHEN** `request-timeout` is 120 and `connect-timeout` is 10
- **THEN** each attempt is made with those limits

#### Scenario: Answer
- **WHEN** Gemini answers two text parts with whitespace around them
- **THEN** the attempt gives the parts joined and trimmed

#### Scenario: Failed answers
- **WHEN** Gemini answers 429 with an error, 200 without candidates, or blank text
- **THEN** the attempt fails, naming the status and Gemini's message when there is one

### Requirement: API keys stay within the rate limit and failed attempts are retried
Keys SHALL be used in turn, from the one after the last used, each for at most `rate-limit`
attempts started in `rate-window` seconds; when every key is at its limit, the conversion SHALL
wait until the oldest of their attempts is `rate-window` seconds old, without using an attempt. A
conversion SHALL make at most `max-attempts` attempts, waiting the `retry-waits` in turn after the
failed ones, the last wait repeating, and give none after the last.

#### Scenario: Keys in turn
- **WHEN** two keys convert three articles
- **THEN** the attempts use the first key, the second, then the first

#### Scenario: Rate limit
- **WHEN** the only key started 10 attempts in the last 60 seconds, with v3's settings
- **THEN** the next attempt waits until the oldest of them is 60 seconds old

#### Scenario: Configured rate limit
- **WHEN** `rate-limit` is 2, `rate-window` is 30 and the only key started 2 attempts
- **THEN** the next attempt waits until the oldest of them is 30 seconds old

#### Scenario: Retries
- **WHEN** every attempt fails, with v3's settings
- **THEN** the conversion makes 10 attempts, waiting 60, 300, 900, then 1800 seconds, and gives
  none

#### Scenario: Configured retries
- **WHEN** `max-attempts` is 3 and `retry-waits` is `[5, 7, 9]` or `[5]`, and every attempt fails
- **THEN** the conversion makes 3 attempts, waiting 5 then 7 seconds, or 5 twice, and gives none

#### Scenario: Success after failures
- **WHEN** the third attempt works
- **THEN** the conversion gives its text after waiting 60 and 300 seconds

### Requirement: Problems are logged without flooding or showing the keys
Failed board pages, empty pages, failed article pages, failed conversion attempts and refused
posts SHALL be logged once per kind (a status code, an error type) and failure episode, per board
(for attempts, for all boards), the rest at debug level, with one info line once it has worked
three times in a row. Lines SHALL name the board and a key by its position, never its text, show
the endpoint only as its origin and name no product.

#### Scenario: Repeated failure
- **WHEN** a board's page answers 503 at three passes
- **THEN** one warning names the board and the status, and the other two are debug lines

#### Scenario: Recovery
- **WHEN** the page then works at three passes
- **THEN** one info line says that the board's page works again

#### Scenario: Keys hidden
- **WHEN** an attempt fails with an error whose text holds the key
- **THEN** no log line holds the key, and the line names the key's position

#### Scenario: Endpoint hidden
- **WHEN** an attempt fails with an error whose text holds the endpoint's URL, its user info, its
  path or its query
- **THEN** the line shows the endpoint's origin and none of its other parts

#### Scenario: No product named
- **WHEN** attempts fail, give up and work again, or an article cannot be converted
- **THEN** no log line, and no name of the loggers that wrote them, names Gemini

## ADDED Requirements

### Requirement: The model settings are config
`config.yaml` SHALL hold the model settings, with v3's values by default: `api-format` (`gemini`
or `openai`), `endpoint` (an http or https URL with a host and no user info, query or fragment),
`model`, `temperature` (0 to 2, or null), `max-output-tokens`, `request-timeout`,
`connect-timeout`, `rate-limit`, `rate-window`, `max-attempts` and `retry-waits`. An invalid value
SHALL fail the load with its key named, and a reload SHALL apply the file's settings.

#### Scenario: Defaults
- **WHEN** `config.yaml` holds none of the model settings
- **THEN** the plugin uses the gemini format at `https://generativelanguage.googleapis.com/v1beta`
  with `gemini-2.5-flash`, temperature 0.1, no output limit, 300 and 30 seconds, 10 attempts per
  key in 60 seconds, 10 attempts and waits of 60, 300, 900 and 1800 seconds

#### Scenario: Bundled config
- **WHEN** the bundled `config.yaml` is read
- **THEN** it holds every model setting with its default

#### Scenario: Settings from the file
- **WHEN** `config.yaml` sets every model setting, with an endpoint that ends in a slash
- **THEN** the plugin uses them, the endpoint without the slash

#### Scenario: Invalid settings
- **WHEN** a setting is out of its range: an endpoint with another scheme, no host, user info, a
  query or a fragment, a gemini model with a slash, a blank model, a temperature of 2.5, a timeout
  of 0, a connect timeout over the request timeout, no retry wait or a negative one
- **THEN** the plugin does not load, and the error names the key

#### Scenario: Endpoint stays hidden
- **WHEN** an invalid endpoint holds a password, a token in its path or a query
- **THEN** neither the error nor its chained validation error shows them

#### Scenario: Settings reach the boards
- **WHEN** the boards start with settings from the file
- **THEN** the requests and the conversions use them, and an info line names the format, the model
  and the endpoint's origin, and no other part of the endpoint

#### Scenario: Reload
- **WHEN** the settings change in `config.yaml` and the plugin reloads
- **THEN** the new cog's boards use the new settings

### Requirement: An OpenAI-compatible API turns an article into Markdown
With `api-format: openai`, each attempt SHALL POST to `<endpoint>/chat/completions` a body with
`model`, the filled prompt as the only user message, and `temperature` and `max_tokens`
(`max-output-tokens`) unless null, with the key as an `Authorization: Bearer` header, never in the
URL, within the timeouts, and take `choices[0].message.content`, trimmed. An answer that is not
200, has no text or is blank SHALL be a failed attempt.

#### Scenario: Request
- **WHEN** an attempt runs against a local server standing for an OpenAI-compatible API
- **THEN** the server receives a POST to the endpoint's path and `/chat/completions` with the
  bearer key, the model, the prompt as the only user message and temperature 0.1, and no key in
  the URL

#### Scenario: Settings
- **WHEN** `temperature` is null and `max-output-tokens` is 512
- **THEN** the body has no `temperature` and has `max_tokens` 512

#### Scenario: Answer
- **WHEN** the API answers a first choice whose content has whitespace around it, and a second
- **THEN** the attempt gives the first choice's content, trimmed

#### Scenario: Failed answers
- **WHEN** the API answers 401 with an error, 200 without choices or with a null content, or blank
  content
- **THEN** the attempt fails, naming the status and the API's message when there is one
