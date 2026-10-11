## 1. CI and Renovate

- [ ] 1.1 xfail tests (the image job, Renovate's first package rule)
- [ ] 1.2 `ci.yml` and `renovate.json`; remove the markers

## 2. Close

- [ ] 2.1 Gate passes, push, CI green with the image job
- [ ] 2.2 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
