## 1. Resources

- [x] 1.1 Bundle `config.yaml` with `source_url`, and v3's en-US and zh-TW lang files with LF line
      endings, final newlines and the source field in `message/bot-info.yaml`

## 2. Installation

- [x] 2.1 xfail tests for "The plugin installs as BotInfo", with the test fixtures
- [ ] 2.2 Add the package, its `setup`, the members intent and the `BotInfo` entry point; remove
      the markers

## 3. Config

- [ ] 3.1 xfail tests for "The config sets the source link", with the field stubbed
- [ ] 3.2 Add `source_url` and its validation to the config model; remove the markers

## 4. Counts

- [ ] 4.1 xfail tests for "The counts sum the bot's guilds", with `member_count` on `FakeGuild`
- [ ] 4.2 Implement the counts; remove the markers

## 5. Reply

- [ ] 5.1 xfail tests for "The reply shows the counts and the source link", with the golden data
- [ ] 5.2 Implement the reply; remove the markers

## 6. Command

- [ ] 6.1 xfail tests for "The command is a localized global command"
- [ ] 6.2 Build the global command from the lang files with v3's contexts and register it in
      `setup`; remove the markers

## 7. Conventions and docs

- [ ] 7.1 Check that the built wheel ships `config.yaml` and `lang/` and that `xincord --no-online`
      loads the plugin
- [ ] 7.2 Porting guide rows and pitfalls, and skill corrections (global commands and their
      contexts, member counts)
- [ ] 7.3 Audit the inventory against the scenarios and the design

## 8. Close

- [ ] 8.1 Gate passes, push, CI green
- [ ] 8.2 Archive the change and run `openspec validate --all --strict`
- [ ] 8.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
