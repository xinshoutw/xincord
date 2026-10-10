## Context

v3's Economy (`Plugins/Economy`, 11 Kotlin files, 1182 lines) keeps two integers per user and
guild: the money (the balance) and the cost (the cumulative spending). `Event`
(`PluginEventConfigure`, `Event.kt:26-131`) exports the lang files, reads `config.yaml`
(`ConfigSerializer.kt:6-42`), loads every `plugins/Economy/data/<guildId>.json` through Core's
`JsonGuildFileManager` and, when enabled, registers nine guild commands (`Register.kt:97-204`) and
forwards them and every button whose ID starts with `economy@` to `Economy` (`Economy.kt:18-203`).
`JsonImpl` (`storage/JsonImpl.kt:17-173`) keeps the wallets in memory with sorted boards and saves
the whole guild file after each change; `SheetImpl` (Google Sheets) is unreachable because `MODE`
is the constant `Mode.Json` (`Event.kt:28`), yet `info.yaml` declares a hard dependency on
GoogleSheetAPI. The inventory is `docs/porting/analysis/inventory/Economy.md`; its section 12
lists fifteen bugs and quirks and the behavior to preserve.

## Goals / Non-Goals

**Goals:** v3's commands, replies, boards, permission layers and per-guild wallets; v3's document
shape in the store, so that the deferred migration can copy v3's files; exact amounts and atomic
changes; every command answers.

