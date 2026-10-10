## 1. Core gateway relay

- [x] 1.1 xfail tests for "Plugins receive gateway events that discord.py does not parse" against a
      stub `Bot.relay_gateway_event`
- [x] 1.2 Implement `relay_gateway_event`; remove the markers

## 2. Resources

- [x] 2.1 Bundle v3's en-US and zh-TW lang files with final newlines

## 3. Installation

- [x] 3.1 xfail tests for "The plugin installs as VoiceLogger"
- [x] 3.2 Add the package, its `setup` and the `VoiceLogger` entry point; remove the markers

## 4. Settings store

- [x] 4.1 xfail tests for "Settings are kept per guild in v3's documents" against stubs in
      `store.py`
- [x] 4.2 Implement `read_settings`, `read_setting`, `toggle`, `add_channels` and `remove`; remove
      the markers

## 5. Detection

- [x] 5.1 xfail tests for "Listen channels detect voice channels" against stubs in `settings.py`
- [x] 5.2 Implement `detects` and `targets`; remove the markers

## 6. Settings menu

- [x] 6.1 xfail tests for "The settings menu shows the channel's settings" against stubs
      (`list_text`, `show_settings`)
- [x] 6.2 Implement `list_text` and `show_settings`; remove the markers

## 7. Components

- [x] 7.1 xfail tests for "The settings components change the settings" against a stub `handle`
- [x] 7.2 Implement `handle` and route `IDS` in `setup`; remove the markers

## 8. Command

- [x] 8.1 xfail tests for "The command is a localized administrator guild command"
- [x] 8.2 Build the group and its subcommand and register it in `setup`; remove the markers

## 9. Voice changes

- [x] 9.1 xfail tests for "Voice channel changes are logged" and "Logs reach every listen channel"
      against a stub listener
- [x] 9.2 Implement the voice listener and the posts; remove the markers

## 10. Status changes

- [x] 10.1 xfail tests for "Status changes name their member from the audit log" against stubs in
      `status.py` (`match` and `find_actor`, pure)
- [x] 10.2 Implement `match` and `find_actor`; remove the markers
- [x] 10.3 xfail tests for "Voice channel status changes are logged" and the listener's part of
      "Status changes name their member from the audit log" against a stub status listener
- [x] 10.4 Relay the event in `setup`; implement the status tracking, `classify`, the audit log
      requests and the member; remove the markers

## 11. Left guilds

- [x] 11.1 xfail tests for "Settings are forgotten with the guild" against stubs
- [x] 11.2 Implement `forget`, `guild_ids`, `on_guild_remove`, `on_ready`, `cog_load` and the
      left-guild check; remove the markers

## 12. Checks at READY

- [x] 12.1 xfail tests for "Settings are checked when the bot is ready" (no stub: the tests run
      `on_ready`, which the left-guild tests also run)
- [x] 12.2 Implement `prune` and the list check; remove the markers

## 13. Conventions and docs

- [x] 13.1 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the plugin;
      drive it once through discord.py's own objects
- [x] 13.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 13.3 Audit the inventory against the scenarios and the design

## 14. Close

- [ ] 14.1 Gate passes, push, CI green
- [ ] 14.2 Archive the change and run `openspec validate --all --strict`
- [ ] 14.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
