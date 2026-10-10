## 1. Shared listen channels

- [x] 1.1 Move VoiceLogger's `settings.py` and `store.py` into `xincord.plugins.listen_channels`
      (`ListenSettings`, bound to a plugin's namespace); VoiceLogger and its tests follow, green
- [x] 1.2 Move the menu, its components, the posts and the checks at READY into `ListenChannels`;
      VoiceLogger's cog keeps its command, the voice and status code; its tests stay green

## 2. Resources

- [x] 2.1 Bundle v3's en-US and zh-TW lang files with final newlines, and the config file

## 3. Installation

- [x] 3.1 xfail tests for "The plugin installs as ChatLogger"
- [x] 3.2 Add the package, its `setup` and the `ChatLogger` entry point; remove the markers

## 4. Config

- [x] 4.1 xfail tests for "The config keeps v3's key and bounds the stored messages"
- [x] 4.2 Implement `Config`; remove the markers

## 5. Detection

- [x] 5.1 xfail tests for "Listen channels detect message channels" (threads and their parents)
- [x] 5.2 Let the shared `detects` and `targets` take the IDs that contain a channel; remove the
      markers

## 6. Settings menu and components

- [x] 6.1 xfail tests for "The settings menu shows the channel's settings" and "The settings
      components change the settings"
- [x] 6.2 Show the menu and handle its components through `ListenChannels`; route `IDS`; remove the
      markers

## 7. Command

- [x] 7.1 xfail tests for "The command is a localized administrator guild command"
- [x] 7.2 Build the group and its subcommand and register it in `setup`; remove the markers

## 8. Message texts

- [x] 8.1 xfail tests for "A message's text is its content and its rich embeds" and the cut of
      "Logged texts are shown as written and fit an embed field" against stubs in `text.py`
- [x] 8.2 Implement `message_text` and `fit`; remove the markers

## 9. Message log

- [x] 9.1 xfail tests for the stored messages against stubs in `messages.py`
- [x] 9.2 Implement `MessageLog`; remove the markers

## 10. Storing messages

- [x] 10.1 xfail tests for "Guild messages are stored" against a stub listener
- [x] 10.2 Implement `on_message`; remove the markers

## 11. Edits

- [x] 11.1 xfail tests for "Edits of stored messages are logged", "Logs reach every listen channel"
      and "Typed placeholders" against a stub listener
- [x] 11.2 Implement `on_raw_message_edit` and the posts; remove the markers

## 12. Deletions

- [x] 12.1 xfail tests for "Deletions of stored messages are logged" and "Long text" against stub
      listeners
- [x] 12.2 Implement `on_raw_message_delete` and `on_raw_bulk_message_delete`; remove the markers

## 13. Retention

- [x] 13.1 xfail tests for "Stored messages are kept for the retention period"
- [x] 13.2 Implement the retention loop; remove the markers

## 14. Left guilds and checks at READY

- [x] 14.1 xfail tests for "Data is forgotten with the guild" and "Settings are checked when the bot
      is ready"
- [x] 14.2 Implement `on_guild_remove`, `on_ready`, `cog_load` and the checks; remove the markers

## 15. Conventions and docs

- [x] 15.1 Check that the built wheel ships `config.yaml` and `lang/` and that `xincord --no-online`
      loads the plugin; drive it once through discord.py's own objects
- [x] 15.2 Porting guide rows and pitfalls, and skill corrections
- [x] 15.3 Audit the inventory against the scenarios and the design

## 16. Review

- [x] 16.1 Gate passes, push, CI green (before the review)
- [ ] 16.2 Cross-review the change (other paths into the features, repeated events, state left
      behind); fix each finding xfail-first
- [x] 16.3 xfail tests for "Edited at once" and "Deleted at once" (found during the review: the
      cached message that `on_message` gets took an edit parsed before the listener ran, and with
      `log_all` false a deletion reached the store before the insert)
- [x] 16.4 Store messages from the relayed `MESSAGE_CREATE` payload and let their edits and
      deletions wait for the insert; remove the markers
- [x] 16.5 xfail test for "Failed load" (found during the review: `cog_load` started the retention
      loop before the checks, so a failing check left it running for a plugin that never loaded)
- [x] 16.6 Check the guilds before the loop starts; remove the marker
- [x] 16.7 xfail test for "Archived threads" (found in the review: the READY check dropped every
      listed thread that discord.py had not cached, archived ones included, which unblocked a
      blocked thread or stopped an allowed one)
- [x] 16.8 Ask Discord about the uncached IDs and drop only those it does not have; remove the
      marker
- [x] 16.9 xfail test for the bulk deletion of "Logs reach every listen channel" (found in the
      review: a purge tried a gone or refusing listen channel once per message)
- [x] 16.10 Skip the listen channels that are gone or refuse for the rest of a bulk deletion;
      remove the marker
- [x] 16.11 xfail test for "Rich preview of a member's link" (found in the review: previews that
      Discord types `rich`, as some sites' are, changed a member's text and were logged as edits)
- [x] 16.12 Leave a member's embeds out of the text; remove the marker

## 17. Close

- [ ] 17.1 Gate passes, push, CI green
- [ ] 17.2 Archive the change and run `openspec validate --all --strict`
- [ ] 17.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
