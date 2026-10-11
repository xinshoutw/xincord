## 1. Resources

- [x] 1.1 Bundle `config.yaml` (v3's interval, example keys and prompt copied by a script, `model`,
      v3's 18 boards with 0 for every channel) and add the trimmed NTUST pages and `golden.yaml`
      under `tests/fixtures/plugins/ntust_announcements/`
- [x] 1.2 Move `Failures` from UptimeHeartbeat's `logs.py` into `xincord.plugins.failures`
      (refactor, no behavior change)

## 2. Installation and config

- [x] 2.1 xfail tests for "The plugin installs as NtustAnnouncements" and "The config names the
      boards, the Gemini keys and the prompt", loading the plugin through its entry point
- [x] 2.2 Add the package, its `setup`, the config models and the `NtustAnnouncements` entry
      point; remove the markers

## 3. Pages

- [x] 3.1 xfail tests for "Board pages list their announcements" and "Article pages give their
      content as minified HTML" against stubs in `markup.py` and `pages.py`
- [x] 3.2 Implement the HTML tree, the selectors, the board entries, the links, the container and
      the minifier; remove the markers

## 4. Messages

- [x] 4.1 xfail tests for "Announcements become messages within Discord's limits" against stubs
      in `messages.py`
- [x] 4.2 Implement the content messages, the split and the title links; remove the markers

## 5. Gemini

- [x] 5.1 xfail tests for "The prompt is filled in one pass", "Gemini keys stay within the rate
      limit and failed attempts are retried" and Gemini's lines of "Problems are logged without
      flooding or showing the keys" against stubs in `gemini.py`
- [x] 5.2 Implement `fill_prompt`, `KeyRing`, `backoff` and `Gemini.convert`; remove the markers
- [x] 5.3 xfail tests for "Gemini turns an article into Markdown" against stubs in `web.py`, with a
      local server standing for NTUST and Gemini
- [x] 5.4 Implement `open_web`, the page fetch and the Gemini request; remove the markers

## 6. Passes and storage

- [x] 6.1 xfail tests for "Each board remembers what it posted" against stubs in `store.py`
- [x] 6.2 Implement the documents, `remember` and their loading and saving; remove the markers
- [x] 6.3 xfail tests for "New announcements are posted in board order" and "Problems are logged
      without flooding or showing the keys" against a stub `Watcher.check`
- [x] 6.4 Implement the passes, the announcements, the posts and their logs; remove the markers

## 7. Loops and ready check

- [x] 7.1 xfail tests for "Boards are checked from READY until the plugin unloads"
- [x] 7.2 Run one loop per board from READY in the cog, with the fetch limit, and end them at
      unload; remove the markers
- [x] 7.3 xfail tests for "Channels are checked when the bot is ready" against a stub `check`
- [x] 7.4 Implement the check on ready and on a load into a ready bot; remove the markers

## 8. Conventions and docs

- [x] 8.1 Check that the built wheel ships `config.yaml`, that `xincord --no-online` loads the
      plugin with example values, the image with every ported plugin, and drive the plugin once
      through discord.py's own objects with HTTP recorded
- [x] 8.2 Porting guide rows and pitfalls, and skill corrections
- [x] 8.3 Audit the inventory against the scenarios and the design

## 9. Review

- [x] 9.1 Gate passes, push, CI green (before the review)
- [x] 9.2 Cross-review the change (other paths into a pass, repeated or concurrent passes, state
      left behind) and fix its findings xfail-first (9.3 to 9.19; design, "Cross-review")
- [x] 9.3 xfail test for a channel that refuses posts (found in the review: every pass converted
      the articles again)
- [x] 9.4 Keep an article's messages until they are posted; remove the marker
- [ ] 9.5 xfail test for a message part of only whitespace (found in the review: the rest was lost)
- [ ] 9.6 Drop blank parts; remove the marker
- [ ] 9.7 xfail tests for an announcement that raises and for deeply nested pages (found in the
      review: the board's later entries waited forever)
- [ ] 9.8 Guard each announcement and walk the tree without recursion; remove the markers
- [ ] 9.9 xfail test for a store write that fails after a post (found in the review: posted again)
- [ ] 9.10 Keep the posted links in memory too; remove the marker
- [ ] 9.11 xfail test for a YAML syntax error on a key's line (found in the review: the key was
      logged), with a `core-config` delta
- [ ] 9.12 Give YAML errors the line and column without the text; remove the marker
- [ ] 9.13 xfail tests for self-closing links and classes split at no-break spaces (found in the
      review: jsoup differs)
- [ ] 9.14 Follow jsoup there; remove the markers
- [ ] 9.15 xfail tests for parsing off the event loop and a long run of whitespace (found in the
      review: the loop blocked for seconds)
- [ ] 9.16 Parse in a worker thread and make the minifier's step linear; remove the markers
- [ ] 9.17 xfail test for article URLs on other hosts (found in the review, as in v3)
- [ ] 9.18 Require an NTUST host; remove the marker
- [ ] 9.19 Tests for the scenarios that no test checked (v3's document in a pass, a redirected page
      with relative links, empty pages logged once, a reload)

## 10. Close

- [ ] 10.1 Gate passes, push, CI green
- [ ] 10.2 Archive the change and run `openspec validate --all --strict`
- [ ] 10.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
