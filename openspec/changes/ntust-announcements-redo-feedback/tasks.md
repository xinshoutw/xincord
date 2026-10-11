## 1. The sign

- [ ] 1.1 xfail tests for "A redo shows that it runs" (the sign before the article is fetched, its
      removal when the old post stays or the redo raises, a refused reaction)
- [ ] 1.2 `Watcher.redo` returns whether it replaced the post; `_redo` adds and removes ⏳; remove
      the markers

## 2. Close

- [ ] 2.1 Gate passes, push, CI green
- [ ] 2.2 The manual check on the test guild (design)
- [ ] 2.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md`
