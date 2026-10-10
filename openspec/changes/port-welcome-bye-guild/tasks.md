## 1. Core placeholders

- [x] 1.1 xfail tests for "Event values follow v3's Placeholder.get(event)" against a stub
      `placeholder_values` in `xincord.core.placeholders`
- [x] 1.2 Move `placeholder_values` from _Example into the core, make _Example import it; remove
      the markers
- [x] 1.3 xfail test for "Interaction language and channel follow v3" in a thread whose parent
      channel is not cached (found while checking the commands in threads)
- [ ] 1.4 Give no category for such a thread instead of raising; remove the marker

## 2. Resources

- [x] 2.1 Bundle v3's en-US and zh-TW lang files, with final newlines and the two zh-TW typos
      corrected

## 3. Installation

- [x] 3.1 xfail tests for "The plugin installs as WelcomeByeGuild"
- [x] 3.2 Add the package, its `setup` and the `WelcomeByeGuild` entry point; remove the markers

## 4. Storage

- [x] 4.1 xfail tests for "Each guild's channels are stored" against stubs in `store.py`
- [x] 4.2 Implement `read`, `set_channel`, `forget` and `guild_ids`; remove the markers

## 5. Placeholders

- [x] 5.1 xfail tests for "Templates get v3's wbg@ placeholders" against stubs in `values.py`
- [x] 5.2 Implement `command_values`, `member_event_values` and the channel checks; remove the
      markers

## 6. Command handlers

- [x] 6.1 xfail tests for "Administrators bind a channel", "Administrators unbind a channel", "Only
      administrators change the channels" and "Replies use the guild's locale", against stubs
- [x] 6.2 Implement `bind_channel`, `unbind_channel`, the access check and `_reply`; remove the
      markers

## 7. Joins and removals

- [x] 7.1 xfail tests for "Members who join are welcomed" and "Members who leave are seen off",
      against stub listeners
- [x] 7.2 Implement `on_member_join` and `on_raw_member_remove`; remove the markers

## 8. Forgetting guilds

- [x] 8.1 xfail tests for "Channels are forgotten with the guild"
- [x] 8.2 Implement `on_guild_remove`, `on_ready`, `cog_load` and `forget_left_guilds`; remove the
      markers

## 9. Commands

- [x] 9.1 xfail tests for "The commands are localized administrator guild commands"
- [x] 9.2 Build the four commands with the text-channel option and register them in `setup`;
      remove the markers

## 10. Conventions and docs

- [ ] 10.1 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the plugin
- [ ] 10.2 Porting guide rows and pitfalls, and skill corrections (per-guild data in the store,
      channel options, `placeholder_values` in the core)
- [ ] 10.3 Audit the inventory against the scenarios and the design

## 11. Close

- [ ] 11.1 Gate passes, push, CI green
- [ ] 11.2 Archive the change and run `openspec validate --all --strict`
- [ ] 11.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
