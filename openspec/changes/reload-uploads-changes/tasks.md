## 1. Uploads

- [x] 1.1 xfail tests for "Commands are uploaded when ready" (the first READY forced, a later one
      not) and "Reloads upload the commands and never overlap" (reloads sync without force, also
      after a failed reload that unloaded a plugin)
- [x] 1.2 Force at the first READY only and sync reloads without force; remove the markers

## 2. Missing intents

- [x] 2.1 xfail test for "Hot reload follows dependencies and intents" (one intent, several)
- [x] 2.2 Singular and plural in the error; remove the marker

## 3. Close

- [ ] 3.1 Gate passes, push, CI green
- [ ] 3.2 The manual check on the owner's test guild (design, "Manual check")
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
