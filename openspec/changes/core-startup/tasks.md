## 1. Test helpers

- [x] 1.1 Move `FakePlugins` and the plugin fixtures into shared test modules

## 2. Command line

- [x] 2.1 xfail tests for "Command line options"
- [x] 2.2 Implement `xincord.core.cli` (`Options`, `parse_args`, `main`) and the `xincord` script;
      remove the markers

## 3. Startup and stop

- [ ] 3.1 xfail tests for "Startup loads the configured plugins", "Offline check" and "Graceful
      stop"
- [ ] 3.2 Implement `run` and `Bot.setup_hook`; remove the markers

## 4. Bot defaults

- [ ] 4.1 xfail tests for "Commands are uploaded when ready" and "Mentions allow users only"
- [ ] 4.2 Implement `on_ready`, `on_guild_join` and the default allowed mentions; remove the
      markers

## 5. Close

- [ ] 5.1 Update `docs/porting-guide.md`, the README and the port-plugin skill
- [ ] 5.2 Gate passes, push, CI green
- [ ] 5.3 Archive the change and run `openspec validate --all --strict`
