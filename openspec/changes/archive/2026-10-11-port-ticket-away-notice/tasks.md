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
- [x] 3.2 Implement `watches`, `watch` and the notice task; remove the markers

## 4. Problems

- [x] 4.1 xfail tests for "Problems with notices are reported"
- [x] 4.2 Log the missing owner, the refused lookup and the refused notice, and check at load that
      the notice can be posted; remove the markers

## 5. Unload

- [x] 5.1 xfail tests for "Pending notices end with the plugin"
- [x] 5.2 Cancel the waiting notices in `cog_unload`; remove the markers

## 6. Ready check

- [x] 6.1 xfail tests for "The guild and the owner are checked when the bot is ready" against a
      stub `check`
- [x] 6.2 Implement the check on ready and on a load into a ready bot; remove the markers

## 7. Conventions and docs

- [x] 7.1 Check that the built wheel ships `config.yaml` and `lang/`, that `xincord --no-online`
      loads the plugin with example IDs, and drive it once through discord.py's own objects
- [x] 7.2 Porting guide rows and pitfalls, and skill corrections
- [x] 7.3 Audit the inventory against the scenarios and the design

## 8. Review

- [x] 8.1 Gate passes, push, CI green (before the review)
- [x] 8.2 Cross-review the change (other paths into the notice, repeated or concurrent events,
      state left behind) and fix its findings xfail-first (8.3 to 8.10; design, "Cross-review")
- [x] 8.3 xfail test for "The bot's own thread" (found in the review: Ticket's archive starts a
      thread named after the ticket channel, which got the notice once the channel's name matched)
- [x] 8.4 Skip the threads that the bot starts; remove the marker
- [x] 8.5 xfail test for "Event after the unload" (found in the review: a listener that discord.py
      scheduled before an unload ran after `cog_unload` and started a notice nothing cancelled)
- [x] 8.6 Start no notice once the cog unloaded; remove the marker
- [x] 8.7 xfail tests for templates that Discord refuses (found in the review: eleven embeds and an
      empty message loaded, then failed at every notice)
- [x] 8.8 Refuse them at load; remove the markers
- [x] 8.9 xfail test for a v3 prefix that YAML reads as a number (found in the review: kaml read
      `- 2024` as text, pydantic refused it), with tests for v3's Chinese prefix
- [x] 8.10 Read numbers in `prefix` as text; remove the marker

## 9. Close

- [x] 9.1 Gate passes, push, CI green
- [x] 9.2 Archive the change and run `openspec validate --all --strict`
- [x] 9.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
