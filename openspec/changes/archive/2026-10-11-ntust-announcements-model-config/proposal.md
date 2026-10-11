## Why

On 2026-10-11 the owner asked that every setting of the model that converts NtustAnnouncements'
articles live in the plugin's `config.yaml`, so that it can be changed at any time and a reload
picks it up, with v3's values as defaults. The port made only `model` configurable: the API's
address and version (`web.API` plus `/v1beta`), Gemini's request format, the temperature
(`web.TEMPERATURE`), the request timeout (`web.GEMINI_TIMEOUT`), each key's rate limit
(`gemini.WINDOW`, `gemini.PER_WINDOW`) and the retries (`gemini.MAX_ATTEMPTS`, `gemini.BACKOFF`)
are constants, as they were in v3. The owner also wants a changed endpoint to reach other APIs:
OpenAI, OpenRouter, Ollama, a proxy, or Gemini's own OpenAI-compatible endpoint.

## What Changes

- New keys in `config.yaml`, all optional with v3's values as defaults, so that v3's file and an
  operator's current file load unchanged: `api-format` (`gemini`, today's request, or `openai`, an
  OpenAI-compatible `POST <endpoint>/chat/completions` with the key as a bearer token), `endpoint`
  (`https://generativelanguage.googleapis.com/v1beta`), `temperature` (0.1, or null to send none),
  `max-output-tokens` (null: none sent), `request-timeout` (300 s) and `connect-timeout` (30 s),
  `rate-limit` (10 attempts per key) and `rate-window` (60 s), `max-attempts` (10) and
  `retry-waits` (60, 300, 900, 1800 s). `model` stays, and an `openai` model may hold `/` and `:`.
- Every value is checked at load, an invalid one disabling the plugin with its key named:
  http or https endpoints with a host and no user info, query or fragment, positive numbers within
  sane ranges, a connect timeout no longer than the request timeout. Validation errors never show
  the endpoint or a key.
- Log lines name no product: Gemini's attempts become conversion attempts, with neutral texts for
  both formats, and the module that logs them is renamed from `gemini` to `conversion` (its logger
  name shows in every line). The endpoint appears only as its origin: a new info line at READY
  names the format, the model and the endpoint's origin, and error texts have their URLs cut to
  origins and the endpoint's path removed (`xincord.plugins.redaction`). Keys stay hidden as
  before. v3's example key is refused with a neutral message.
- The bundled `config.yaml` lists every new key with its default and a comment; its comments no
  longer describe Gemini as the only API.

Kotlin sources (v3's hard-coded values that become config):
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:34-36`
  (model, requests per minute, rate-limit window)
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:131-150`
  (the request and its temperature)
- `XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:155-218`
  (attempts and waits)

Out of scope: other request formats (OpenAI's Responses API, Anthropic's Messages API, Azure
OpenAI's deployments with an `api-version` query and an `api-key` header); more generation settings
(top-p, stop sequences, reasoning effort, system prompts); keys per endpoint or several endpoints at
once; streaming; settings for the NTUST pages (the five fetches at a time, their 30-second timeouts)
and the message split, which are not model settings; migrating operators' files (the new keys are
optional).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-ntust-announcements`: the model settings are config (new), an OpenAI-compatible format
  (new); Gemini's request, the keys' rate limit and retries, the config and the logs take the
  settings (modified; two requirements renamed from "Gemini keys" to "API keys").

## Impact

`packages/xincord-plugins/src/xincord/plugins/ntust_announcements/`: `config.py` and the bundled
`config.yaml`, a new `api.py` (the formats' requests and answers), `gemini.py` renamed
`conversion.py` (limits, retries, neutral lines, URL redaction), `web.py` (requests from the
settings), `cog.py` (settings passed to the boards, the info line at READY) and one line of
`watch.py`; their tests. No core change and no new dependency. Operators see new config keys and
reworded log lines (listed in `design.md`); with `api-format: openai`, the boards' articles go to
the configured API with the operator's keys.
