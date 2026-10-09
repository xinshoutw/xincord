## 1. Routing

- [ ] 1.1 xfail tests for "Component and modal interactions reach their plugin" and "Routes follow
      the plugin's lifecycle"
- [ ] 1.2 Implement `Bot.route` and `Bot.on_interaction`; remove the markers

## 2. Upgrade

- [ ] 2.1 xfail tests for "Legacy IDs are upgraded after use"
- [ ] 2.2 Implement the upgrade after legacy interactions; remove the markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
