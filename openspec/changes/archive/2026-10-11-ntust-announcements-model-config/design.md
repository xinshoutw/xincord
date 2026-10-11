## Context

NtustAnnouncements (`xincord.plugins.ntust_announcements`, v3's NtustManager, ported in
`port-ntust-announcements`) has an LLM turn each NTUST article into Discord Markdown. The port kept
v3's Gemini call (`GeminiApiService.kt:34-36`, `131-150`, `155-218`) and made only the model a
config key: `web.Web.generate` POSTs to `API` (`https://generativelanguage.googleapis.com`) plus
`/v1beta/models/<model>:generateContent`, the key in `x-goog-api-key`, temperature 0.1 (`TEMPERATURE`)
within `GEMINI_TIMEOUT` (300 s in all, 30 s to connect); `gemini.KeyRing` allows each key 10
attempts (`PER_WINDOW`) in 60 seconds (`WINDOW`); `gemini.Gemini.convert` makes 10 attempts
(`MAX_ATTEMPTS`) and waits 60, 300, 900, then 1800 seconds after the failed ones (`BACKOFF`).

On 2026-10-11 the owner asked for all of them in `config.yaml`, changeable at any time with a reload
picking them up, v3's values as defaults: the endpoint (with the path and version that the request
uses), an API format, `gemini` (today's request) or `openai` (an OpenAI-compatible
`POST <endpoint>/chat/completions`, the key as `Authorization: Bearer`, the reply in
`choices[0].message.content`), so that a changed endpoint reaches OpenAI, OpenRouter, Ollama, a
proxy or Gemini's own OpenAI-compatible endpoint; the model, the temperature, a maximum output
length if trivial, the timeouts, the rate limit and the retries. Every value is validated at load
with its key named, keys stay redacted, the endpoint is logged only as its origin, and texts that
name Gemini where the format makes them wrong become neutral.

APIs checked on 2026-10-11 (vendor documentation): Gemini's `generateContent` takes
`generationConfig.temperature` and `maxOutputTokens`; Gemini's OpenAI-compatible endpoint is
`https://generativelanguage.googleapis.com/v1beta/openai/` with a bearer key; OpenAI's chat
completions take `temperature` (0 to 2) and the deprecated `max_tokens`, which its o-series
(reasoning) models refuse in favor of `max_completion_tokens`, and its reasoning models refuse a
temperature other than their default; Ollama's `/v1/chat/completions` takes `temperature` and
`max_tokens` but lists no `max_completion_tokens`, and ignores the key; the error answers of
Gemini, OpenAI, OpenRouter and Ollama's compatible endpoint carry `error.message`.

## Goals / Non-Goals

**Goals:** every model setting in `config.yaml` with v3's values as defaults, so v3's file and
current operators' files load unchanged and behave as before; the `openai` format; validation at
load with the key named and nothing secret shown; a reload applies the settings; logs that name no
product and show the endpoint only as its origin.

**Non-Goals:** other formats (OpenAI's Responses API, Anthropic's Messages API, Azure OpenAI's
deployments with an `api-version` query and an `api-key` header); more generation settings
(top-p, stop sequences, reasoning effort, a system prompt); several endpoints or keys per endpoint;
streaming; the NTUST pages' settings (five fetches at a time, 30-second timeouts) and the message
split; a migration of operators' files (the keys are optional).

## Decisions

### Config keys

New top-level keys, kebab-case like v3's `fetch-interval` and `api-keys`, flat like the plugin's
other keys, each optional with v3's value as default, in the bundled file between `api-keys` and
`prompt`:

| Key | Default | Accepted |
|---|---|---|
| `api-format` | `gemini` | `gemini` or `openai` |
| `endpoint` | `https://generativelanguage.googleapis.com/v1beta` | an http or https URL as aiohttp reads it (yarl): a host, a port from 1 to 65535, no spaces, no user info, no query, no fragment; a final `/` is dropped |
| `model` (exists) | `gemini-2.5-flash` | 1 to 256 characters without whitespace; with `gemini`, letters, digits, `.`, `-` and `_` only, since it goes into the URL's path |
| `temperature` | 0.1 | 0 to 2, or null (none sent) |
| `max-output-tokens` | null (none sent) | 1 to 1048576, or null |
| `request-timeout` | 300 | seconds, more than 0, at most 3600 |
| `connect-timeout` | 30 | seconds, more than 0, at most `request-timeout` |
| `rate-limit` | 10 | attempts per key in a window, 1 to 10000 |
| `rate-window` | 60 | seconds, more than 0, at most 86400 |
| `max-attempts` | 10 | 1 to 100 |
| `retry-waits` | `[60, 300, 900, 1800]` | 1 to 100 waits, each 0 to 86400 seconds |

