## 1. Resources

- [x] 1.1 Move NtustAnnouncements' `page_context` and TWCA's intermediate certificate into the
      shared package `xincord.plugins.ntust_tls` (refactor, no behavior change)
- [x] 1.2 Bundle `config.yaml` and the lang files (v3's English texts in en-US, zh-TW
      translations), and add the trimmed answer and `golden.yaml` under
      `tests/fixtures/plugins/ntust_course_watch/`

## 2. Installation and config

- [x] 2.1 xfail tests for "The plugin installs as NtustCourseWatch" and "The config names the
      semester, the start and the intervals", loading the plugin through its entry point
- [x] 2.2 Add the package, its `setup`, the config model and the `NtustCourseWatch` entry point;
      remove the markers

## 3. Course query

- [x] 3.1 xfail tests for "Course seats come from NTUST's course query" against stubs in
      `courses.py` and `web.py`, with a local server standing for NTUST
- [x] 3.2 Implement the request body, the answer, v3's limits and the request; remove the
      markers

## 4. Registrations

- [x] 4.1 xfail tests for "Registrations are kept as v3's document" against stubs in `store.py`
- [x] 4.2 Implement the document, its checks and its changes under the lock; remove the markers

## 5. Commands

- [x] 5.1 xfail tests for "Members register courses in a channel", "Members unregister their own
      courses", "Members list their courses in the channel" and "Commands keep v3's names and
      answer in the member's locale"
- [x] 5.2 Build the three commands and their replies; remove the markers

## 6. Alerts

- [x] 6.1 xfail tests for "Channels hear about courses with seats" and "Channels hear once when a
      course fills" against stubs in `alerts.py` and `watch.py`
- [x] 6.2 Implement the throttle, the texts, the split and the step's alerts; remove the markers

## 7. Loop and failures

- [x] 7.1 xfail tests for "Registered courses are checked in turn from READY" and "Failures are
      logged without flooding"
- [x] 7.2 Run the loop from READY in the cog, post through partial messageables, log failures once
      per episode and forget deleted channels; remove the markers

## 8. Conventions and docs

- [ ] 8.1 Check that the built wheel ships `config.yaml`, `lang/` and `ntust_tls`, that
      `xincord --no-online` loads the plugin, the image with every ported plugin and the course
      query's TLS from it, and drive the plugin once through discord.py's own objects with HTTP
      recorded
- [ ] 8.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 8.3 Audit the inventory against the scenarios and the design

## 9. Review

- [ ] 9.1 Gate passes, push, CI green (before the review)
- [ ] 9.2 Cross-review the change (other paths into a step, repeated or concurrent steps and
      commands, state left behind) and fix its findings xfail-first

## 10. Close

- [ ] 10.1 Gate passes, push, CI green
- [ ] 10.2 Archive the change and run `openspec validate --all --strict`
- [ ] 10.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
