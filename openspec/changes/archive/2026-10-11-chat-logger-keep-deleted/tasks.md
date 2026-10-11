## 1. Keeping deleted texts

- [x] 1.1 xfail tests for "Deleted texts can be kept" (kept alone and in bulk, removed by default,
      an invalid value)
- [x] 1.2 The `keep_deleted` key, the bundled file's comment, `keep` on `pop` and `pop_all`;
      remove the markers

## 2. Close

- [x] 2.1 Gate passes, push, CI green
- [x] 2.2 The manual check on the owner's test guild (design)
- [x] 2.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md`