- Floats are finite (`allow_inf_nan=False`: YAML's `.inf` and `.nan` are refused) and the numbers
  are strict, so YAML's `yes`, `on` and `true` are refused where a number goes (a lax number takes
  them as 1; found in the cross-review). The bounds catch units typed wrongly (milliseconds for
  seconds, a day of waits) and are wider than any provider's documented values.
- `Config` declares `api_format` before `model` and `request_timeout` before `connect_timeout`, so
  that the field validators of `model` and `connect_timeout` read the earlier field from pydantic's
  `ValidationInfo.data` and the error names the field itself; a model validator would report
  `<root>`. When the earlier field is invalid, only the field's own rules apply.
- `Config.api` (an `api.Api`) and `Config.limits` (a `conversion.Limits`) gather the settings for
  the web and the conversions. `Api()` and `Limits()` hold v3's values and are the fields' defaults,
  the one source of them.
- Validators give fixed messages and the model hides its input (as before), so neither the
  `ConfigError` nor the chained `ValidationError` shows the endpoint, which can hold a proxy's
  token in its path. v3's example key is refused with `replace the example key with your API key`
  (was `... with a Gemini API key`).
- `temperature: null` exists because OpenAI's reasoning models refuse any temperature but their
  default; `max-output-tokens` is a pass-through (Gemini's `maxOutputTokens`, OpenAI's
  `max_tokens`), null by default because v3 sent none.
- The endpoint includes the API's version path, as the owner asked, and each format appends its
  own path. One default for both formats: switching `api-format` alone keeps Gemini's native
  endpoint, which answers 404 to `chat/completions`; the bundled file's comment lists the
  endpoints of each format. User info is refused: keys belong in `api-keys`, and aiohttp refuses an
  `Authorization` header together with credentials in the URL (the `openai` format). Queries and
  fragments are refused because the format's path is appended.

### Requests (`api.py`, new)

- `ApiFormat` (`gemini`, `openai`) and `Api` (frozen dataclass: `format`, `endpoint`, `model`,
  `temperature`, `max_output_tokens`, `request_timeout`, `connect_timeout`) with `url`,
  `headers(key)` and `body(prompt)`; `answer_text(format, answer)` and `error_message(answer)`.
  Pure, tested without HTTP.
- `gemini`: `POST <endpoint>/models/<model>:generateContent`, `x-goog-api-key: <key>`, body
  `{"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": t,
  "maxOutputTokens": n}}` with each null setting left out and `generationConfig` left out when
  empty; the text is the first candidate's text parts joined and trimmed (unchanged).
- `openai`: `POST <endpoint>/chat/completions`, `Authorization: Bearer <key>`, body `{"model": m,
  "messages": [{"role": "user", "content": prompt}], "temperature": t, "max_tokens": n}` with each
  null setting left out; the text is `choices[0].message.content` when it is a string, trimmed;
  anything else (no choices, a null content of a refusal or a tool call, a list) gives no text, a
  failed attempt. The prompt is the only message, as it was Gemini's only part. `max_tokens`, not
  `max_completion_tokens`: Ollama, OpenRouter and Gemini's compatible endpoint take it; OpenAI's
  reasoning models refuse it, so the comment says to leave it null for them.
- Both formats: a status other than 200 raises `ApiError(status, error.message)` (was
  `GeminiError`), the message taken from the first item when the answer is a list (Gemini's
  OpenAI-compatible endpoint) and `error` itself when it is a text; no redirects;
  `aiohttp.ClientTimeout(total=request-timeout, connect=connect-timeout)`.
- `web.Web` takes the `Api` (`open_web(api)`), so the session, the pages and the TLS context stay
  as they were. `API`, `TEMPERATURE` and `GEMINI_TIMEOUT` go.

### Conversions (`gemini.py` renamed `conversion.py`)

- The module's logger name shows in every line (`discord.utils.setup_logging`'s format), and
  `xincord.plugins.ntust_announcements.gemini` would name Gemini with any format: a `refactor`
  commit renames the module and its test, `Gemini` to `Converter` and `GeminiError` to `ApiError`,
  before the behavior changes.
- `Limits` (frozen dataclass: `rate_limit`, `rate_window`, `max_attempts`, `retry_waits`).
  `KeyRing(keys, limit, window)` and `backoff(failed, waits)` take them; `Converter` takes a
  `Limits` and `urls`, the endpoint and the request URL, whose parts error texts never show.
