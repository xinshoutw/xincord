# Spec Delta

## Purpose

A per-guild virtual wallet: each user has a balance (money) and a cumulative spending (cost);
listed administrators change them, everyone sees their own wallet, and two leaderboards rank them.

## ADDED Requirements

### Requirement: The plugin installs as Economy
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Economy`, pointing to `xincord.plugins.economy`, with no dependencies (v3's
GoogleSheetAPI is gone) and no intents. It SHALL bundle `config.yaml` and v3's en-US and zh-TW
lang files (`register.yaml` and ten messages each), which its first load writes to
`plugins/Economy/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Economy` enabled and no GoogleSheetAPI installed
- **THEN** it returns `Economy` from `xincord.plugins.economy` with no dependencies and no intents

#### Scenario: First load creates the files
- **WHEN** the plugin is enabled in an empty directory
- **THEN** `plugins/Economy/config.yaml` is the bundled file and the 22 lang files exist under
  `plugins/Economy/lang/`, and the plugin loads once `admin_id` lists an administrator

### Requirement: The config lists the administrators
`config.yaml` SHALL hold `admin_id`, the IDs of the users who change wallets and see the boards
and other users' wallets, and `board_user_show_limit`, the number of board rows, 1 to 25 with the
default 10. As in v3, `admin_id` SHALL list at least one ID; otherwise, or with a limit out of
range, the plugin SHALL not load and the error SHALL name the key. v3's `enabled` and Google
Sheets keys SHALL only warn.

#### Scenario: v3's file
- **WHEN** `config.yaml` is v3's file, with `enabled` and the Google Sheets keys
- **THEN** the plugin loads with its administrators and its limit, and warnings name `enabled` and
  each Google Sheets key

#### Scenario: Bundled file
- **WHEN** the bundled `config.yaml` loads
- **THEN** the plugin does not load and the error names `admin_id`, which the file leaves for the
  operator to fill

#### Scenario: Invalid values
- **WHEN** `admin_id` is missing or empty, or `board_user_show_limit` is 0 or 26
- **THEN** the plugin does not load and the error names the key

### Requirement: Changes follow v3's arithmetic
The change commands SHALL apply v3's operations to a wallet with exact integers that never wrap:
`add-money` adds the amount to the money, `remove-money` subtracts it from the money and adds it
to the cost, `set-money` sets the money, `add-cost` adds it to the cost, `remove-cost` subtracts it
from the cost and `set-cost` sets the cost. Money and cost MAY become negative.

#### Scenario: Each operation
- **WHEN** a wallet with money 100 and cost 20 is changed by 30
- **THEN** `add-money` gives 130 and 20, `remove-money` 70 and 50, `set-money` 30 and 20,
  `add-cost` 100 and 50, `remove-cost` 100 and -10, and `set-cost` 100 and 30

#### Scenario: Past 32 bits
- **WHEN** 1 is added to the money 2147483647, or 2^53 to the money 2^53
- **THEN** the money is 2147483648, or 2^54, where v3 wrapped to -2147483648 or gave no reply

### Requirement: Wallets are kept per guild in v3's documents
The plugin SHALL keep a guild's wallets in the store under the namespace `Economy` and the guild's
ID, as v3's document `{"<user ID>": {"cost": <cost>, "money": <money>}}`. A user without an entry
SHALL have money and cost 0, and reading SHALL never write. A change SHALL rewrite only that user's
entry. An entry whose money or cost is not an integer SHALL stop the command with an error and
SHALL never be overwritten.

#### Scenario: First change
- **WHEN** the first change in guild 10 gives user 7 the money 5
- **THEN** the store holds `{"7": {"cost": 0, "money": 5}}` under `Economy` and `10`

#### Scenario: User without a wallet
- **WHEN** user 8 has no entry in guild 10
- **THEN** their wallet has money 0 and cost 0, and nothing is written

#### Scenario: Other entries kept
- **WHEN** the document also holds other users, a key that is not a user ID and a field that is
  not v3's
- **THEN** a change of user 7 leaves the other entries as they were and writes user 7's entry as
  `cost` and `money` only

#### Scenario: Unreadable entry
- **WHEN** user 7's entry has the cost `"7"`, the money null or no money
- **THEN** reading or changing user 7's wallet raises an error and the document stays as it was

### Requirement: Changes are atomic
A change SHALL read and write the guild's document in one store transaction, so that concurrent
changes never lose one another, where v3 could lose updates between JDA's threads.

#### Scenario: Concurrent changes
- **WHEN** 50 `add-money` changes of 1 run concurrently for one user
- **THEN** that user's money is 50

### Requirement: The balance shows a wallet
`balance` SHALL replace the deferred response with the `balance` message in the user's locale,
with the target's v3 values, `%economy_money%` and `%economy_cost%`. The target SHALL be the user,
or the `member` option's user when an administrator names one. A user who is not an administrator
and names someone else SHALL get `no-permission`. Nothing SHALL be written.

#### Scenario: Own wallet
- **WHEN** bob, with the money 1500 and the cost 990, runs `balance` with an en-US or a zh-TW
  client
- **THEN** the response is v3's `balance` embed in that locale with bob's name and both amounts

#### Scenario: No wallet yet
- **WHEN** a user without a wallet runs `balance`
- **THEN** the response shows the amounts 0 and 0, and nothing is written

#### Scenario: Administrator names a member
- **WHEN** an administrator runs `balance` naming bob
- **THEN** the response shows bob's name and wallet

#### Scenario: Member names someone else
- **WHEN** a user who is not an administrator runs `balance` naming bob, or naming themselves
- **THEN** the response is `no-permission`, or their own wallet

### Requirement: Administrators change wallets
`add-money`, `remove-money`, `set-money`, `add-cost`, `remove-cost` and `set-cost` SHALL change the
`member` option's wallet by `value` and replace the deferred response with the message named like
the command, in the user's locale, with the member's v3 values, the new `%economy_money%` and
`%economy_cost%` and the previous `%economy_money_before%` and `%economy_cost_before%`.

#### Scenario: Change reply
- **WHEN** an administrator with an en-US or a zh-TW client runs one of the six commands for bob,
  with the money 100 and the cost 20, and the value 30
- **THEN** bob's wallet changes as that command does, and the response is v3's embed of that
  command in that locale with bob's name and the amounts before and after

#### Scenario: User outside the guild
- **WHEN** the `member` option names a user who is not in the guild
- **THEN** that user's wallet changes, as in v3

### Requirement: Only administrators change wallets and see boards
A user whose ID `admin_id` does not list SHALL get `no-permission`, rendered in the user's locale
with v3's global values, for the six change commands and both boards, before the amount is
checked, and nothing SHALL be written. Discord's Administrator permission SHALL not count.

#### Scenario: Member changes a wallet
- **WHEN** a user with Discord's Administrator permission whose ID `admin_id` does not list runs
  `add-money` with the value -5
- **THEN** the response is v3's `no-permission` embed in the user's locale and nothing is written

#### Scenario: Member asks for a board
- **WHEN** a user whose ID `admin_id` does not list runs `top-money` or `top-cost`
- **THEN** the response is `no-permission`

### Requirement: Negative amounts are refused
A change command whose `value` is negative SHALL replace the deferred response with v3's text
`Bad Value` and write nothing. The value 0 SHALL be accepted.

#### Scenario: Negative amount
- **WHEN** an administrator runs `remove-money` with the value -1
- **THEN** the response is `Bad Value` and nothing is written

#### Scenario: Zero
- **WHEN** an administrator runs `add-money` with the value 0 for a user without a wallet
- **THEN** the response is the `add-money` message and the user has a wallet with 0 and 0

### Requirement: Boards rank the wallets
A board SHALL rank every wallet of the guild, those at 0 included, by money for `top-money` and by
cost for `top-cost`, from the highest amount; equal amounts SHALL be ordered by user ID, the lowest
first. At most `board_user_show_limit` wallets SHALL be ranked.

#### Scenario: Order and ties
- **WHEN** users 3, 2 and 1 have the money 20, 50 and 20
- **THEN** the money board ranks user 2, then 1, then 3

#### Scenario: Limit
- **WHEN** 30 users have wallets and the limit is 25
- **THEN** the board ranks the 25 highest

### Requirement: Administrators see the boards
`top-money` and `top-cost` SHALL replace the deferred response with the message named like the
command, in the user's locale with the user's v3 values. Its first embed's description SHALL hold
one row per ranked wallet, rendered from that description with `%index%`, `%name_mention%` and
`%economy_board%`, and other embeds SHALL be dropped. Without wallets, the embed SHALL have no
description. Nothing SHALL be written.

#### Scenario: Money board
- **WHEN** an administrator with an en-US or a zh-TW client runs `top-money` in a guild where users
  2, 1 and 3 have the money 50, 20 and 20
- **THEN** the response is v3's money board embed in that locale with three rows in that order

#### Scenario: Empty board
- **WHEN** an administrator runs `top-cost` in a guild without wallets
- **THEN** the response is v3's cost board embed without a description, and nothing is written

### Requirement: Board templates are checked at load
The plugin SHALL not load when the `top-money` or `top-cost` message of a locale has no first
embed with a description, the template of the board's rows, and the error SHALL name the file.

#### Scenario: Missing row template
- **WHEN** an operator's `top-cost` message has an embed without a description
- **THEN** the plugin does not load and the error names that file

### Requirement: Economy buttons show the presser's wallet
A button whose ID the plugin owns, in the new format or in v3's `economy@` format, SHALL answer the
presser with the `balance` message in an ephemeral response, in their locale with their values and
wallet, whatever the ID's fields. Outside a guild, and for other components, nothing SHALL be
answered, as in v3. Nothing SHALL be written.

#### Scenario: v3 button
- **WHEN** bob presses a button with the ID `economy@` on a message in a guild
- **THEN** he gets his wallet in an ephemeral `balance` message, and the button's ID becomes
  `economy:1:`

#### Scenario: New button
- **WHEN** bob presses a button with the ID `economy:1:a=balance`
- **THEN** he gets his wallet in an ephemeral `balance` message

#### Scenario: Outside a guild
- **WHEN** a button with an Economy ID is pressed outside a guild, or a select menu has one
- **THEN** nothing is answered

### Requirement: The commands are localized guild commands
The plugin SHALL register v3's nine guild commands with v3's names, descriptions and
localizations: `balance`, with the optional user option `member`, for everyone; `top-money` and
`top-cost`; and the six change commands, with the required user option `member` and integer option
`value`. All but `balance` SHALL be visible to administrators by default. The tree SHALL defer them
ephemerally.

#### Scenario: Command payloads
- **WHEN** the guild command payload is built
- **THEN** the nine commands have v3's descriptions, options and en-US and zh-TW localizations,
  `balance` has no default member permissions and the others have 8

#### Scenario: Command callbacks
- **WHEN** each command runs
- **THEN** its callback, bound to the plugin's cog, answers in the response that the tree deferred
  ephemerally
