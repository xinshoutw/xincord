## 1. Discovery

- [x] 1.1 xfail tests for "Plugins are discovered through entry points", "Plugins load in
      dependency order" and "Intents are aggregated before connecting"
- [ ] 1.2 Implement `discover` and `required_intents`; remove the markers

## 2. Loading

- [ ] 2.1 xfail tests for "A failing plugin disables only itself" and "Plugin files live under
      plugins/<Name>/"
- [ ] 2.2 Implement `Bot.load_plugins` and `PluginContext`; remove the markers

## 3. Hot reload

- [ ] 3.1 xfail tests for "Hot reload follows dependencies and intents"
- [ ] 3.2 Implement `Bot.reload_plugin` and `Bot.load_plugin`; remove the markers

## 4. Core config

- [ ] 4.1 xfail tests for "The core config lists the enabled plugins" and "v3 plugin switches
      migrate to the enabled list"
- [ ] 4.2 Implement the `plugins` key and its migration; remove the markers

## 5. Close

- [ ] 5.1 Update `docs/porting-guide.md`
- [ ] 5.2 Gate passes, push, CI green
- [ ] 5.3 Archive the change and run `openspec validate --all --strict`