- `backoff`: the wait after the n-th failed attempt is `retry_waits[min(n, len) - 1]`, v3's rule
  with v3's list. `convert` reads the clock once per pass, for `take` and `wait` alike.
- `config.py` imports `api.py` (the format, the defaults) and `conversion.py` (`Limits`), which
  imported Kotlin's `trim` from `pages.py`, which imports `config.py`'s `Layout`: a second
  `refactor` commit moves `trim` into `strings.py`, a module that imports nothing of the plugin.

### Logs

| Where | Before | After |
|---|---|---|
| failed attempt (warning once per kind and episode, else debug) | `Gemini attempt 3 of 10 at <article> failed with key 1: <error>` | `conversion attempt 3 of 10 at <article> failed with key 1: <error>` |
| blank answer | `Gemini gave no text` | `the model gave no text` |
| episode over (info) | `Gemini works again after 3 failed attempts` | `conversions work again after 3 failed attempts` |
| keys full (debug) | `every Gemini key is at its limit; waiting 12.0 s` | `every key is at its rate limit; waiting 12.0 s` |
| success (debug) | `Gemini converted <article> on attempt 1 with key 2` | `converted <article> on attempt 1 with key 2` |
| given up (error) | `Gemini failed 10 attempts at <article>` | `gave up converting <article> after 10 attempts` |
| title link instead (warning, per board) | `posting <article> as its title, since Gemini could not convert it` | `posting <article> as its title, since the model could not convert it` |
| READY, new (info) | | `converting articles with gemini-2.5-flash at https://generativelanguage.googleapis.com (api-format gemini)` |

