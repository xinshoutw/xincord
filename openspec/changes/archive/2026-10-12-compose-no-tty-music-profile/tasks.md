## 1. Compose

- [x] 1.1 xfail tests (no TTY, the `music` profile, the optional dependency, `.env.example`)
- [x] 1.2 `compose.yaml`, `.env.example`, README and MusicPlayer's config comment; update the old
      tests; remove the markers
- [x] 1.3 Plain log lines off a terminal: xfail test, then the plain formatter in `main`

## 2. Close

- [x] 2.1 Gate passes, push, CI green; production: `COMPOSE_PROFILES=music` in the main bot's
      `.env`, the new `compose.yaml` for both bots, the shop bot's node stopped (the plain log
      lines reach production with the next release)
- [x] 2.2 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
