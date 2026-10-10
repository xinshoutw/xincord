## Why

Decision C1 ports BasicCalculator right after _Example, and F3 lists it as in use. v3's
BasicCalculator (`Plugins/BasicCalculator`, 5 Kotlin files, 326 lines) has one guild command,
`/basic-calculate formula`, which evaluates an arithmetic formula with exact decimals and posts the
result as an embed in the channel, or edits the deferred ephemeral response into an error embed.
B17 asks for golden tests: `docs/porting/analysis/inventory/fixtures/` holds 3155 formulas with
v3's answers, recorded by running v3's evaluator.

## What Changes

- New plugin package `xincord.plugins.basic_calculator`, registered as `BasicCalculator`, with v3's
  en-US and zh-TW lang files and no config file (v3's only key was `enabled`).
- A pure evaluator module that keeps v3's formula language, error messages and exact `BigDecimal`
  results, with v3's defects fixed: a minus after an operator negates (v3 computed `2*-3` as `-3`),
  `^` groups from the right, exponents must be whole numbers (negative ones divide), division by
  zero and oversized numbers get an error instead of no reply, and formulas and numbers have size
  limits so that `10^999999999` cannot stall the bot.
- `/basic-calculate formula` (at most 1018 characters): the answer goes to the channel as v3 did,
  and to the deferred response when the channel refuses it; errors edit the deferred ephemeral
  response.
- Golden tests over v3's 3155 recorded formulas: every record gives v3's answer unless a fixed
  defect changes it, and those agree with an independent evaluator built on Python's expression
  parser.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:14-206`
- `XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/Event.kt:14-62`
- `XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/command/Register.kt:9-27`
- `XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/command/CmdFileSerializer.kt:7-23`
- `XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/config/ConfigSerializer.kt:5-8`
- the lang files under `Plugins/BasicCalculator/src/main/resources/lang/`

Out of scope: functions, constants, exponent notation, unary `+` and other operators v3 did not
read (`%`, `×`, `÷`, `,`, `!`); fractional exponents; localized error messages (v3's were English);
rate limiting; the untracked, empty `Plugins/BasicCalculator/src/index.css`, which nothing uses.

## Capabilities

### New Capabilities

- `plugin-basic-calculator`: the BasicCalculator plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/basic_calculator/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/basic_calculator/` with
fixtures in `tests/fixtures/plugins/basic_calculator/` and a fake channel in
`tests/support/discord_fakes.py`. No core changes and no new dependencies.
