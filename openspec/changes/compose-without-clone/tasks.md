## 1. Compose without a clone

- [ ] 1.1 xfail tests (the published image and the directory mount, the inline node config, the
      build override, Renovate's managers)
- [ ] 1.2 `compose.yaml`, `compose.build.yaml`, the removed `lavalink/application.yml`, the ignore
      files, `.env.example`, README and Renovate; update the old tests; remove the markers

## 2. Close

- [ ] 2.1 Gate passes, push, CI green; the manual check (design) in an empty directory
- [ ] 2.2 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
