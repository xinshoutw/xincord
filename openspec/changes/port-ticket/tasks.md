## 1. Resources

- [x] 1.1 Bundle v3's en-US and zh-TW lang files (LF line endings, B2 and B13 fixed) with the new
      `text.yaml` (v3's texts from the Kotlin code)
- [x] 1.2 Move UptimeHeartbeat's URL redaction into the shared package `xincord.plugins.redaction`

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as Ticket"
- [x] 2.2 Add the package, its `setup` and the `Ticket` entry point; remove the markers

## 3. Texts

- [x] 3.1 xfail tests for "Texts follow the reader" against a stub `Texts.get`
- [x] 3.2 Implement `Texts` and the cog's user and public texts; remove the markers

## 4. Stored panels

- [x] 4.1 xfail tests for "Panels are stored as v3's documents" against stubs in `model.py` and
      `store.py`
- [x] 4.2 Implement `parse_entry`, `entry_json` and `Panels`; remove the markers

## 5. Preview

- [x] 5.1 xfail tests for "The preview shows the draft" against stubs in `views.py`
- [x] 5.2 Implement `preview_embed` and `preview_button`; remove the markers

## 6. Commands

- [x] 6.1 xfail tests for "The commands are localized administrator guild commands" and "The
      create command opens the builder"
- [x] 6.2 Build and register the commands, `defaults` and the create callback; remove the markers

## 7. Adding to a message

- [x] 7.1 xfail tests for "The add command opens the builder for a message" against a stub callback
- [x] 7.2 Implement the add callback and its checks; remove the markers

## 8. Sessions

- [x] 8.1 xfail tests for "Only the latest builder of a draft works" against stubs `press`,
      `choose` and `submit`, with `handle` dispatching to them
- [x] 8.2 Look the session up by user, guild and builder message and answer the session-expired
      text; remove the markers

## 9. Modals

- [x] 9.1 xfail tests for "Builder buttons open pre-filled modals" (and the preview modal of "The
      preview shows the draft") against a stub `_open_modal`
- [x] 9.2 Implement `_open_modal`; remove the markers

## 10. Screens

- [x] 10.1 xfail tests for "Builder buttons switch screens" against a stub `_screen`
- [x] 10.2 Implement `_screen`; remove the markers

## 11. Submissions

- [x] 11.1 xfail tests for "Submitted modals change the draft" against stubs `drafts.submit` and
      `parse_color`
- [x] 11.2 Implement them and `_update`; remove the markers

## 12. Selections

- [x] 12.1 xfail tests for "Selections change the draft" against stubs in `drafts.py`
- [x] 12.2 Implement the selections; remove the markers

## 13. Refused changes

- [x] 13.1 xfail tests for "A change that Discord refuses keeps the draft"
- [x] 13.2 Keep the draft and answer the refused text when the builder's edit fails; remove the
       markers

## 14. Confirming

- [x] 14.1 xfail tests for "Confirming posts a new panel", "Confirming adds a button to the
       message" and "A panel that cannot be posted keeps the builder" against a stub `_confirm`
- [x] 14.2 Implement `_confirm`, `panel_button` and the add path; remove the markers

## 15. Pressing a panel

- [x] 15.1 xfail tests for "Pressing a panel button asks for the reason" against a stub `ask`
- [x] 15.2 Implement `ask`; remove the markers

## 16. Tickets

- [x] 16.1 xfail tests for "Submitting the reason opens a ticket channel" and "Ticket channels get
       v3's permissions and the bot's" against stubs `open_ticket` and `tickets.overwrites`
- [x] 16.2 Implement them, `opener` and `control_row`; remove the markers

## 17. Lock and unlock

- [x] 17.1 xfail tests for "The control row locks and unlocks the ticket" against a stub `lock`
- [x] 17.2 Implement `lock`; remove the markers

## 18. Delete

- [x] 18.1 xfail tests for "Administrators delete the ticket" against a stub `delete`
- [x] 18.2 Implement `delete`; remove the markers

## 19. Save

- [x] 19.1 xfail tests for "Administrators choose where to save the conversation" against stubs
       `save` and `select_target`
- [x] 19.2 Implement them and `save_select`; remove the markers

## 20. Archive

- [x] 20.1 xfail tests for "The archive copies the conversation into a thread" against stubs in
       `archive.py`
- [x] 20.2 Implement the names, the forwarding and the archive; remove the markers
- [x] 20.3 xfail tests for "Threads started in the ticket are flattened"
- [x] 20.4 Implement the flattening; remove the markers
- [x] 20.5 xfail tests for "A failed archive is reported and cleans up"
- [x] 20.6 Implement the failure paths and `readable_error`; remove the markers

## 21. Routes

- [x] 21.1 xfail tests for "v3's panels and tickets keep working" through `bot.on_interaction`
- [x] 21.2 Route `IDS` to `handle` in `setup`; remove the markers

## 22. Left guilds

- [ ] 22.1 xfail tests for "Leaving a guild forgets its panels" against stub listeners
- [ ] 22.2 Implement `on_guild_remove` and the READY check; remove the markers

## 23. Conventions and docs

- [ ] 23.1 Golden tests: v3's texts per locale, v3's IDs, every shipped template renders in each
       locale
- [ ] 23.2 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the plugin;
       drive it once through discord.py's own objects
- [ ] 23.3 Porting guide rows and pitfalls, and skill corrections
- [ ] 23.4 Audit the inventory against the scenarios and the design

## 24. Close

- [ ] 24.1 Gate passes, push, CI green
- [ ] 24.2 Archive the change and run `openspec validate --all --strict`
- [ ] 24.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
