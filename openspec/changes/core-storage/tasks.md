## 1. Key-value store

- [x] 1.1 xfail tests for "Values are stored by namespace and key", "Only JSON values are
      accepted" and "Awaited writes are durable"
- [ ] 1.2 Implement `Store` open/close/get/put/delete/keys/items/run; remove the markers

## 2. Atomic updates, own tables, corruption, locks

- [ ] 2.1 xfail tests for "Read-modify-write is atomic", "Plugins can use their own tables",
      "Corrupt databases are never reset" and "Keyed locks serialize multi-step flows"
- [ ] 2.2 Implement `update`, `lock` and the open-time check; remove the markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
