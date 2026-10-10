## 1. Resources

- [x] 1.1 Bundle `config.yaml` (0 for both IDs, v3's prefixes and delay, comments with the intents
      and placeholder IDs) and v3's zh-TW `message/not-online.yaml` with example values and its
      text in the description, written by a script that replaced v3's values

## 2. Installation and config

- [x] 2.1 xfail tests for "The plugin installs as TicketAwayNotice" and "The config names the
      guild, the owner, the prefixes and the delay", loading the plugin through its entry point
- [x] 2.2 Add the package, its `setup`, the members and presences intents, the config model and
      the `TicketAwayNotice` entry point; remove the markers

## 3. Watching and the delay

- [x] 3.1 xfail tests for "New channels whose names start with a prefix are watched" and "The
      notice waits for the delay while the owner is offline" against stubs `Config.watches` and
      `TicketAwayNotice.watch`, with the payload builders, the fake `sleep` and the golden data
- [ ] 3.2 Implement `watches`, `watch` and the notice task; remove the markers

## 4. Problems

- [ ] 4.1 xfail tests for "Problems with notices are reported"
- [ ] 4.2 Log the missing owner, the refused lookup and the refused notice, and check at load that
      the notice can be posted; remove the markers

## 5. Unload

- [ ] 5.1 xfail tests for "Pending notices end with the plugin"
- [ ] 5.2 Cancel the waiting notices in `cog_unload`; remove the markers

## 6. Ready check

- [ ] 6.1 xfail tests for "The guild and the owner are checked when the bot is ready" against a
      stub `check`
- [ ] 6.2 Implement the check on ready and on a load into a ready bot; remove the markers

## 7. Conventions and docs

- [ ] 7.1 Check that the built wheel ships `config.yaml` and `lang/`, that `xincord --no-online`
      loads the plugin with example IDs, and drive it once through discord.py's own objects
- [ ] 7.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 7.3 Audit the inventory against the scenarios and the design

## 8. Review

- [ ] 8.1 Gate passes, push, CI green (before the review)
- [ ] 8.2 Cross-review the change (other paths into the notice, repeated or concurrent events,
      state left behind) and fix its findings xfail-first

## 9. Close

- [ ] 9.1 Gate passes, push, CI green
- [ ] 9.2 Archive the change and run `openspec validate --all --strict`
- [ ] 9.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
