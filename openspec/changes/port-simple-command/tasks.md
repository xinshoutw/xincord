## 1. Resources

- [x] 1.1 Bundle v3's zh-TW `register.yaml` and the five message templates, with example account
      numbers under a comment in place of v3's

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as SimpleCommand"
- [x] 2.2 Add the package, its `setup` and the `SimpleCommand` entry point; remove the markers

## 3. Posting

- [x] 3.1 xfail tests for "A command posts its message in the channel", with the golden embeds and
      the posting stubbed
- [x] 3.2 Implement the posting and the fallback to the deferred response; remove the markers

## 4. Commands

- [x] 4.1 xfail tests for "The commands are localized administrator guild commands"
- [x] 4.2 Build the five commands from the lang files with the administrator default permission and
      register them in `setup`; remove the markers

## 5. Conventions and docs

- [x] 5.1 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the plugin
- [x] 5.2 Porting guide rows and pitfalls, and skill corrections (whole messages and their files,
      shared callbacks)
- [x] 5.3 Audit the inventory against the scenarios and the design

## 6. Close

- [ ] 6.1 Gate passes, push, CI green
- [ ] 6.2 Archive the change and run `openspec validate --all --strict`
- [ ] 6.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
