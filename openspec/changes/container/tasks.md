## 1. Image

- [x] 1.1 xfail tests for "Container image"
- [x] 1.2 Add the `Dockerfile` and `.dockerignore`; remove the markers

## 2. Compose

- [x] 2.1 xfail tests for "Compose service"
- [x] 2.2 Add `compose.yaml` and ignore `bot/`; remove the markers

## 3. Close

- [ ] 3.1 Manual check from the design, with the owner's go-ahead to start the Docker engine
- [ ] 3.2 Update the README and `docs/porting-guide.md`
- [ ] 3.3 Gate passes, push, CI green
- [ ] 3.4 Archive the change and run `openspec validate --all --strict`
