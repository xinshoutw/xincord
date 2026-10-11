## Context

The owner's request of 2026-10-11 has two parts: the member who opened a ticket must not use the
ticket channel's control row, whose four buttons become staff-only, and the row's labels become
clearer.

Today (`port-ticket`), the row's handlers live in `controls.ControlRow`, the cog's base:

- `lock` (lock and unlock) checks nobody, as v3 (`Ticket.kt:148-179`): it acknowledges at once
  (`response.defer()`), fetches the ticket's member, sets their overwrite and shows the other row.
- `delete` reads the entry of the row's panel button (`_staff_entry`): without one, the not-found
  text; for staff, an acknowledgement and the deletion; for anyone else, an acknowledgement only,
  as v3 (`Ticket.kt:181-196`).
- `save` answers a user who is no member with an acknowledgement (v3's `deferEdit`), a row without
  its entry with the not-found text, anyone but staff with the admin-only text, and staff with the
  channel select (`Ticket.kt:198-242`).
- `_staff_entry` decides who is staff: a member holding one of the entry's staff roles, or
  Administrator (`tickets.is_staff`, v3's `hasTicketAdminPermission`, `Ticket.kt:834-837`).
- The labels come from `text.yaml`'s `control.*` (zh-TW: v3's Kotlin strings, `Ticket.kt:783-821`;
  en-US: English texts added by the port) and are rendered in the default locale, zh-TW, for every
  reader: the row is a public message.

## Goals / Non-Goals

**Goals:** lock, unlock, save and delete act for the ticket's staff only; any other member, the
ticket's member included, gets the existing `error.admin-only` text ephemerally and nothing
changes; the existing not-found handling stays; no request to Discord before the acknowledgement;
the owner's labels in both `text.yaml` files.

**Non-Goals:** the save select's checks (unchanged: v3's order, staff-only already); rights of
the ticket's member to close their own ticket; a confirmation before deletion; per-reader labels;
editing rows already posted; a fallback for rows whose entry is gone; renewing operators' exported
lang files; new wording for `error.admin-only` (its en-US text names administrators, while staff
roles count too; the owner asked for the existing text).

## Decisions

### One check for the four buttons

`ControlRow._staff(interaction, fields)` returns the entry of the row's panel button when one of
its staff pressed; otherwise it answers the press through `_refuse(interaction, key)` and returns
None. It wraps `_staff_entry`, unchanged, so the order stays v3's (a member, the entry, staff):

