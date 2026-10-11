## 1. Time zone

- [x] 1.1 xfail test for "Time zone from .env" (the service's `TZ`, the commented example)
- [x] 1.2 `TZ` in `compose.yaml` and `.env.example`, the README; remove the marker

## 2. Close

- [ ] 2.1 Gate passes, push, CI green
- [ ] 2.2 Set `TZ=Asia/Taipei` in the owner's `.env` and run the manual check (design)
- [ ] 2.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md` (the time zone items)
