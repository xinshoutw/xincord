## 1. Loader

- [x] 1.1 xfail tests for "Config files are validated against a typed schema", "Missing config
      files are created from the default" and "Unknown keys warn instead of failing"
- [x] 1.2 Implement `load_config`, `Model` and `ConfigError`; remove the markers

## 2. Core schema

- [x] 2.1 xfail tests for "Core config schema"
- [x] 2.2 Implement `CoreConfig` and the default `config.yaml`; remove the markers

## 3. Migration

- [ ] 3.1 xfail tests for "v3 core config migrates to the new schema"
- [ ] 3.2 Implement `xincord.core.migrate_v3`; remove the markers

## 4. Close

- [ ] 4.1 Update `docs/porting-guide.md` (differences table)
- [ ] 4.2 Gate passes, push, CI green
- [ ] 4.3 Archive the change and run `openspec validate --all --strict`
