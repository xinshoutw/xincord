## 1. Export

- [x] 1.1 xfail tests for "Bundled lang files are exported"
- [x] 1.2 Implement `export_lang`; remove the markers

## 2. Loading and validation

- [x] 2.1 xfail tests for "Locales come from Discord locale directories", "Lang files are
      validated at load" and "Key sets are compared with the default locale"
- [x] 2.2 Implement `Lang.load`; remove the markers

## 3. Lookup and translation

- [ ] 3.1 xfail tests for "Texts and templates fall back to the default locale" and "Commands are
      localized from register.yaml without fallback"
- [ ] 3.2 Implement the lookups and `Translator`; remove the markers

## 4. Close

- [ ] 4.1 Update `docs/porting-guide.md`
- [ ] 4.2 Gate passes, push, CI green
- [ ] 4.3 Archive the change and run `openspec validate --all --strict`
