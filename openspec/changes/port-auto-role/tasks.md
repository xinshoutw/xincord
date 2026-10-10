## 1. Resources

- [ ] 1.1 Bundle `config.yaml` with no guilds and a commented example with placeholder IDs (v3's
      file held real IDs)

## 2. Installation

- [ ] 2.1 xfail tests for "The plugin installs as AutoRole", with the test fixtures and the
      `config` argument of `plugin_fakes.load_plugin`
- [ ] 2.2 Add the package, its `setup`, the members intent and the `AutoRole` entry point; remove
      the markers

## 3. Config

- [ ] 3.1 xfail tests for "The config lists guilds and their roles"
- [ ] 3.2 Add the config model and the guild-to-roles map; remove the markers

## 4. Join

- [ ] 4.1 xfail tests for "Members who join get the guild's roles", with the guild, role and
      member fakes and `plugin_fakes.dispatch`
- [ ] 4.2 Implement the join listener; remove the markers

## 5. Skipped roles

- [ ] 5.1 xfail tests for "Roles that cannot be given are skipped", with the problems routed to a
      stub
- [ ] 5.2 Log the skipped roles, the missing permission and the failed requests; remove the
      markers

## 6. Ready check

- [ ] 6.1 xfail tests for "Problems are logged when the bot is ready"
- [ ] 6.2 Implement the check on ready and on a load into a ready bot; remove the markers

## 7. Conventions and docs

- [ ] 7.1 Check that the built wheel ships `config.yaml` and that `xincord --no-online` loads the
      plugin
- [ ] 7.2 Porting guide rows and pitfalls, and skill corrections (listeners, intents, plugins
      without lang files, the new test helpers)
- [ ] 7.3 Audit the inventory against the scenarios and the design

## 8. Close

- [ ] 8.1 Gate passes, push, CI green
- [ ] 8.2 Archive the change and run `openspec validate --all --strict`
- [ ] 8.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
