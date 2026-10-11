## 1. Staff-only control row

- [x] 1.1 xfail tests for "The control row locks and unlocks the ticket" (the ticket's member and
      other members refused, a row without its entry, a user who is no member), "Administrators
      delete the ticket" (any other member refused) and "v3's panels and tickets keep working" (a
      v3 row pressed by the ticket's member), against a stub `_refuse` that the new cases reach;
      the tests that press lock as staff store the panel's entry
- [x] 1.2 Check staff in lock and unlock, and answer every refusal of the four buttons through one
      check (`_staff`, `_refuse`); remove the markers

## 2. Labels

- [x] 2.1 xfail tests for "Texts follow the reader" (the owner's labels in both `text.yaml` files)
- [x] 2.2 Change the labels and the golden data, and point the row tests at the owner's labels;
      remove the markers

## 3. Checks and docs

- [x] 3.1 The wheel ships both `text.yaml` files with the new labels
- [x] 3.2 Porting guide rows
- [x] 3.3 Audit: every scenario of the delta has a test
- [x] 3.4 Push the work so far (CI green); cross-review (a subagent); record its findings and fix
      them xfail-first (3.5 to 3.7; design, "Cross-review")
- [x] 3.5 xfail tests for "The control row locks and unlocks the ticket" (@everyone among the staff
      roles, a staff role beside it), "Administrators delete the ticket" and "Administrators choose
      where to save the conversation" (@everyone), found in the review: discord.py lists @everyone
      among a member's roles, so an entry naming it made every member staff; against a guard stub
      in `_role_ids`. The delta names @everyone and keeps the lock requirement's "with the same
      fields"
- [x] 3.6 Leave @everyone out of a member's role IDs; remove the markers
- [x] 3.7 The review's notes: what v3's lock and unlock let members do, the design's checks, and the
      pitfall in the porting guide and `HANDOFF.md`

## 4. Close

- [x] 4.1 Gate passes, push, CI green
- [x] 4.2 Archive the change and run `openspec validate --all --strict`
- [x] 4.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
