## Context

v3's BasicCalculator (`Plugins/BasicCalculator`, 5 Kotlin files, 326 lines) registers one guild
command, `/basic-calculate formula` (`Register.kt:18-27`), when its config's `enabled` is true
(`Event.kt:49-55`). The core has already deferred the reply ephemerally. `BasicCalculator.kt:27-61`
trims the formula, evaluates it with a shunting-yard parser and `BigDecimal`
(`BasicCalculator.kt:68-206`), then either posts the `basic-calculate` embed to the channel and
deletes the deferred response, or, on an `IllegalArgumentException`, edits the deferred response
into the `error` embed. The inventory is `docs/porting/analysis/inventory/BasicCalculator.md`; its
fixtures hold 3155 formulas with v3's answers, recorded by running v3's evaluator.

## Goals / Non-Goals

**Goals:** v3's formula language, results and messages for every formula v3 answered correctly;
the defects in the inventory's section 12 fixed; golden tests that show both.

**Non-Goals:** new syntax (functions, constants, exponent notation, unary `+`, `%`, `×`, `÷`);
fractional exponents; localized error messages; rate limiting.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/basic_calculator/`: `__init__.py` (metadata and
  `setup`), `calculator.py` (the pure evaluator, no discord.py), `cog.py` (the command and its
  replies) and `lang/`. Entry point `BasicCalculator = "xincord.plugins.basic_calculator"`.
- No `config.yaml` and no `Config` model: v3's only key was `enabled`, which the core's `plugins`
  list replaces (port-plugin skill). A v3 `plugins/BasicCalculator/config.yaml` is left alone and
  never read.
- `DEFAULT_LOCALE = "zh-TW"`, as v3 hard-coded (`Event.kt:27`, `BasicCalculator.kt:17`). No
  intents, no dependencies, no component IDs (v3 had no components).
- `lang/<locale>/register.yaml`, `message/basic-calculate.yaml` and `message/error.yaml` are v3's,
  with final newlines added. The en-US `formula` description is corrected (see below). The embed
  image (`https://blog.xinshou.tw/favicon.ico`) and the footer stay: they are v3's branding in
  operator-editable templates, not IDs or secrets.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --all-packages` lists the six lang files and the `BasicCalculator` entry point, and
  `xincord --no-online`, run from a scratch virtual environment with both wheels and
  `plugins: [BasicCalculator]`, loads the plugin, writes `plugins/BasicCalculator/lang/` without a
  `config.yaml`, and exits with 0.

### Evaluator (`calculator.py`)

The pipeline keeps v3's structure so that v3's messages keep their order: `normalize(raw)` (trim),
`to_postfix(formula)` (the shunting-yard pass with v3's reading errors) and
`evaluate_postfix(tokens)` (the stack machine with v3's evaluation errors); `calculate(formula)`
chains the last two. Errors are `CalcError(message)` with v3's English texts.

- **Trimming.** Kotlin's `trim()` strips `Char.isWhitespace()` characters, which are Python's
  `str.isspace()` ones except U+0085; then `trimEnd('?', '=', ' ')` is `rstrip("?= ")`.
- **Reading.** As v3: whitespace is skipped but ends a number; a number is a run of
  `str.isdecimal()` characters and `.` (Kotlin's `Char.isDigit()` is Unicode `Nd` too); an implicit
  `*` goes between a number or `)` and a number or `(`; `+ -` rank 1 and `* /` rank 2, left
  associative; a stray `)` fails at once with `Unmatched bracket`, a leftover `(` at the end; any
  other character fails with `Unknown character: <c>`. Fixed: a minus at the start or after an
  operator or `(` pushes a prefix negation (`neg`, rank 3) instead of v3's `0` and binary minus,
  and `^` (rank 4) is right associative. Python reads code points where Kotlin read UTF-16 units,
  which only changes messages about characters outside the BMP.
- **Numbers.** Values are `BigDecimal(unscaled, scale)`, an exact model of Java's `BigDecimal`:
  `+ -` align scales, `*` adds them, `/` rounds the exact quotient half up to scale 10
  (`divide(b, 10, HALF_UP)`), `^` raises the unscaled value and multiplies the scale. Python's
  `decimal` would need a context to avoid its 28-digit default, and `Fraction` normalizes with a gcd
  that costs 75 to 180 ms per operation at 100,000 digits; scaled integers cost at most a few
  milliseconds there. A token is a number when it matches `[0-9]+\.?[0-9]*|\.[0-9]+` (Kotlin's
  `toBigDecimalOrNull()` takes ASCII digits only), else `Unknown Token: <token>`.
- **Result.** `setScale(5, HALF_UP).stripTrailingZeros().toPlainString()`: round half up (away
  from zero) to 5 places, drop trailing zeros, never an exponent, and zero is `0`, never `-0`.
- **Powers.** The exponent must be a whole number (`2^2.0` is 4), else `Exponent must be an
  integer`; a negative exponent divides 1 by the positive power with the division's rounding, so
  `a^-n` is `1/a^n`; `0^0` is 1, as in v3.
- **Size limits.** A value may keep at most 50,000 digits (`DIGITS_MAX`) in its unscaled value and
  at most 50,000 decimal places; each operation's result is checked, and a power is checked before
  it is computed from the exponent and the base's size, so `10^999999999` fails at once with `Too
  many digits`. The limit admits `(1+1/1000)^1000`, whose exact value needs 10,001 digits. A result
  over 1018 characters (`RESULT_MAX`) also fails with `Too many digits`; besides fitting the embed,
  this keeps `str()` under Python's 4,300-digit conversion limit. Formulas over 1018 characters
  (`FORMULA_MAX`) fail with `Formula too long` before reading, which also keeps every number token
  under that limit.
- **New messages:** `Division by zero`, `Exponent must be an integer`, `Too many digits`,
  `Formula too long`, in English like v3's four.

### Command and replies (`cog.py`)

- `BasicCalculator.command()` builds `basic-calculate` from the Lang (`basic-calculate.name`,
  `.description`, `.options.formula.name`, `.options.formula.description`) with the cog's
  `basic_calculate` method as the callback, then `rename` and `describe`. Base names are v3's
  `Commands.slash("basic-calculate", "calculate + - * / ^ ( ) math problem")` and
  `OptionData(STRING, "formula", "What's problem?", true)`. `formula` is
  `app_commands.Range[str, None, FORMULA_MAX]`: 1018 is Discord's 1024-character field value minus
  the six backticks the templates put around `%bc_question%`. A guild command; it keeps the tree's
  ephemeral defer, so the replies edit or delete the deferred response.
- Values are v3's `Placeholder.get(member)`, `actor_values(interaction.user, bot)`, plus
  `bc_question` (the trimmed formula) and, on success, `bc_answer` and `bc_answer_round`, or, on an
  error, `bc_error`. Templates are loaded once in `setup`; the user's locale falls back to zh-TW.
- **Success:** the `basic-calculate` message goes to `interaction.channel` and the deferred
  response is deleted, as v3's `sendMessage(...).flatMap { deleteOriginal() }`. When the channel has
  no `send` (a forum or a category) or sending raises `discord.HTTPException` (missing permissions,
  for example), the plugin logs it and edits the deferred response into the same message instead.
- **Error:** the `error` message replaces the deferred ephemeral response
  (`hook.editOriginal`).
- The calculation runs in a worker thread (`asyncio.to_thread`), so that a long one never holds up
  the gateway; v3 calculated on JDA's event thread. The size limits bound it (see Risks).

### Golden tests

`tests/fixtures/plugins/basic_calculator/` holds copies of v3's `BasicCalculator-golden.jsonl`
(3000 random formulas) and `BasicCalculator-edge-cases.jsonl` (155 picked ones), and `golden.yaml`
with v3's text per locale (command localizations and embeds). Every golden record must trim to
v3's formula; its answer must be v3's result, or v3's message for an `IllegalArgumentException`,
unless one of the fixed defects applies: a minus after an operator, a `^`, or v3's
`ArithmeticException` (no reply in v3). Those records must agree with an independent evaluator in
the test: it rewrites the formula into Python syntax (numbers become names, implicit `*` is
written out, `^` becomes `**`), parses it with `ast.parse` and walks the tree with `Fraction`
arithmetic; it never executes anything. Python's grammar gives the fixed precedence (`-2**2` is
`-(2**2)`, `2**-1` is `2**(-1)`, `**` groups from the right). The same evaluator agrees with v3 on
every unchanged record it can read, which checks it in turn. Prototyping this port showed 2614
unchanged records, 281 changed by the minus fix, 253 v3 arithmetic exceptions (most of them
divisions by v3's synthetic `0`) and 7 powers.

### v3 behaved differently

- v3 behaved differently: a minus after an operator became a binary minus with a synthetic `0`, so
  `2*-3` was `-3`, `2--3` was `-1`, `2^-1` was `0` and `1/-2` divided by zero; it now negates.
- v3 behaved differently: `^` grouped from the left (`2^3^2` was 64); it now groups from the right
  (512).
- v3 behaved differently: `^` truncated its exponent to a 32-bit integer, so `2^0.5` was 1 and
  `2^4294967297` was 2; fractional exponents now fail with `Exponent must be an integer` and huge
  ones with `Too many digits`.
- v3 behaved differently: division by zero and negative or huge exponents threw an uncaught
  `ArithmeticException`, leaving "thinking..." until the token expired; they now get an error
  embed, and negative exponents are computed (`2^-1` is 0.5).
- v3 behaved differently: no size limits; `10^999999999` could stall the gateway thread, and a
  formula or result over 1018 characters broke the embed without a reply; formulas are now capped
  at 1018 characters and oversized numbers fail with `Too many digits`.
- v3 behaved differently: the error embed expanded `%...%` in the formula recursively
  (`%bot_name%` showed the bot's name, `%bc_question%` failed without a reply); the formula is now
  shown as typed.
- v3 behaved differently: the `bc_` keys were put into the member's cached substitutor (or the
  global one) and stayed there; each render now uses its own values.
- v3 behaved differently: `%bc_answer_round%` was the whole answer (`split('.', limit = 1)`); it is
  now the part before the decimal point, without `-0`.
- v3 behaved differently: when posting to the channel failed, the user kept "thinking..."; the
  answer now replaces the deferred response.
- v3 behaved differently: the en-US `formula` description said "bracket is ignorable"; it now says
  that the multiplication sign can be omitted, as the zh-TW text does.
- v3 behaved differently: the reply needed the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree always defers this command.
- v3 behaved differently: an unknown character outside the BMP was reported as half of a UTF-16
  surrogate pair; the message now shows the whole character.

Kept on purpose: non-ASCII digits (`３`, `١٢`) are read as part of a number and then refused with
`Unknown Token`, as v3 did (the inventory's item 10); both readings refuse the formula and the
message names the token. Users whose locale has no lang directory get the zh-TW embeds, as in v3
and _Example.

## Risks / Trade-offs

- The fixes change answers that v3 users may remember (`2*-3`, `2^3^2`); the owner reviews them in
  `docs/porting/owner-review.md`.
- The 50,000-digit limit refuses some formulas v3 answered slowly, such as `(1+1/10000)^10000`
  (100,000 digits in v3's representation).
- English error messages in zh-TW embeds, as in v3.

## Manual smoke checklist

On a test guild, with a bot token and `plugins: [BasicCalculator]` in `config.yaml`:

1. Start the bot: the log lists `BasicCalculator` as loaded; `plugins/BasicCalculator/lang/`
   exists and no `plugins/BasicCalculator/config.yaml` is written.
2. The command appears as `/calculate` (en-US client) and `/告訴我` (zh-TW client) with the
   localized descriptions; `formula` refuses more than 1018 characters.
3. `formula: 1+1=?`: the "thinking" message disappears and the channel gets a public cyan
   `🔢 Calculator` embed with `1+1`, `2`, the favicon image and the footer.
4. `2*-3` gives `-6`, `2^3^2` gives `512`, `1/3` gives `0.33333`, `2^-1` gives `0.5`.
5. `1/0`, `abc` and `%bot_name%`: an ephemeral red embed with `Division by zero`, `Unknown
   character: a` and `Unknown character: %`, the formula shown as typed.
6. `10^999999999` answers `Too many digits` at once, and the bot keeps answering other commands.
7. In a channel where the bot lacks Send Messages, the answer arrives as the ephemeral response.
8. In a thread, the answer is posted in the thread.

## User-visible changes

New copy: the en-US `formula` description in `lang/en-US/register.yaml`, and the error messages
`Division by zero`, `Exponent must be an integer`, `Too many digits` and `Formula too long`
(English in every locale, as v3's).

1. `2*-3`, `2--3`, `2^-1`, `1/-2` and similar formulas give the mathematical answer (v3: `-3`,
   `-1`, `0`, no reply).
2. `2^3^2` is 512 (v3: 64).
3. Fractional exponents fail with `Exponent must be an integer` (v3: truncated, `2^0.5` was 1).
4. Division by zero, negative and huge exponents get an answer (v3: no reply).
5. `formula` accepts at most 1018 characters; oversized numbers fail with `Too many digits`.
6. `%...%` in a failing formula is shown as typed.
7. The en-US `formula` description says that the multiplication sign can be omitted.
8. When the bot cannot post in the channel, the answer arrives privately (v3: "thinking..."
   forever).
