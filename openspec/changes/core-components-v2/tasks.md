## 1. Loading

- [x] 1.1 xfail tests for "Components V2 templates are validated when they load"
- [x] 1.2 Implement the V2 schema and mode rules; remove the markers

## 2. Rendering

- [x] 2.1 xfail tests for "V2 messages render into a layout view", "Section accessories are
      inferred" and "V2 interactive components follow v3"
- [x] 2.2 Implement the V2 renderer and files; remove the markers
- [x] 2.3 xfail tests for "V2 model keys insert runtime objects"
- [x] 2.4 Implement V2 models and the embed container; remove the markers

## 3. Close

- [ ] 3.1 Update `docs/porting-guide.md`
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 Archive the change and run `openspec validate --all --strict`
