## 1. Reload

- [x] 1.1 xfail tests for "Reload follows the config", "Reload one plugin with its dependents" and
      "Reloads upload the commands and never overlap"
- [x] 1.2 Implement `Bot.reload` and `CORE_CONFIG`; remove the markers

## 2. Triggers

- [ ] 2.1 xfail tests for "Owner-only reload command" and "SIGHUP reloads"
- [ ] 2.2 Implement `xincord.core.admin.Xincord`, register it in `setup_hook`, and handle SIGHUP;
      remove the markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md` and the README
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
