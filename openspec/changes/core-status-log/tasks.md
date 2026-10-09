## 1. Status rotation

- [ ] 1.1 xfail tests for "Status rotation"
- [ ] 1.2 Implement `xincord.core.status`, the bot's config and the rotation task; remove the
      markers

## 2. Interaction log

- [ ] 2.1 xfail tests for "Interaction console lines" and "Interaction log channels"
- [ ] 2.2 Implement `xincord.core.interaction_log` and log from `Bot.on_interaction`; remove the
      markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
