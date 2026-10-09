## 1. Discovery

- [x] 1.1 xfail tests for "Plugins are discovered through entry points", "Plugins load in
      dependency order" and "Intents are aggregated before connecting"
- [x] 1.2 Implement `discover` and `required_intents`; remove the markers

## 2. Loading

- [x] 2.1 xfail tests for "A failing plugin disables only itself" and "Plugin files live under
      plugins/<Name>/"
- [x] 2.2 Implement `Bot.load_plugins` and `PluginContext`; remove the markers

## 3. Hot reload

- [x] 3.1 xfail tests for "Hot reload follows dependencies and intents"
- [x] 3.2 Implement `Bot.reload_plugin` and `Bot.load_plugin`; remove the markers

## 4. Core config

- [x] 4.1 xfail tests for "The core config lists the enabled plugins" and "v3 plugin switches
      migrate to the enabled list"
- [x] 4.2 Implement the `plugins` key and its migration; remove the markers

## 5. Close

- [x] 5.1 Update `docs/porting-guide.md`
- [x] 5.2 Gate passes, push, CI green
- [x] 5.3 Archive the change and run `openspec validate --all --strict`
