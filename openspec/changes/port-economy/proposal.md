## Why

Decision C1 ports Economy after Feedbacker, and F3 lists it as in use. v3's Economy
(`Plugins/Economy`, 11 Kotlin files, 1182 lines) is a per-guild virtual wallet: every user has a
balance (money) and a cumulative spending (cost); administrators listed in `config.yaml` add,
remove or set either amount, everyone sees their own wallet with `/balance`, and two leaderboards
rank the wallets. It is the first port whose data changes amounts that must stay exact and must
never lose an update.

## What Changes

- New plugin package `xincord.plugins.economy`, registered as `Economy`, with no dependencies, no
  intents, v3's en-US and zh-TW lang files (`register.yaml` and ten messages per locale) and a
  bundled `config.yaml`.
- `config.yaml` keeps v3's `admin_id` (the administrators, at least one, as in v3) and
  `board_user_show_limit` (1 to 25, default 10). The bundled file lists no administrator, so the
  plugin does not load until the operator adds one; v3's files load unchanged, and their `enabled`
  and Google Sheets keys only warn.
- v3's nine guild commands keep their names, descriptions, localizations and options: `balance`
  (optional `member`, visible to everyone), `top-money` and `top-cost`, and `add-money`,
  `remove-money`, `set-money`, `add-cost`, `remove-cost`, `set-cost` (`member` and `value`),
  visible to administrators by default. Every reply edits the ephemeral deferred response with
  v3's templates in the user's locale.
- Wallets are kept per guild in the shared store as v3's JSON document
  (`{"<userId>": {"cost": .., "money": ..}}`) under the namespace `Economy` and the guild's ID, and
  every change is one atomic store update. Amounts are Python integers: exact, never wrapped.
- v3's `economy@` buttons keep working: an Economy button shows the presser's wallet.
- Core (`core-placeholders`): `global_values(client)` gives v3's global placeholders (`bot_id`,
  `bot_name`), which v3 rendered `no-permission` with; BotInfo and SimpleCommand use it instead of
  their own copies.
- v3's defects are fixed: amounts no longer wrap at 32 bits and values above 2147483647 no longer
  leave the response "thinking"; reading a wallet no longer writes one, so `/balance` no longer
  fills the boards with zero wallets; concurrent changes no longer lose updates; an unreadable
  wallet stops the command instead of resetting the guild's data; a member who names someone else
  in `/balance` gets `no-permission` instead of their own wallet; board ties have a fixed order;
  a board template without its row template fails at load instead of at use; the dead Google
  Sheets storage and its hard dependency on GoogleSheetAPI are gone (decision B12).

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Event.kt:26-131`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:18-203`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/MessageReplier.kt:13-69`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/UserData.kt:11-69`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:17-173`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/IStorage.kt:9-23`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/json/JsonData.kt:3-10`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/command/Register.kt:11-204`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/command/CmdFileSerializer.kt:7-59`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/config/ConfigSerializer.kt:6-42`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/config.yaml:1-42`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/info.yaml:1-12`
- `XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/` and `lang/zh-TW/`
  (`register.yaml:1-81` and the ten files under `message/`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:15-41`
  (the global substitutor and `Placeholder.get(user)`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:84-134`
  (rendering without a substitutor, `getMessageData`)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40` and
  `Core/src/main/kotlin/core/json/JsonFileManager.kt:29-113` (the per-guild files)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/GlobalUtil.kt:49-59` (the command and
  prefix filters)

Out of scope: the Google Sheets storage (`SheetImpl.kt`, dead in v3) and its config keys (B12);
moving v3's per-guild files and the legacy single `data/data.json` into the store, which the
deferred data migration does (B11); deleting the wallets of guilds the bot left (v3 kept them);
the Web Dashboard's toggle and reload (B13).

## Capabilities

### New Capabilities

- `plugin-economy`: the Economy plugin.

### Modified Capabilities

- `core-placeholders`: v3's global placeholders are available for templates rendered without a
  user.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/economy/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/economy/` and golden data in
`tests/fixtures/plugins/economy/`. Core: `xincord.core.placeholders.global_values`, which BotInfo
and SimpleCommand now use. Data: one JSON document per guild in the store's key-value table. No
new dependencies. Operators who move from v3 keep their `plugins/Economy/config.yaml` and `lang/`
files; their wallets stay in v3's files until the deferred migration.
