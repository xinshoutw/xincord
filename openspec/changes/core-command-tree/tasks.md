## 1. Defer

- [x] 1.1 xfail tests for "Application commands are deferred ephemerally"
- [x] 1.2 Implement `CommandTree.interaction_check` and use the tree in `Bot`; remove the markers

## 2. Scopes and sync

- [x] 2.1 xfail tests for "Commands are split into guild and global scopes" and "Commands are
      uploaded only when they change"
- [x] 2.2 Implement `CommandTree.payloads`, `sync_global` and `sync_guild`; remove the markers

## 3. Close

- [x] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
