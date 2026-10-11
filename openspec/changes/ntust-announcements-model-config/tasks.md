## 1. Module names

- [x] 1.1 Rename `gemini.py` to `conversion.py`, `Gemini` to `Converter`, `GeminiError` to
      `ApiError` and `test_gemini.py` to `test_conversion.py` (refactor, no other change)

## 2. Requests

- [x] 2.1 xfail tests for "Gemini turns an article into Markdown" (settings, timeouts) and "An
      OpenAI-compatible API turns an article into Markdown", against stubs in a new `api.py`, with
      `open_web` taking an `Api`
- [x] 2.2 Build each format's request from the settings and read its answer; remove the markers

## 3. Conversions

- [x] 3.1 xfail tests for "API keys stay within the rate limit and failed attempts are retried"
      (configured limits) and "Problems are logged without flooding or showing the keys" (the
      endpoint hidden, no product named), against stubs in `conversion.py`
- [x] 3.2 Take the limits, redact the endpoint from error texts and word the lines neutrally; remove
      the markers

## 4. Config

- [x] 4.0 Move Kotlin's `trim` from `pages.py` into `strings.py` (refactor), so that `config.py`
      can import `api.py` and `conversion.py` without a cycle through `pages.py`
- [x] 4.1 xfail tests for "The model settings are config" and "The config names the boards, the API
      keys and the prompt" (the example key), against stub fields and properties in `config.py`
- [x] 4.2 Validate the settings, bundle them in `config.yaml`, pass them to the boards with the
      READY line and word the title-link warning neutrally; remove the markers

## 5. Checks and docs

- [x] 5.1 The wheel ships the new `config.yaml`; `xincord --no-online` from a scratch venv loads the
      plugin with example values and refuses an invalid setting; a scratch probe runs both formats
      through the plugin's web against a local server
- [x] 5.2 Porting guide rows and conventions, port-plugin skill notes
- [x] 5.3 Audit: every scenario of the delta has a test
- [ ] 5.4 Push the work so far (CI green); cross-review (a subagent); record its findings and fix
      them xfail-first

## 6. Close

- [ ] 6.1 Gate passes, push, CI green
- [ ] 6.2 Archive the change and run `openspec validate --all --strict`
- [ ] 6.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