- a user who is no member: an acknowledgement only (`response.defer()`, v3's `deferEdit`), as save
  and delete answer today. Discord sends the member with every interaction in a guild, and
  discord.py then gives a `Member`, so this happens only outside guilds, where no ticket channel
  is;
- a row without its entry: `error.not-found`, ephemerally (`tell`), as save and delete answer
  today;
- anyone but staff: `error.admin-only`, ephemerally, as save answers today.

`lock` calls it after `_controls`, so a row whose member is no user ID still gets no response from
anyone, as v3 threw before answering; `delete` and `save` call it first. The save select
(`select_target`) keeps its own checks, which answer a user who is no member with
`error.no-member`, in v3's order.

### The acknowledgement

Lock and unlock acknowledged first; they now read the store first (`Panels.entry`: one
`Store.get`, without the guild's lock that `/add-ticket`'s confirmation holds across Discord
requests), as save and delete always did. Every request to Discord (the member's fetch, the
overwrite, the row's edit, the channel's deletion) still comes after `response.defer()`, so the
press is answered within Discord's three seconds whatever Discord takes. A refusal is the
interaction's response itself (`response.send_message(..., ephemeral=True)`), which no
acknowledgement may precede.

### Labels

`control.*` in both `text.yaml` files becomes the owner's: lock `Click to lock`, unlock `Click to
unlock`, save `Save conversation` and delete `Delete` in en-US, and the owner's zh-TW words. The
row stays in the default locale (zh-TW) for everyone, so the en-US labels show nowhere today; both
locales keep every key, as the core expects.

Rows already posted are not edited (decision B9: never mass re-send): a row shows the new labels
when it is rebuilt, which only lock and unlock do (`views.control_row` with the public texts).
Save and delete leave the row as it is, and the core's upgrade of v3's IDs keeps the labels of
the message it rebuilds.

`PluginContext.lang` exports the bundled lang files only where they are missing: a
`plugins/Ticket/lang/<locale>/text.yaml` written by an earlier start keeps its labels until
`--force-renew-lang-resources` (`-Flang`) overwrites every enabled plugin's exported lang files
with the bundled ones, operators' edits included, or until the operator edits the four
`control.*` lines.

### Tests (xfail-first)

The new cases are routed to a stub `_refuse` that raises `NotImplementedError`: every refusal of
lock and unlock, and delete's refusal of anyone but staff. The tests that press lock as staff
store the panel's entry first, which changes nothing before the gate exists. A press of a v3 row
by the ticket's member goes through `bot.on_interaction`, whose core logs the stub's error, so
that test fails on its assertions (no `raises`), as do the label tests, which read the lang files.
The implementation commit adds `_staff`, implements `_refuse` and moves `delete` and `save` to the
check. The label commit changes both `text.yaml` files and the golden data: v3's labels leave the
`v3-texts` section, and a `labels` section holds the owner's, which the row tests read.

## v3 behaved differently

- v3 behaved differently: lock and unlock had no permission check (`Ticket.kt:148-179`), so the
  ticket's member could lock themselves out or unlock a ticket that its staff had locked; they act
  for staff only and answer anyone else with the admin-only text (the owner's request).
- v3 behaved differently: delete by anyone but staff was acknowledged and did nothing
  (`Ticket.kt:181-196`); it answers the admin-only text (the owner's request).
- v3 behaved differently: the row's labels were v3's Kotlin strings (`Ticket.kt:783-821`), whose
  words for lock and unlock read as "close" and "open"; they are the owner's.

## User-visible changes

- The ticket's member, or any member without a staff role or Administrator, who presses lock,
  unlock or delete gets the admin-only text ephemerally (in their language) and nothing changes.
  Before, lock and unlock worked for anyone and delete did nothing silently. Save is unchanged.
- Lock and unlock on a row whose panel button's entry is gone answer the not-found text, as save
  and delete did; before, they worked without it.
- New labels: lock `Click to lock`, unlock `Click to unlock`, save `Save conversation`, delete
  `Delete` (en-US) and the owner's zh-TW words, which every reader sees since the row is zh-TW.
- Rows already posted keep their labels until their next lock or unlock. Exported lang files keep
  the old labels until renewed with `--force-renew-lang-resources` or edited.

## Choices made without the owner

- A user who is no member keeps the silent acknowledgement on all four buttons (impossible in a
  guild channel); alternative: the admin-only text.
- Lock and unlock need the panel's entry, as save and delete: a ticket whose entry is gone (its
  guild's panels deleted when the bot left, or a v3 ticket before the v3 data import) can no longer
  be locked or unlocked from its row; staff change or delete such a channel by hand; alternative:
  let Administrators act without the entry.
- A row whose member is no user ID still gets no response from anyone, checked before staff, as v3
  threw; alternative: answer non-staff first.

## Risks / Trade-offs

- Lock and unlock depend on the store: a broken stored entry (`DataError`) or a failing store now
  fails them as it fails save and delete (the core logs it, and the press shows Discord's
  "interaction failed").
- Until the v3 data import stores v3's panels, the rows of v3's ticket channels answer the
  not-found text to lock and unlock too. The import comes before cutover.
- A staff member whose role is removed loses the row at their next press, as for save and delete.
- Lock and unlock pressed together still race as before: the last overwrite and row win.

## Manual smoke checklist

Needs a token, a test guild, a second account, a staff role and a panel posted with that role.

1. From the second account, open a ticket. Press lock, save and delete: each answers the
   admin-only text ephemerally, in the account's language; the channel, its permissions and the
   row stay.
2. As a member with the staff role (no Administrator), press lock, then unlock: the second account
   loses and regains the channel, and the row reads the new labels. Save offers the select; delete
   deletes the channel.
3. As an Administrator without the staff role: the same.
4. A row posted before the change keeps its labels until its next lock or unlock.
5. With a `plugins/Ticket/lang/zh-TW/text.yaml` from an earlier start, the labels stay the old ones
   until `--force-renew-lang-resources` or an edit of its `control.*` lines.

## Checks (2026-10-11)

- The `xincord-plugins` wheel (`uv build --package xincord-plugins`) holds both `text.yaml` files
  with the owner's labels under `control.*`.
- No new probe: a refusal is `response.send_message(..., ephemeral=True)` and a staff press
  `response.defer()` then `edit_original_response(view=...)`, the calls that `port-ticket`'s probe
  recorded through discord.py's own objects for save's admin-only reply and for lock (archived
  design, "Checks"); the tests drive the four buttons through the plugin's route handler and v3's
  rows through `bot.on_interaction`.

## Scenario audit

| Requirement | Scenario | Tests |
|---|---|---|
| Texts follow the reader | A reply in the user's locale | `test_texts.py::test_replies_in_the_users_locale` |
| Texts follow the reader | Public texts in the default locale | `test_texts.py::test_public_texts_in_the_default_locale`, `test_ticket.py::test_public_texts_in_the_default_locale` |
| Texts follow the reader | The control row's labels | `test_texts.py::test_control_row_labels`, `test_lock.py::test_lock_and_unlock` |
| The control row locks and unlocks the ticket | Lock and unlock | `test_lock.py::test_lock_and_unlock`, `test_staff_role`, `test_cached_member` |
| The control row locks and unlocks the ticket | Not the ticket's staff | `test_lock.py::test_not_the_tickets_staff` |
| The control row locks and unlocks the ticket | No entry | `test_lock.py::test_no_entry` |
| The control row locks and unlocks the ticket | A member who left | `test_lock.py::test_member_who_left` |
| Administrators delete the ticket | Deletion | `test_delete.py::test_deletion` |
| Administrators delete the ticket | Not a staff member | `test_delete.py::test_not_a_staff_member` |
| v3's panels and tickets keep working | v3's panel button | `test_routes.py::test_v3_panel_button` |
| v3's panels and tickets keep working | v3's control row | `test_routes.py::test_v3_control_row` |
| v3's panels and tickets keep working | v3's control row pressed by the ticket's member | `test_routes.py::test_v3_control_row_refused` |
