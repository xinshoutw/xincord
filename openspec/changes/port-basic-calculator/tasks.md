## 1. Resources

- [x] 1.1 Bundle v3's en-US and zh-TW `register.yaml`, `message/basic-calculate.yaml` and
      `message/error.yaml`, with the corrected en-US `formula` description

## 2. Installation

- [ ] 2.1 xfail tests for "The plugin installs as BasicCalculator"
- [ ] 2.2 Add the package, its `setup` and the `BasicCalculator` entry point; remove the markers

## 3. Trimming

- [ ] 3.1 xfail tests for "Formulas are trimmed as in v3"
- [ ] 3.2 Implement `normalize`; remove the markers

## 4. Reading

- [ ] 4.1 xfail tests for "Formulas are read with v3's syntax"
- [ ] 4.2 Implement `to_postfix`; remove the markers

## 5. Results

- [ ] 5.1 xfail tests for "Results are exact and rounded as in v3"
- [ ] 5.2 Implement `evaluate_postfix`, the exact numbers and the size limits; remove the markers

## 6. Powers

- [ ] 6.1 xfail tests for "Powers take whole exponents"
- [ ] 6.2 Implement powers; remove the markers

## 7. Golden files

- [ ] 7.1 xfail tests for "The golden formulas give v3's answers", with copies of v3's golden files
      and the independent evaluator
- [ ] 7.2 Implement `calculate`; remove the markers

## 8. Answer

- [ ] 8.1 xfail tests for "The answer is posted in the channel", with a fake channel and the golden
      embeds
- [ ] 8.2 Implement the answer; remove the markers

## 9. Errors

- [ ] 9.1 xfail tests for "Errors are answered privately"
- [ ] 9.2 Implement the error reply; remove the markers

## 10. Command

- [ ] 10.1 xfail tests for "The command is a localized guild command"
- [ ] 10.2 Build the command from the lang files and register it in `setup`; remove the markers

## 11. Conventions and docs

- [ ] 11.1 Check that the built wheel ships `lang/` and that `xincord --no-online` loads the plugin
- [ ] 11.2 Porting guide rows and pitfalls, skill corrections, and the measured worst case in the
      design
- [ ] 11.3 Audit the inventory against the scenarios and the design

## 12. Close

- [ ] 12.1 Gate passes, push, CI green
- [ ] 12.2 Archive the change and run `openspec validate --all --strict`
- [ ] 12.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
