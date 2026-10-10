## Purpose

`/basic-calculate` evaluates an arithmetic formula exactly and posts the result in the channel, or
answers privately with the reason it cannot.

## ADDED Requirements

### Requirement: The plugin installs as Calculator
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Calculator`, pointing to `xincord.plugins.calculator`, with no dependencies and
no extra intents. It SHALL bundle en-US and zh-TW lang files, which its first load writes to
`plugins/Calculator/`, and no config file.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Calculator` enabled
- **THEN** it returns `Calculator` from `xincord.plugins.calculator` with no
  dependencies and no intents

#### Scenario: First load creates the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** `register.yaml`, `message/basic-calculate.yaml` and `message/error.yaml` exist for en-US
  and zh-TW under `plugins/Calculator/lang/`, and no `config.yaml` is written

### Requirement: Formulas are trimmed as in v3
The plugin SHALL remove the formula's leading and trailing whitespace as Kotlin's `trim()` did, for
which U+0085 is not whitespace, then its trailing `?`, `=` and spaces, and use the result as the
formula everywhere.

#### Scenario: Trailing signs
- **WHEN** the formulas `1+1 = ?` and `1 + 1 ==` are trimmed
- **THEN** they become `1+1` and `1 + 1`

#### Scenario: Whitespace
- **WHEN** a formula is surrounded by ideographic spaces, or ends with U+0085
- **THEN** the ideographic spaces are removed and U+0085 stays

#### Scenario: Leading signs stay
- **WHEN** the formula `?1+1` is trimmed
- **THEN** it stays `?1+1`

### Requirement: Formulas are read with v3's syntax
The plugin SHALL read numbers (runs of digits and `.`), `+ - * / ^` and brackets, skip whitespace,
multiply implicitly between a number or `)` and a following number or `(`, and rank `^` over `* /`
over `+ -`, failing with v3's `Unknown character: <c>` and `Unmatched bracket`. A minus at the start
or after an operator or `(` SHALL negate, binding tighter than `* /` and looser than `^`; `^` SHALL
group from the right. Formulas over 1018 characters SHALL fail with `Formula too long`.

#### Scenario: Implicit multiplication
- **WHEN** `2 3`, `2(3)`, `(2)3` and `8/2(2+2)` are read
- **THEN** they read as `2 * 3`, `2 * 3`, `2 * 3` and `(8 / 2) * (2 + 2)`

#### Scenario: Minus after an operator
- **WHEN** `2*-3`, `2--3`, `-2*3`, `-2^2` and `2^-1` are read
- **THEN** they read as `2 * (-3)`, `2 - (-3)`, `(-2) * 3`, `-(2 ^ 2)` and `2 ^ (-1)`

#### Scenario: Powers group from the right
- **WHEN** `2^3^2` is read
- **THEN** it reads as `2 ^ (3 ^ 2)`

#### Scenario: Reading errors
- **WHEN** `1e5`, `(a`, `1)`, `)a` and `(1` are read
- **THEN** they fail with `Unknown character: e`, `Unknown character: a` and, for the last three,
  `Unmatched bracket`

#### Scenario: Long formulas
- **WHEN** a formula of 1019 characters is read
- **THEN** it fails with `Formula too long`, and one of 1018 characters is read

### Requirement: Results are exact and rounded as in v3
The plugin SHALL compute exactly, as v3's `BigDecimal`: a number is ASCII digits with at most one
`.`, else `Unknown Token: <token>`; a missing operand is `Illegal formula`; `/` rounds half up to 10
places and fails with `Division by zero`; the result is rounded half up to 5 places with no trailing
zeros, exponent or `-0`. A value needing over 50,000 digits or decimal places, or a result over 1018
characters, SHALL fail with `Too many digits`.

#### Scenario: Exact arithmetic
- **WHEN** `123456789012345678901234567890*10` and `0.1+0.2` are evaluated
- **THEN** the results are `1234567890123456789012345678900` and `0.3`

#### Scenario: Rounding
- **WHEN** `2/3`, `1/3*3`, `0.000005`, `0-0.000001` and `499999951/100000000000000` are evaluated
- **THEN** the results are `0.66667`, `1`, `0.00001`, `0` and `0.00001`

#### Scenario: Number and operand errors
- **WHEN** `.`, `1.2.3`, a fullwidth `3`, `+3` and `()` are evaluated
- **THEN** the first three fail with `Unknown Token: <token>` and the last two with `Illegal formula`

#### Scenario: Division by zero
- **WHEN** `1/0` and `3/(1-1)` are evaluated
- **THEN** both fail with `Division by zero`

#### Scenario: Errors in evaluation order
- **WHEN** `1/0+1.2.3` and `+ 1.2.3` are evaluated
- **THEN** they fail with `Division by zero` and `Unknown Token: 1.2.3`

