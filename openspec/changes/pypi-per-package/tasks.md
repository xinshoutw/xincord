## 1. Jobs

- [x] 1.1 xfail tests for "PyPI from 1.0.0" (a job and an environment per package, the plugins
      after the core, the writers)
- [x] 1.2 The `pypi-plugins` job and the per-package downloads; README; remove the markers

## 2. Close

- [ ] 2.1 Gate passes, push, CI green
- [ ] 2.2 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md` (the pending publishers)
