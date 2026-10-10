## 1. Core placeholders

- [x] 1.1 xfail tests for "Global values follow v3" against a stub `global_values`
- [x] 1.2 Implement `global_values`; remove the markers
- [x] 1.3 BotInfo and SimpleCommand call `global_values` instead of their `_bot_values`

## 2. Resources

- [x] 2.1 Bundle v3's en-US and zh-TW lang files with LF line endings, and `config.yaml` without
      real IDs or the Google Sheets keys

## 3. Installation

- [x] 3.1 xfail tests for "The plugin installs as Economy"
- [x] 3.2 Add the package, its `setup` and the `Economy` entry point; remove the markers

## 4. Config

- [x] 4.1 xfail tests for "The config lists the administrators"
- [x] 4.2 Add `admin_id` and `board_user_show_limit` with v3's checks; remove the markers

## 5. Wallets

- [ ] 5.1 xfail tests for "Changes follow v3's arithmetic" and "Boards rank the wallets" against
      stubs in `wallet.py`
- [ ] 5.2 Implement `OPERATIONS` and `rank`; remove the markers

## 6. Storage

- [ ] 6.1 xfail tests for "Wallets are kept per guild in v3's documents" and "Changes are atomic"
      against stubs in `store.py`
- [ ] 6.2 Implement `read`, `read_all` and `change`; remove the markers

## 7. Balance

- [ ] 7.1 xfail tests for "The balance shows a wallet" against a stub `show_balance`
- [ ] 7.2 Implement `show_balance`; remove the markers

## 8. Changes

- [ ] 8.1 xfail tests for "Administrators change wallets", "Only administrators change wallets and
      see boards" and "Negative amounts are refused", against a stub `change_wallet` (and
      `show_board` for the boards' permission)
- [ ] 8.2 Implement `change_wallet`; remove the markers

## 9. Boards

- [ ] 9.1 xfail tests for "Administrators see the boards" and "Board templates are checked at
      load", against a stub `show_board` and a stub check
- [ ] 9.2 Implement `show_board` and `check_boards`; remove the markers

## 10. Buttons

- [ ] 10.1 xfail tests for "Economy buttons show the presser's wallet" against a stub `handle`
- [ ] 10.2 Implement `handle`; remove the markers

## 11. Commands

- [ ] 11.1 xfail tests for "The commands are localized guild commands"
- [ ] 11.2 Build the nine commands, register them and route `IDS` in `setup`; remove the markers

## 12. Conventions and docs

- [ ] 12.1 Check that the built wheel ships `config.yaml` and `lang/` and that `xincord --no-online`
      loads the plugin; drive it once through discord.py's own objects
- [ ] 12.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 12.3 Audit the inventory against the scenarios and the design

## 13. Close

- [ ] 13.1 Gate passes, push, CI green
- [ ] 13.2 Archive the change and run `openspec validate --all --strict`
- [ ] 13.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