#### Scenario: Too many digits
- **WHEN** fifty-one numbers of 1000 nines are multiplied, or two numbers of 600 nines
- **THEN** both fail with `Too many digits`

### Requirement: Powers take whole exponents
`a^b` SHALL be exact for a whole number `b`, with `0^0` giving 1; a negative exponent SHALL give
`1 / a^-b`, rounded as a division; an exponent that is not a whole number SHALL fail with `Exponent
must be an integer`. A power that would need over 50,000 digits or decimal places SHALL fail with
`Too many digits` before it is computed.

#### Scenario: Whole exponents
- **WHEN** `2^64`, `0.5^2`, `0^0` and `2^2.0` are evaluated
- **THEN** the results are `18446744073709551616`, `0.25`, `1` and `4`

#### Scenario: Negative exponents
- **WHEN** `2^-1`, `2^(0-2)`, `3^-1` and `0^-1` are evaluated
- **THEN** the first three give `0.5`, `0.25` and `0.33333`, and `0^-1` fails with `Division by
  zero`

#### Scenario: Fractional exponents
- **WHEN** `2^0.5` and `4^(1/2)` are evaluated
- **THEN** both fail with `Exponent must be an integer`

#### Scenario: Huge powers
- **WHEN** `10^999999999`, `2^4294967297` and `0.1^60000` are evaluated
- **THEN** each fails with `Too many digits` at once, while `1^4294967297` gives `1`

### Requirement: The golden formulas give v3's answers
Each record of v3's golden files SHALL trim to v3's formula and give v3's result or error message,
unless it has a minus after an operator, a `^` or a v3 `ArithmeticException`; such a record SHALL
give the answer of an independent evaluator that follows these requirements through Python's
expression parser instead.

#### Scenario: Golden files
- **WHEN** the 3155 records of v3's golden and edge-case files are calculated
- **THEN** each gives v3's formula and v3's answer, or differs for one of the reasons above and
  agrees with the independent evaluator

#### Scenario: Independent evaluator
- **WHEN** the independent evaluator reads a golden formula
- **THEN** its answer is the plugin's

### Requirement: The answer is posted in the channel
On success the plugin SHALL send the `basic-calculate` template in the user's locale, falling back
to zh-TW, to the command's channel, then delete the deferred response. Values: `%bc_question%`,
`%bc_answer%`, `%bc_answer_round%` (the part before the decimal point) and v3's member
placeholders. If the channel cannot take the message, the plugin SHALL edit the deferred response
into it instead.

#### Scenario: Answer
- **WHEN** an en-US user runs the command with `1+1 = ?`
- **THEN** the channel receives v3's en-US calculator embed showing `1+1` and `2`, and the deferred
  response is deleted

#### Scenario: Locale and fallback
- **WHEN** a zh-TW user and a Japanese user run the command with `1+1 = ?`
- **THEN** both get v3's zh-TW calculator embed

#### Scenario: Placeholders
- **WHEN** the operator's en-US template has the content `%user_name%: %bc_question% =
  %bc_answer% (%bc_answer_round%)` and alice runs the command with `-7/2`
- **THEN** the message's content is `alice: -7/2 = -3.5 (-3)`

#### Scenario: Channel refuses the message
- **WHEN** sending to the channel fails with a Discord error, or the channel cannot hold messages
- **THEN** the deferred response is edited into the answer and not deleted

### Requirement: Errors are answered privately
When the formula cannot be calculated, the plugin SHALL edit the deferred ephemeral response into
the `error` template in the user's locale, falling back to zh-TW, with `%bc_question%`,
`%bc_error%` (the English message) and v3's member placeholders. The formula SHALL be shown as
typed.

#### Scenario: Error
- **WHEN** an en-US user and a zh-TW user run the command with `1e5`
- **THEN** each deferred response becomes v3's error embed in that locale, showing `1e5` and
  `Unknown character: e`, and nothing is sent to the channel

#### Scenario: Placeholder text in the formula
- **WHEN** the formula is `%bot_name%`
- **THEN** the error embed shows `%bot_name%` and `Unknown character: %`

### Requirement: The command is a localized guild command
The plugin SHALL register the guild command `basic-calculate` with a required text option `formula`
of at most 1018 characters. Names and descriptions SHALL default to v3's and be localized in en-US
and zh-TW from `register.yaml`, with the en-US `formula` description corrected. The command SHALL
keep the command tree's ephemeral defer.

#### Scenario: Command payload
- **WHEN** the plugin is loaded and the commands are translated
- **THEN** the guild payload holds `basic-calculate` with v3's names, descriptions and
  localizations, the corrected en-US `formula` description, no default member permissions, and
  `formula` required with a maximum length of 1018

#### Scenario: Command callback
- **WHEN** the registered command's callback runs with `1+1`
- **THEN** the response is deferred ephemerally, the answer is sent to the channel and the deferred
  response is deleted