**Non-Goals:** Google Sheets (B12); migrating v3's files and the legacy `data/data.json` (B11);
deleting the wallets of guilds the bot left; new commands, history or currency formatting.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/economy/`: `__init__.py` (metadata and `setup`),
  `config.py` (`Config`), `wallet.py` (pure: `Wallet`, v3's operations, the board ranking),
  `store.py` (the guild documents in the store), `cog.py` (`IDS`, the commands, the button
  handler and the board template check), `config.yaml` and `lang/`. Entry point
  `Economy = "xincord.plugins.economy"`.
- `DEPENDS` and `SOFT_DEPENDS` are empty: v3's hard `depend_plugins: [GoogleSheetAPI]` served only
  the dead Sheets path (B12). `INTENTS = discord.Intents.none()`: the `member` option is resolved
  from the interaction payload and nothing reads the member cache. `DEFAULT_LOCALE = "zh-TW"`, v3's
  hard-coded default and fallback.
- `lang/` holds v3's 22 files (`register.yaml` and `message/{balance,no-permission,top-money,
  top-cost,add-money,remove-money,set-money,add-cost,remove-cost,set-cost}.yaml` per locale) with
  LF line endings (both `register.yaml` files had CRLF lines) and v3's text, en-US copy-paste
  author names included (see "Kept on purpose").
- `config.yaml` holds `admin_id: []` and `board_user_show_limit: 10`, with comments: the
  administrators are user IDs, at least one is needed, and an example list. v3's file shipped two
  real user IDs and the Google OAuth setup notes, which are gone.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists the five modules, `config.yaml`, the 22 lang files and
  the `Economy` entry point. `xincord --no-online`, run from a scratch virtual environment with both
  wheels and `plugins: [Economy]`, writes `plugins/Economy/config.yaml` (the bundled file) and the
  22 lang files and exits with 1, naming `admin_id`; with an operator's `admin_id` it loads the
  plugin and exits with 0; with v3's `config.yaml` it warns about `enabled` and the eight Google
  Sheets keys and exits with 0.
- A scratch probe drove the plugin through discord.py's own objects (`discord.Interaction` built
  from gateway payloads, the tree's `_call` and `Bot.on_interaction`), with `HTTPClient.request`
  and the webhook adapter's `request` recorded: every command deferred with type 5 and the
  ephemeral flag and then edited `@original`; `add-money` and `remove-money` (zh-TW) showed the
  amounts before and after; a user option that Discord resolved without a member changed that
  user's wallet, by 2^53 exactly; `set-cost` with -1 answered `Bad Value`; a user outside
  `admin_id` got `no-permission` for a change and for naming someone in `balance`; both boards
  listed the wallets in order in both locales; a v3 `economy@` button deferred ephemerally and
  showed the presser's wallet, and the core fetched the message and patched its button's ID to
  `economy:1:`.

### Config

`Config(Model)`:

- `admin_id: tuple[int, ...]` with at least one item, required. v3 defaulted it to `[]` and its
  `init` block refused an empty list, so an operator's file without it failed in v3 too; the
  pydantic error names `admin_id`. The bundled file leaves it empty, so the plugin does not load
  until the operator lists the administrators (no real ID ships, and an example ID would grant a
  stranger the commands).
- `board_user_show_limit: int`, 1 to 25, default 10, v3's range.
- v3's `enabled`, `client_id`, `client_secret`, `port`, `sheet_id`, `sheet_label`,
  `sheet_range_id`, `sheet_range_money` and `sheet_range_cost` are not fields: a v3 file loads and
  each of them logs an `unknown key` warning (the core's rule). v3's `port` range check goes with
  them.

### Storage

`store.py` keeps the wallets in the store's key-value table: namespace `Economy` (the plugin's
name), key the guild ID in decimal, value v3's document `{"<user ID>": {"cost": <int>, "money":
<int>}}`, Moshi's field order and compact form, so that the deferred migration (B11) can copy v3's
`plugins/Economy/data/<guildId>.json` files.

- `read(store, guild_id, user_id)` and `read_all(store, guild_id)` never write: a guild or a user
  without an entry has money 0 and cost 0 (v3 created both and saved the file).
- `change(store, guild_id, user_id, operation, value)` runs one `Store.update`: the function reads
  the document, applies the operation and returns a new document with that user's entry rewritten
  (`cost` and `money` only, as Moshi re-saved it) and every other entry unchanged, including keys
  that are not user IDs (v3 kept them in the file and skipped them in memory). The update is one
  SQLite transaction on the store's single thread, so concurrent changes are serialized; discord.py
  runs handlers concurrently, and v3's button callback ran beside the gateway thread with no lock.
  It returns the wallet before and after.
- An entry that exists but is not an object whose `money` and `cost` are JSON integers (booleans
  excluded) raises `DataError`, which names the guild and the user; a change rolls back and
  writes nothing. v3's Moshi refused such entries too, and Core then replaced the whole file with
  `{}`. Moshi also read quoted numbers; v3 rewrote every file with plain numbers at each load, so
  stored documents have none, and the migration can convert any that remain. A document that is
  not an object raises `DataError` too.
- A board reads the entries whose key is a canonical decimal user ID (`[1-9][0-9]*`); other keys
  are skipped, as v3's `toLongOrNull` skipped them.
- Data of guilds the bot left is kept, as in v3: no `on_guild_remove` and no cleanup at READY.
  Wallets may hold real value (the templates show a currency), and a kick by mistake must not
  erase them.

### Arithmetic

`wallet.py` has `Wallet(money: int = 0, cost: int = 0)` (frozen) and `OPERATIONS`, keyed by v3's
command names, each a pure function of the wallet and the amount (`UserData.kt:21-68`):
`add-money` money + v; `remove-money` money - v and cost + v; `set-money` money = v; `add-cost`
cost + v; `remove-cost` cost - v; `set-cost` cost = v. Python's integers are exact and unbounded,
so nothing wraps. Discord limits an integer option to plus or minus 2^53, and each change adds at
most that much, so the amounts stay far below the 4300 digits that Python's `str` accepts.

### Commands

- `COMMANDS` maps each of v3's nine names, in v3's order, to a `CommandSpec(kind, description,
  member, value)`: the callback kind (`balance`, `board` or `change`) and v3's base texts from
  `Register.kt` (the command's description and the options' descriptions). `Economy.command(name)`
  builds it with `app_commands.Command` and the cog's bound method (`show_balance`, `show_board`
  or `change_wallet`), `rename` and `describe` from `register.yaml` (`<name>.name`,
  `<name>.description`, `<name>.options.member.*`, `<name>.options.value.*`; v3's lookup keys were
  the Kotlin properties `topMoney`, `addMoney`, ...).
- `balance` has no default permissions (v3's `DefaultMemberPermissions.ENABLED`); the other eight
  get `app_commands.default_permissions(administrator=True)` (v3's `enabledFor(ADMINISTRATOR)`).
  Guild commands, as v3's `guildCommands()`.
- `member` is `discord.Member | discord.User` (optional, default None, for `balance`): v3 read it
  with `asUser`, so users outside the guild count, and discord.py passes the user when Discord
  resolved no member. `value` is a plain `int`, an integer option without limits, as in v3.
- The command tree defers each command ephemerally, as v3's core did, and every answer edits that
  response, rendered in `interaction.locale` (v3's `event.userLocale`).
- The shared callbacks read the invoked name from `interaction.command.name` (SimpleCommand's and
  WelcomeByeGuild's pattern). A command without a guild cannot happen for guild commands; the
  callbacks return without an answer there, as v3's `event.guild?.idLong ?: return`.

### Values

- A user's values are `actor_values(user, bot)`, v3's `Placeholder.get(user)` (`bot_id`,
  `bot_name`, `user_id`, `user_mention`, `user_name`, `user_avatar_url`; discord.py's members add
  the `member_` keys, which v3's users lacked and no template uses).
- A wallet adds `economy_money` and `economy_cost`; a change adds `economy_money_before` and
  `economy_cost_before`, both for every change command (v3 set only the ones of the amounts the
  command changed).
- `no-permission` gets `global_values(interaction.client)`: v3 rendered it without a substitutor,
  that is with its global keys `bot_id` and `bot_name`.
- Amounts are rendered with `str(int)`, as Kotlin's `"$money"`.

### Balance

`show_balance(interaction, member=None)` (`Economy.kt:62-71`, `:185-188`): the target is `member`
or the user. When the target is someone else and the user is not in `admin_id`, the response is
`no-permission` (v3 silently showed the user's own wallet). Otherwise the response is `balance`
with the target's values and wallet, read without writing.

### Changes

`change_wallet(interaction, member, value)` (`Economy.kt:73-139`) follows v3's order: a user not in
`admin_id` gets `no-permission` before the value is looked at; a negative value gets the content
`Bad Value` (v3's text, not localized, as v3); otherwise `change` applies `OPERATIONS[name]` to
`member`'s wallet and the response is the message named like the command, with `member`'s values
and the wallet before and after. 0 is accepted and records a wallet, as in v3.

### Boards

- `rank(wallets, kind, limit)` (pure) sorts the user IDs by `-amount`, then by the ID, and keeps the
  first `limit`. v3 used a stable descending sort over a list in Java `HashMap` order with new users
  appended, so its ties had no defined order.
- `show_board(interaction)` (`Economy.kt:42-53`, `MessageReplier.kt:44-68`,
  `JsonImpl.kt:90-120`): a user not in `admin_id` gets `no-permission`; otherwise the template named
  like the command is rendered with the user's values (v3's `Placeholder.get(event.user)`), each
  ranked wallet renders the first embed's raw description with those values and `index` (from 1),
  `name_mention` (`<@id>`) and `economy_board` (the amount), the rows are joined without a
  separator, and a copy of the first rendered embed gets them as its description (none for an empty
  board) and becomes the message's only embed, as v3's `setEmbeds`. The content and components of
  the template stay, as in v3's builder. Nothing is written (v3 created an empty guild file).
- `check_boards(lang, templates)` runs in `setup`: for each loaded locale, the `top-money` and
  `top-cost` templates that the locale resolves to must have a first embed that is not a
  `model_key` and has a description; otherwise `setup` raises `TemplateError` with the file's path
  and the plugin does not load. v3 threw a `NullPointerException` at each use instead.

### Component IDs

`IDS = ComponentIds("economy", ("action",), legacy_prefix="economy@")`: v3 declared no fields and
only checked the prefix from `info.yaml`; `action` is there because a codec needs one field and v3
plugins start with it. `setup` routes `IDS` to `Economy.handle` (`Economy.kt:34-39`, `:55-60`),
which answers a button interaction in a guild, whatever its fields: it defers ephemerally, as v3's
`deferReply(true)`, and edits the response into `balance` with the presser's values and wallet.
Other component types (v3 handled buttons only) and interactions outside a guild get no answer, as
in v3. The core parses v3's IDs (`economy@` alone, or v3's `<letter>:<value>` segments) and
upgrades the message's buttons afterwards (`economy@` becomes `economy:1:`). No v3 or bundled
template produces such a button; an operator's Components V2 template can, with a raw `custom_id`.

### Core: global values

`xincord.core.placeholders.global_values(client)` returns `{"bot_id", "bot_name"}` of
`client.user`, or nothing before the bot logged in: v3's `Placeholder.globalSubstitutor`, used by
`getCreateBuilder(key, locale)` without a substitutor. BotInfo and SimpleCommand had a private
copy (`_bot_values`); Economy is the third user, so the helper moves into the core and both
plugins call it. Their behavior does not change.

### Tests

- `tests/core/test_placeholders_events.py` covers `global_values`.
- `tests/plugins/economy/`: `test_plugin.py`, `test_config.py`, `test_wallet.py`, `test_store.py`,
  `test_balance.py`, `test_change.py`, `test_board.py`, `test_button.py` and `test_command.py`;
  `conftest.py` loads the plugin with an operator config that lists the administrator 1, and finds
  the cog with `cast`, because `test_config.py` loads invalid files.
- `tests/fixtures/plugins/economy/golden.yaml`: v3's embeds per locale for every template with
  example values, v3's config file with example IDs, and the translated command payloads.

### v3 behaved differently

- v3 behaved differently: amounts were 32-bit `Int`s that wrapped silently (`2147483647 + 1` was
  saved as `-2147483648`), and a `value` beyond the 32-bit range threw in `asInt`, leaving the
  response "thinking"; amounts are exact integers, and any value Discord sends is applied.
- v3 behaved differently: `/balance`, the button and the boards created the user's wallet (and the
  guild's file) when reading, so every member who ran `/balance` appeared on the boards at 0;
  reading writes nothing, and only changed wallets are ranked.
- v3 behaved differently: a user who is not an administrator and named another member in
  `/balance` silently got their own wallet; they get `no-permission`.
- v3 behaved differently: ties on a board had no defined order (Java `HashMap` order and a stable
  sort); they are ordered by user ID.
- v3 behaved differently: a change could lose a concurrent one (the button callback ran on JDA's
  callback pool beside the gateway thread, without a lock); a change is one store transaction.
- v3 behaved differently: an unreadable file was replaced by `{}` and saved, losing the guild's
  wallets, and files were written in place; an unreadable entry stops the command with an error
  and is never overwritten, and the store's writes are transactions.
- v3 behaved differently: each change reply set only the before values of the amounts it changed,
  and the other key kept whatever an earlier command had left in the user's cached placeholders;
  every change reply has both before values.
- v3 behaved differently: the placeholders lived in per-user caches shared by every plugin and
  every guild; each render has its own values.
- v3 behaved differently: a board template without a description threw at each use and gave no
  reply; it disables the plugin at load with the file named.
- v3 behaved differently: Economy did not load without the GoogleSheetAPI plugin, which only the
  dead Sheets storage used; it has no dependency, and the Sheets keys only warn.
- v3 behaved differently: an empty `admin_id`, a `port` outside 1 to 65535 or a limit outside 1 to
  25 stopped the whole bot, even with the plugin disabled; only Economy is disabled (the `port` is
  gone), unknown keys warn, and the file is read only when `plugins` lists the plugin.
- v3 behaved differently: the commands needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers them.
- v3 behaved differently: every load and reload rewrote every guild file, and a file whose name was
  not a number stopped the load; the store is read only when a command needs it.

Kept on purpose: the two permission layers (Discord's Administrator default and `admin_id`, global
to every guild); every reply ephemeral; `Bad Value` in English for every locale and as plain
content; 0 accepted and negative amounts refused; balances and costs allowed to go negative;
`remove-money` moving the amount into the cost; boards listing wallets at 0 and users outside the
guild; the row template with its trailing blank line; v3's en-US author names `Pocket Add Balance`
and `Pocket Reduce Balance` on `add-cost` and `remove-cost` (operators' copy, not a defect of the
code); the wallets of guilds the bot left; no answer outside a guild.

### Inventory audit

Every section of `docs/porting/analysis/inventory/Economy.md` maps to this change:

- Overview (1): the entry object, `info.yaml` and the name are "The plugin installs as Economy"
  ("Discovered by name", without GoogleSheetAPI); `component_prefix: economy@` is `IDS`'s legacy
  prefix ("v3 button"); `SheetImpl`, `Mode` and the GoogleSheetAPI build dependency are out of
  scope (B12); `author`, `coreApi` and `version` have no counterpart.
- Lifecycle (2): exporting the lang files and reading the config are "First load creates the
  files" and the config scenarios; validation while disabled and the bot-wide abort are a "v3
  behaved differently" entry; `enabled` is the core's `plugins` list; the legacy `data.json`
  migration is out of scope (B11, see "Risks"); the eager load and re-save of every guild file and
  the non-numeric file name are a "v3 behaved differently" entry (the store is read per command);
  the hard-coded zh-TW `StringLocalizer` is `DEFAULT_LOCALE`; `init()` and the redundant sorts
  have no counterpart (`rank` sorts per board); `reload()` is the core's reload; `unload()` and
  background jobs: none; the in-memory maps and the shared `DataContainer` are replaced by reads
  of the store.
- Slash commands (3): the nine guild commands, their texts, options, localizations and default
  permissions are "Command payloads"; the name filter and the `top-` dispatch are the tree and the
  `kind` in `COMMANDS`; the silent `guild == null` return is "Outside a guild"; the two permission
  layers are the payload's default permissions and "Only administrators change wallets and see
  boards" (Discord's Administrator does not count); the ephemeral auto-defer is "Command
  callbacks". `/balance`: the target rules are "Own wallet", "Administrator names a member" and
  "Member names someone else" (a "v3 behaved differently" entry), the created record is "No
  wallet yet", the placeholders and the template are the golden `balance`. Boards: the admin check
  is "Member asks for a board", the template copy with a reset description and the appended rows
  are "Money board" and the operator-template test, the stable sort and the tie order are "Order
  and ties", the limit is "Limit", zeros are listed ("Order and ties" for the cost board), the
  empty board without description and without a created file is "Empty board", the mutated
  substitutor is per-render values. Changes: the admin check before the value is "Member changes a
  wallet"; `asInt` beyond 32 bits and the `Int` wrap are "Past 32 bits"; `Bad Value` and 0 are
  "Negative amount" and "Zero"; the target is "Change reply" and "User outside the guild"; the six
  operations are "Each operation"; the before keys are "Change reply" (both keys, a "v3 behaved
  differently" entry); the template named like the command is the golden `changes`; re-sorting
  every guild has no counterpart.
- Components (4): any `economy@` button is "v3 button" (decoded by the core, upgraded to
  `economy:1:`) and "New button"; no answer outside a guild is "Outside a guild"; the
  `deferReply(true)` and the edit are checked in every button test; the created record is "No
  wallet yet" in the button tests; no expiry: kept; IDs that are not in v3's field format are a
  "v3 behaved differently" entry; no selects or modals: "Outside a guild" covers a select and a
  modal with an Economy ID.
- Events (5): the command and button listeners are the tree and `bot.route`; no
  `GuildLeaveEvent`: the wallets of left guilds are kept (Storage).
- Configuration (6): `enabled` and the eight Sheets keys warn ("v3's file"); `port` and its check
  are gone; `admin_id` must list someone ("Invalid values", "Bundled file"); the limit's range is
  "Invalid values" and "Limit"; the shipped real IDs and the OAuth notes are gone (bundled file);
  kaml's strict mode and the bot-wide abort are "v3 behaved differently" entries.
- Localization and templates (7): en-US and zh-TW with the zh-TW default are `DEFAULT_LOCALE` and
  the bundled files; the user's locale is tested in both locales for every reply; the missing-key
  exception is the core's per-file fallback; the shared embed elements, the currency suffixes and
  the copy-paste author names are the golden embeds ("Kept on purpose" for the names); the
  plugin's placeholders and `user_name` are the golden embeds; the global per-user substitutor is
  per-render values.
- Persistence (8): one document per guild under `Economy` ("First change"), Moshi's compact form
  and field order ("First change"), non-numeric keys kept and skipped ("Other entries kept"),
  unknown fields ignored ("Other entries kept"); quoted numbers, null, missing fields and
  fractions are "Unreadable entry" (the quoted numbers are discussed under Storage); values beyond
  32 bits are accepted ("Past 32 bits"); the reset to `{}` and the in-place writes are a "v3
  behaved differently" entry; records created by reads are "No wallet yet" and "Empty board"; no
  deletion path: kept; the legacy migration and the Sheets layout are out of scope.
- External dependencies (9): GoogleSheetAPI and its Google libraries are gone; no HTTP, no
  credentials; the imgur author icon stays in the templates.
- Discord requirements (10): no intents ("Discovered by name"); the user option from the payload,
  a defer and an edit per command and per button (the probe).
- Concurrency (11): the button callback pool and the non-atomic read-modify-write are "Changes are
  atomic"; the placeholder cache is per-render values.
- Bugs and quirks (12): 1 and 2 are "Past 32 bits"; 3 is "Unreadable entry"; 4 is "No wallet yet"
  and "Empty board"; 5 is "Discovered by name"; 6 is a "v3 behaved differently" entry and the core's
  config loading; 7 is kept with "v3 button" and "New button"; 8 is out of scope (B11); 9 is
  "Member names someone else"; 10 is "Order and ties"; 11 and 12 are kept on purpose; 13 is
  "Outside a guild"; 14 is "Concurrent changes"; 15 is out of scope (B12). The behavior to
  preserve is listed under "Kept on purpose" and tested by the scenarios above.
- Testability (13): `is_admin` and `resolve_target` are `_is_admin` and the balance tests;
  `validate_value` is the negative tests; `apply_op` is `OPERATIONS`; `build_board` is `rank`;
  `render_board_description` is `_board` with the board tests; the repository is `store.py`; the
  JSON compatibility cases are `test_store.py`; `migrate_legacy` is out of scope; the Discord
  doubles are the shared fakes.
- Assessment (14): the commands are built from `COMMANDS` instead of decorators, with
  `default_permissions(administrator=True)` on eight; guild registration makes them guild-only;
  `member: discord.User` became `discord.Member | discord.User`; `value` stays a plain `int`
  without `Range`, so that negative values get v3's `Bad Value`; the Translator, the auto-defer
  and the edits are as suggested; the files became the store, with atomic updates instead of a
  lock and atomic file writes; the migration is deferred; the button is routed by the core's
  `ComponentIds`; `SheetImpl` and the dependency are dropped.

## Risks / Trade-offs

- The local copy of the production data (`XsDiscordBotKt/Server/plugins/Economy/data/`) holds the
  legacy single `data.json` of v3.2.1, which v3.4 would have moved to the only guild's file at its
  first load. The deferred migration must do the same, or the wallets stay behind.
- An operator's row template long enough to exceed Discord's 4096-character description at 25 rows
  makes Discord refuse the board; the tree logs the error and the response stays "thinking", as
  JDA's `appendDescription` threw in v3.
- An unreadable entry leaves that command's response "thinking" and logs the error; such entries
  can only come from hand edits or a faulty migration, and overwriting them would lose money.
- Wallets of guilds the bot left are never deleted, as in v3; the store grows by one document per
  guild that ever had a wallet.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [Economy]` in `config.yaml`, two accounts (the
administrator, listed in `admin_id`, and a member with neither Administrator nor a listing):

