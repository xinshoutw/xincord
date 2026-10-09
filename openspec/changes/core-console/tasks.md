## 1. Console

- [x] 1.1 Add the `prompt-toolkit` dependency
- [x] 1.2 xfail tests for "Console commands" and "Console completion"
- [ ] 1.3 Implement `xincord.core.console`; remove the markers

## 2. Wiring

- [ ] 2.1 xfail tests for "Console only on a terminal"
- [ ] 2.2 Start the console from `cli` and set up logging inside `patch_stdout`; remove the
      markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md` and the README
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
