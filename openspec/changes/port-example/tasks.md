## 1. Resources

- [x] 1.1 Bundle `config.yaml` and the en-US and zh-TW lang files: v3's `register.yaml` and
      `message/example.yaml` with the config field, and the new `message/counter.yaml`

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as _Example", with the shared `store` fixture and
      `load_plugin` helper
- [x] 2.2 Add the package, its `setup` and the `_Example` entry point; remove the markers

## 3. Config

- [x] 3.1 xfail tests for "The config holds an example key"
- [x] 3.2 Add `example_key` to the config model; remove the markers

## 4. Reply

- [x] 4.1 xfail tests for "The reply echoes the options", with the Discord fakes and the golden
      data
- [x] 4.2 Implement the reply; remove the markers

## 5. Command

- [x] 5.1 xfail tests for "The command is a localized guild command"
- [x] 5.2 Build the command from the lang files and register it in `setup`; remove the markers

## 6. Counter

- [ ] 6.1 xfail tests for "The counter button counts presses"
- [ ] 6.2 Implement the handler and route the IDs in `setup`; remove the markers

## 7. Conventions

- [ ] 7.1 Check that the built wheel ships `config.yaml` and `lang/`
- [ ] 7.2 Write the plugin conventions into the port-plugin skill and `docs/porting-guide.md`,
      with the differences rows and the pitfalls
- [ ] 7.3 Audit the inventory against the scenarios and the design

## 8. Close

- [ ] 8.1 Gate passes, push, CI green
- [ ] 8.2 Archive the change and run `openspec validate --all --strict`
- [ ] 8.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
