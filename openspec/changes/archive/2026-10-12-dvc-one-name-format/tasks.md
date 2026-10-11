## 1. One format

- [x] 1.1 xfail tests for "v3's second format is ignored" (a v3 entry with any `formatName2`,
      written without it, the command's options)
- [x] 1.2 Remove `format_name_2` from the binding, the store, the command and both
      `register.yaml`; update the tests and the golden file; remove the markers

## 2. Close

- [x] 2.1 Gate passes, push, CI green
- [x] 2.2 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
