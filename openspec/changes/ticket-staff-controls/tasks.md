## 1. Staff-only control row

- [ ] 1.1 xfail tests for "The control row locks and unlocks the ticket" (the ticket's member and
      other members refused, a row without its entry, a user who is no member), "Administrators
      delete the ticket" (any other member refused) and "v3's panels and tickets keep working" (a
      v3 row pressed by the ticket's member), against a stub `_refuse` that the new cases reach;
      the tests that press lock as staff store the panel's entry
- [ ] 1.2 Check staff in lock and unlock, and answer every refusal of the four buttons through one
      check (`_staff`, `_refuse`); remove the markers

## 2. Labels

- [ ] 2.1 xfail tests for "Texts follow the reader" (the owner's labels in both `text.yaml` files)
- [ ] 2.2 Change the labels and the golden data, and point the row tests at the owner's labels;
      remove the markers

## 3. Checks and docs

- [ ] 3.1 The wheel ships both `text.yaml` files with the new labels
- [ ] 3.2 Porting guide rows
- [ ] 3.3 Audit: every scenario of the delta has a test
- [ ] 3.4 Push the work so far (CI green); cross-review (a subagent); record its findings and fix
      them xfail-first

## 4. Close

- [ ] 4.1 Gate passes, push, CI green
- [ ] 4.2 Archive the change and run `openspec validate --all --strict`
- [ ] 4.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
