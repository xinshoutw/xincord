## 1. Core: command names and translations

- [x] 1.1 xfail tests for "Lang files are validated at load": `is_command_name` against a stub
- [x] 1.2 Make the name check public; remove the markers
- [x] 1.3 xfail tests for "Commands can be localized from a table": `localized` against a stub
- [x] 1.4 Implement `localized` and the translator's table; remove the markers

## 2. Core: guild lists

- [x] 2.1 xfail tests for "Commands are split into guild and global scopes": a guild list
- [x] 2.2 Build each guild's payload without the commands of other guilds; remove the markers

## 3. Core: failed reloads

- [x] 3.1 xfail tests for "Hot reload follows dependencies and intents": broken files keep the
      previous version, and a previous version that fails too is unloaded
- [x] 3.2 Replay the previous version's config and lang in discord.py's fallback and unload a
      plugin whose previous version fails; remove the markers

## 4. Bundled config

- [x] 4.1 Bundle `config.yaml` with v3's five commands (not read yet)

## 5. Commands from the config

- [x] 5.1 xfail tests for "The plugin installs as CustomCommands", "Commands come from the config"
      and "Config changes apply on reload"
- [x] 5.2 Read the config in `setup`, build the commands from its entries and drop the bundled
      `register.yaml`; remove the markers

## 6. Templates and placeholders

- [x] 6.1 xfail tests for "A command posts its message in the channel": the template key and the
      user's placeholders
- [x] 6.2 Implement `template` and `placeholder_values`; remove the markers

## 7. Replies

- [x] 7.1 xfail tests for "A command can answer with a public or an ephemeral reply"
- [x] 7.2 Implement `reply`; remove the markers

## 8. Validation

- [x] 8.1 xfail tests for "The config is validated at load"
- [x] 8.2 Implement the value rules in the models and the checks in `setup`; remove the markers

## 9. Migration

- [x] 9.1 xfail tests for "CustomCommands' v3 switch file is set aside"
- [x] 9.2 Set the switch file aside in `migrate_v3`; remove the markers

## 10. Checks and docs

- [ ] 10.1 The wheel ships `config.yaml` and the templates and no `register.yaml`; `xincord
      --no-online` loads the plugin from a scratch venv; a probe through discord.py's objects
      (translated payload, public and ephemeral replies)
- [ ] 10.2 Image check: `docker compose build` and `docker compose run --rm -T bot --no-online`
- [ ] 10.3 Porting guide rows and conventions, port-plugin skill notes; audit the scenarios and the
      inventory against the tests and `design.md`
- [ ] 10.4 Cross-review (a subagent) and its fixes

## 11. Close

- [ ] 11.1 Gate passes, push, CI green
- [ ] 11.2 Archive the change and run `openspec validate --all --strict`
- [ ] 11.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the port-plugin skill; push; CI
      green