1. Start the bot with the bundled config: the log says Economy is disabled and names `admin_id`;
   `plugins/Economy/config.yaml` and the 22 files under `plugins/Economy/lang/` exist.
2. Put the administrator's ID in `admin_id`, restart: the log lists `Economy` as loaded.
3. As the member, the command list shows only `balance` (with an en-US client: "get current balance
   detail from member"); run it: an ephemeral pocket embed with 0 and 0.
4. As the member, run `balance member:<administrator>`: `no-permission`.
5. As the administrator, run `add-money member:<member> value:100`, then `remove-money` 30, then
   `set-cost` 5: each reply shows the before and after amounts; `balance member:<member>` shows 70
   and 5.
6. Run `add-money` with the value -1: `Bad Value`; with 2147483647 twice: 4294967294 and up.
7. Run `top-money` and `top-cost`: the member and the administrator in amount order, mentions
   shown; in a guild without wallets the board embed has no rows.
8. As the member, run `top-money` through a guild that granted the command in its integration
   settings: `no-permission`.
9. Switch the member's client to zh-TW: the replies use the zh-TW templates and command names.
10. Post a Components V2 message (for example with SimpleCommand) that has a button with
    `custom_id: "economy:1:a=balance"`, press it as the member: an ephemeral pocket embed.

## User-visible changes

Copy: none new. `Bad Value` stays as v3's English text.

1. A user who is not an administrator and names someone else in `/balance` gets `no-permission`
   (v3: their own wallet, without a word).
2. Reading a wallet (`/balance`, a button) no longer creates it, so members appear on the boards
   only once an administrator changed their wallet (v3 ranked everyone who had run `/balance`, at
   0).
3. Board ties are ordered by user ID (v3: no defined order).
4. Amounts beyond 2147483647 work: v3 wrapped them to negative numbers, and values above that
   limit got no reply.
5. Every change reply can show both before values (only matters for operators' templates).
6. The bundled `config.yaml` lists no administrator, so the plugin stays disabled until one is
   added (v3 shipped two real IDs); a v3 file loads unchanged and warns about `enabled` and the
   eight Google Sheets keys; a bad value disables only Economy.
7. Economy no longer needs the GoogleSheetAPI plugin.
8. A board template without a description in its first embed disables the plugin at load.
9. The commands always answer (v3 needed the core's auto-defer switch).
10. `economy@` buttons whose ID is not in v3's field format (`economy@` followed by
    `<letter>:<value>` segments) are logged as malformed instead of showing the wallet; none exist
    in v3's templates or the production copy.
