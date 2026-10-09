## 1. Codec

- [x] 1.1 xfail tests for "Component IDs use a versioned format" and "Legacy v3 IDs decode
      permanently"
- [x] 1.2 Implement `ComponentIds` build, parse and the legacy decoder; remove the markers

## 2. Lazy upgrade

- [x] 2.1 xfail tests for "Legacy IDs are upgraded lazily"
- [x] 2.2 Implement `ComponentIds.upgrade` and `upgrade_view`; remove the markers

## 3. Close

- [x] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