Every line starts with `NtustAnnouncements:` (the board's lines with `NtustAnnouncements board
<name>:`); counts of one read `1 failed attempt` and `1 attempt`. The same texts serve both formats,
so `gemini` changes too: one code path, and the endpoint's origin in the READY line names the
provider. An error's text is redacted before it is logged: every http or https URL in it is cut to
its origin and the endpoint's and the request URL's user info, path and query are removed wherever
they appear (`xincord.plugins.redaction.redact`), then every key is replaced with `...` as before.
The API's own message can quote a key masked (OpenAI shows its start and last four characters); only
whole keys are replaced.

### Wiring and reload

`_run` reads `config.api` and `config.limits` after READY, logs the READY line, opens the web with
the `Api` and builds the `Converter` with the `Limits` and the URLs. A reload builds a new cog
from the file (unchanged since the port), so the next board passes use the new settings; an
attempt under way in the old cog ends with it, and its article is converted again at the new cog's
first pass. The new cog's rate limiter starts empty, as the port's did, after a reload that worked
and after one that failed (the previous version is set up again): right after a reload a key can
take up to `rate-limit` attempts more within one window than the setting allows, and an article
in its retries starts its attempts again (review queue).

### Tests (xfail-first)

Each xfail commit routes the new cases to stubs that raise `NotImplementedError` and leaves v3's
paths working, so the existing tests stay green:

- Requests: `api.Api`'s format and settings other than the endpoint and the model, and
  `answer_text` for `openai`, raise; tests run `open_web(Api(...))` against a local server
  (`test_web.py`) and `answer_text` on odd answers.
- Conversions: `KeyRing`, `backoff` and `Converter` raise for limits other than v3's and for
  `urls`; tests drive them on a fake clock (`test_conversion.py`).
- Config: the new fields take a `BeforeValidator` that raises (pydantic passes errors other than
  `ValueError` and `AssertionError` through), and `Config.api` and `Config.limits` raise; tests
  validate through the core's `parse_model`, hand a parsed config to the loaded cog before READY,
  and reload the plugin with a changed file (`test_config.py`, `test_lifecycle.py`).

## v3 behaved differently

- v3 behaved differently: the model, the temperature, the rate limit, the retries and Gemini as the
  only API were hard-coded, and its SDK set no timeout; they are config keys with v3's values as
  defaults, `openai` reaches OpenAI-compatible APIs, and a reload applies them.

## User-visible changes

1. `config.yaml`: new keys `api-format`, `endpoint`, `temperature`, `max-output-tokens`,
   `request-timeout`, `connect-timeout`, `rate-limit`, `rate-window`, `max-attempts` and
   `retry-waits`, with comments; the header, `api-keys`, `model` and `prompt` comments no longer
   say Gemini only. An operator's existing `plugins/NtustAnnouncements/config.yaml` keeps its text
   and gets the defaults, which are v3's.
2. `api-format: openai` sends the articles to the configured OpenAI-compatible API.
3. Config errors: v3's example key reads `replace the example key with your API key`; a gemini
   model outside letters, digits, `.`, `-` and `_` reads `the gemini format takes letters, digits,
   '.', '-' and '_'` (was pydantic's pattern message); new errors for each new key.
4. Log lines as in the table above, the new READY line, error texts with URLs cut to their origins,
   and the logger name `xincord.plugins.ntust_announcements.conversion` (was `...gemini`).

## Risks / Trade-offs

- With `openai`, the articles and the operator's keys go to whatever `endpoint` names; an `http://`
  endpoint on another host sends the key unencrypted. The comment lists the providers' https
  endpoints.
- Switching `api-format` without `endpoint` posts to Gemini's native endpoint, which answers 404: a
  warning per episode, then each article is posted as its title link after `max-attempts`.
- `max-output-tokens` as `max_tokens` fails with OpenAI's reasoning models, and any temperature does
  too: the comment says to leave both null for them.
- A small `rate-window` or `retry-waits` with large `rate-limit` and `max-attempts` can spend a
  daily quota fast; the bounds only catch typos.
- Redacting every URL in an error's text also shortens the links that APIs put in their messages
  (OpenAI's link to its key page shows only `https://platform.openai.com`).
- The renamed logger changes any log filter that an operator set on `...gemini` (none in the
  repository).

## Manual smoke checklist

With a token, a test guild, two boards with test channels and `plugins: [NtustAnnouncements]`:

1. Keep the defaults with a Gemini key: at READY the log says `converting articles with
   gemini-2.5-flash at https://generativelanguage.googleapis.com (api-format gemini)` and the posts
   are as before.
2. Set `api-format: openai` and `endpoint: https://generativelanguage.googleapis.com/v1beta/openai`
   with the same key, delete one board's document, `/xincord reload NtustAnnouncements`: the READY
   line names the new endpoint's origin and the board's articles are posted as Markdown.
3. Point `endpoint` at OpenAI, OpenRouter or Ollama (`http://host.docker.internal:11434/v1` from
   the compose container to Ollama on the Mac, any text as the key) with a model they serve; for an
   OpenAI reasoning model set `temperature: null`. Articles convert.
4. Set a wrong key: one warning per episode names `key 1`, the status and the API's message, and
   `docker compose logs bot | grep <key>` finds nothing; an endpoint with a token in its path never
   shows the path.
5. Set `max-attempts: 2` and `retry-waits: [5]` with a wrong key: an article is posted as its title
   link after one 5-second wait.
6. Set an invalid value (`temperature: 3`): the reload fails with `config.yaml: temperature: ...`
   and the previous settings keep running.

## Checks (2026-10-11)

- Package: the `xincord-plugins` wheel ships `api.py`, `conversion.py`, `strings.py` and the new
  `config.yaml`, and no `gemini.py`. `xincord --no-online` from a scratch venv with both wheels and
  `plugins: [NtustAnnouncements]` exits 1 with the bundled config (both `api-keys` with `replace the
  example key with your API key` and the 18 `channel-id`s, no model setting); 0 with example keys
  and channels and `api-format: openai`, `endpoint: "https://openrouter.ai/api/v1/"`,
  `model: "openai/gpt-4o-mini"`, `temperature: null`; 1 with `temperature: 3` (`temperature: Input
  should be less than or equal to 2`), and 1 with an endpoint holding user info, a token in its
  path and a query, the error naming `endpoint` and no line of the log holding the secrets.
- Probe (a scratch script with the installed wheels, not committed): `open_web` and `Converter`
  against a local aiohttp server. The openai format POSTed `/secret-token/v1/chat/completions`
  with `Bearer <key>`, the model, the prompt as the only user message and `max_tokens` 64 without
  a temperature, and gave the first choice's content trimmed; the gemini format POSTed
  `/secret-token/v1beta/models/gemini-2.5-flash:generateContent` with `x-goog-api-key` and
  temperature 0.1. A server answering a malformed status line gave aiohttp's `400, message="Bad
  status line ...", url='http://127.0.0.1:<port>'` (the path cut), a closed port `Cannot connect to
  host 127.0.0.1:<port> ...`; no line held the path's token or a key, and no line of an openai
  attempt named Gemini.
- Not rebuilt: the image. Only the plugin's modules and bundled config changed, and no
  dependency; the wheel check covers them.

## Cross-review (a subagent, 2026-10-11)

A review of the pushed work (other paths into the settings, retries and repeated work, state left
behind), with scratch probes through the loaded plugin, local servers and the core's reload, found
no high or medium problem and these low ones:

1. Numeric settings took YAML's booleans (`max-output-tokens: yes` asked for one token, and each
   article was posted as that token). Fixed: the numbers are strict (tasks 5.5 and 5.6).
2. `urlsplit` accepted endpoints that aiohttp's yarl refuses (a backslash in the host, so every
   attempt failed, and `origin` then showed the text after the backslash) and port 0. Fixed: the
   endpoint is read with yarl; `redaction.origin` is unchanged, since no endpoint can hold a
   backslash now.
3. `error_message` read only `{"error": {"message": ...}}`; Gemini's OpenAI-compatible endpoint
   answers a list of one error, and some servers an error text. Fixed: both shapes.
4. `Converter.convert` read the clock twice: an attempt leaving the window between the readings
   left `KeyRing.wait` no attempt to wait for (`IndexError`), more likely with `rate-limit: 1` and a
   small window. Fixed: one reading per pass.
5. Any reload, a failed one included, starts the boards again with an empty rate limiter and
   restarts an article's attempts. Kept and recorded (above and in the review queue): keeping the
   limiter's state outside the cog would need state that survives the plugin's modules.
6. A short placeholder key (`o`) is replaced in every error text, which garbles them. The bundled
   comment now suggests a placeholder that no address or message holds; whole keys stay hidden.
7. Docs: the comment's Ollama address was the bot's own container under compose (now
   `host.docker.internal`), the comment did not say that `connect-timeout` is at most
   `request-timeout`, and the failures package's docstring named Gemini. Fixed.

The review also found sound: settings reaching the web and the conversions on a first load, a load
into a ready bot, a reload and a failed reload; `--no-online`; an unload during a request or a
retry wait; the limits with two boards on one converter, `max-attempts: 1`, one wait, more waits
than attempts and zero waits; both formats' requests, null settings left out, temperature 0 kept,
no redirects and the timeouts applied; no line or logger name holding the endpoint's path, a key
or Gemini, through a 401 quoting the key, odd paths, IPv6, a bad status line, a disconnect and a
closed port; the validators reading defaults; and no module-level state.

## Scenario audit

Every scenario of the delta has a test (`tests/plugins/ntust_announcements/`):

- The config names the boards, the API keys and the prompt: v3 config file (`test_config.py`
  `test_v3_config_file`, `test_default_model_settings`), bundled config (`test_bundled_config`),
  invalid values (`test_invalid_values`), example key (`test_example_key`), keys stay hidden
  (`test_keys_stay_hidden`).
- Gemini turns an article into Markdown: request (`test_web.py` `test_request`), settings
  (`test_request_settings`, `test_request_without_settings`), timeouts (`test_timeouts`), answer
  (`test_answer`), failed answers (`test_refused_answers`, `test_answers_without_text`,
  `test_answer_text`).
- API keys stay within the rate limit and failed attempts are retried: keys in turn
  (`test_conversion.py` `test_keys_in_turn`), rate limit (`test_rate_limit`, `test_window`),
  configured rate limit (`test_configured_window`, `test_configured_rate_limit`), retries
  (`test_retries`, `test_backoff`), configured retries (`test_configured_retries`,
  `test_configured_backoff`), success after failures (`test_success_after_failures`).
- Problems are logged without flooding or showing the keys: repeated failure and recovery
  (`test_watch.py`, unchanged), keys hidden (`test_keys_hidden`), endpoint hidden
  (`test_endpoint_hidden`, `test_lifecycle.py` `test_settings_reach_the_boards`), no product named
  (`test_no_product_named`, `test_counts_of_one`, `test_settings_reach_the_boards`).
- The model settings are config: defaults (`test_default_model_settings`), bundled config
  (`test_bundled_model_settings`), settings from the file (`test_model_settings_from_the_file`),
  invalid settings (`test_invalid_model_settings`), endpoint stays hidden
  (`test_endpoint_stays_hidden`), settings reach the boards (`test_settings_reach_the_boards`),
  reload (`test_reload_applies_the_settings`).
- An OpenAI-compatible API turns an article into Markdown: request (`test_openai_request`),
  settings (`test_openai_settings`), answer (`test_openai_answer`), failed answers
  (`test_openai_refused_answers`, `test_openai_answers_without_text`, `test_openai_answer_text`).
