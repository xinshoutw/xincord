## 1. Key-value store

- [x] 1.1 xfail tests for "Values are stored by namespace and key", "Only JSON values are
      accepted" and "Awaited writes are durable"
- [x] 1.2 Implement `Store` open/close/get/put/delete/keys/items/run; remove the markers

## 2. Atomic updates, own tables, corruption, locks

- [x] 2.1 xfail tests for "Read-modify-write is atomic", "Plugins can use their own tables",
      "Corrupt databases are never reset" and "Keyed locks serialize multi-step flows"
- [x] 2.2 Implement `update`, `lock` and the open-time check; remove the markers

## 3. Close

- [x] 3.1 Update `docs/porting-guide.md`
- [x] 3.2 Gate passes, push, CI green
- [x] 3.3 Archive the change and run `openspec validate --all --strict`
