## 1. Resources

- [x] 1.1 Bundle v3's en-US and zh-TW lang files with final newlines and the en-US `unbind-fail`
      correction

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as DynamicVoiceChannel"
- [x] 2.2 Add the package, its `setup` and the `DynamicVoiceChannel` entry point; remove the markers

## 3. Bindings

- [x] 3.1 xfail tests for "Bindings are kept per guild in v3's documents" against stubs in
      `store.py`
- [x] 3.2 Implement `read_bindings`, `find`, `bind`, `unbind` and `drop`; remove the markers

## 4. Rooms

- [x] 4.1 xfail tests for "Rooms are tracked per guild" against stubs in `store.py`
- [x] 4.2 Implement `read_rooms`, `track` and `untrack`; remove the markers

## 5. Room names

- [x] 5.1 xfail tests for "Room names follow format 1" against stubs in `names.py`
- [x] 5.2 Implement `custom_name` and `room_name`; remove the markers

## 6. Bind and unbind

- [ ] 6.1 xfail tests for "Administrators bind lobbies" and "Administrators unbind lobbies" against
      stub callbacks
- [ ] 6.2 Implement `bind_lobby` and `unbind_lobby`; remove the markers

## 7. Command

- [ ] 7.1 xfail tests for "The command is a localized administrator guild command"
- [ ] 7.2 Build the group and its subcommands and register it in `setup`; remove the markers

## 8. Room creation

- [ ] 8.1 xfail tests for "Joining an empty lobby creates a room" and "Failures leave a lobby"
      against a stub listener
- [ ] 8.2 Implement the voice listener's creation path; remove the markers

## 9. Room deletion

- [ ] 9.1 xfail tests for "Empty rooms are deleted" against a stub deletion path
- [ ] 9.2 Implement the deletion path and the guild's voice lock; remove the markers

## 10. Left guilds

- [ ] 10.1 xfail tests for "Data is forgotten with the guild" against stubs
- [ ] 10.2 Implement `forget`, `guild_ids`, `on_guild_remove`, `on_ready`, `cog_load` and the
      left-guild check; remove the markers

## 11. Checks at READY

- [ ] 11.1 xfail tests for "Bindings and rooms are checked when the bot is ready" against stubs
- [ ] 11.2 Implement the binding and room checks; remove the markers

## 12. Conventions and docs

- [ ] 12.1 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the
      plugin; drive it once through discord.py's own objects
- [ ] 12.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 12.3 Audit the inventory against the scenarios and the design

## 13. Close

- [ ] 13.1 Gate passes, push, CI green
- [ ] 13.2 Archive the change and run `openspec validate --all --strict`
- [ ] 13.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
