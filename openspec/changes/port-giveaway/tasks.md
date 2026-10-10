## 1. Resources

- [x] 1.1 Bundle v3's en-US and zh-TW lang files with the new `text.yaml` (v3's texts from the
      Kotlin code), and `config.yaml` with v3's keys and `timeZone`

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as Giveaway"
- [x] 2.2 Add the package, its `setup` and the `Giveaway` entry point; remove the markers

## 3. Config

- [x] 3.1 xfail tests for "The config keeps v3's keys"
- [x] 3.2 Implement `Config` (aliases, locale and zone checks, the clamped period); remove the
      markers

## 4. Language

- [x] 4.1 xfail tests for "Each message uses one language" against a stub `texts.language`
- [x] 4.2 Implement `language` and `Texts`; remove the markers

## 5. End times

- [x] 5.1 xfail tests for "End times are read and shown in the configured zone" against stubs in
      `times.py`
- [x] 5.2 Implement `parse_end_time` and `format_end_time`; remove the markers

## 6. Inputs

- [x] 6.1 xfail tests for "Builder inputs are checked as in v3" against stubs in `inputs.py`
- [x] 6.2 Implement `trim`, `winner_count`, `is_http_url`, `thumbnail` and `clip`; remove the
      markers

## 7. Winners

- [x] 7.1 xfail tests for "Winners are drawn per prize" against a stub `model.draw_winners`
- [x] 7.2 Implement `draw_winners` and the cog's `SystemRandom`; remove the markers

## 8. Stored giveaways

- [x] 8.1 xfail tests for "Giveaways are stored as v3's documents" against stubs in `model.py`
      and `store.py`
- [x] 8.2 Implement `parse_instance`, `instance_json` and `Giveaways`; remove the markers

## 9. Preview

- [x] 9.1 xfail tests for "The preview shows the draft" against a stub `texts.preview`
- [x] 9.2 Implement `preview`; remove the markers

## 10. Command

- [x] 10.1 xfail tests for "The command opens the builder" and "The command is a localized
      administrator guild command"
- [x] 10.2 Build and register the command and its callback; remove the markers

## 11. Drafts

- [x] 11.1 xfail tests for "Only the latest builder of a draft works" against stubs `press` and
      `submit`, with `handle` dispatching to them
- [x] 11.2 Look the draft up by user, guild and builder message, answer the session-expired text,
      dispatch the sub-actions; remove the markers

## 12. Modals

- [x] 12.1 xfail tests for "Builder buttons open pre-filled modals" against a stub `_open_modal`
- [x] 12.2 Implement `_open_modal`; remove the markers

## 13. Submissions

- [x] 13.1 xfail tests for "Submitted modals change the draft" against stubs `drafts.submit` and
      `_apply`
- [x] 13.2 Implement them; remove the markers

## 14. Prizes and policy

- [x] 14.1 xfail tests for "The builder removes prizes and switches the winner policy" against
      stubs `_remove_prize` and `_switch_policy`
- [x] 14.2 Implement them; remove the markers

## 15. Post

- [x] 15.1 xfail tests for "The post shows the giveaway" against stubs `texts.post_embed` and
      `texts.post_buttons`
- [x] 15.2 Implement them; remove the markers

## 16. Confirmation checks

- [x] 16.1 xfail tests for "Confirming checks the draft and the administrator" against a stub
      `_confirm`
- [x] 16.2 Implement `drafts.problem` and the checks; remove the markers

## 17. Posting

- [x] 17.1 xfail tests for "Confirming posts the giveaway" and "A giveaway that cannot be posted
      keeps the builder" against a stub `_post`
- [x] 17.2 Implement `_post`; remove the markers

## 18. Cancel

- [x] 18.1 xfail tests for "Cancelling ends the draft" against a stub `_cancel`
- [x] 18.2 Implement `_cancel`; remove the markers

## 19. Joins

- [x] 19.1 xfail tests for "Members join and leave" against a stub `join`
- [x] 19.2 Implement `model.join` and the handler; remove the markers

## 20. Draws

- [x] 20.1 xfail tests for "The creator or an administrator draws and administrators reroll"
      against a stub `draw`
- [x] 20.2 Implement `model.draw`, the handler and the result; remove the markers

## 21. Automatic draw

- [x] 21.1 xfail tests for "Due giveaways are drawn automatically" against a stub `draw_due`
- [x] 21.2 Implement the loop, `draw_due` and the posts; remove the markers

## 22. Routes

- [x] 22.1 xfail tests for "v3's posts keep working" through `bot.on_interaction`
- [ ] 22.2 Route `IDS` to `handle` in `setup`; remove the markers

## 23. Left guilds

- [ ] 23.1 xfail tests for "Leaving a guild drops its drafts" against a stub listener
- [ ] 23.2 Implement `on_guild_remove`; remove the markers

## 24. Conventions and docs

- [ ] 24.1 Check that the built wheel ships `config.yaml` and `lang/` and that `xincord
      --no-online` loads the plugin; drive it once through discord.py's own objects
- [ ] 24.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 24.3 Audit the inventory against the scenarios and the design

## 25. Review

- [ ] 25.1 Gate passes, push, CI green (before the review)
- [ ] 25.2 Cross-review the change (other paths into the features, repeated or concurrent
      presses, state left behind); fix each finding xfail-first

## 26. Close

- [ ] 26.1 Gate passes, push, CI green
- [ ] 26.2 Archive the change and run `openspec validate --all --strict`
- [ ] 26.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
