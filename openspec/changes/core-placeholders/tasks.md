## 1. Rendering

- [x] 1.1 xfail tests for "Placeholders are replaced in a single pass" and "Every render uses only
      its own values"
- [ ] 1.2 Implement `render`; remove the markers

## 2. Value families

- [ ] 2.1 xfail tests for "Acting-user values follow v3", "User and member values follow v3",
      "Guild values follow v3", "Channel and event values follow v3" and "Locale names follow JDA"
- [ ] 2.2 Implement the families, the Protocols and `locales.yaml`; remove the markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
