## Why

On 2026-10-11 the owner asked that the member who opened a ticket no longer be able to use the
ticket channel's control row, and for clearer labels on it. `port-ticket` kept v3's rules: lock and
unlock check nobody, so the ticket's member can lock themselves out, and any member who sees the
channel can lock or unlock it (`Ticket.kt:148-179`); delete answers anyone but staff with a silent
acknowledgement (`Ticket.kt:181-196`); only save refuses them with the admin-only text
(`Ticket.kt:198-242`). The labels are v3's Kotlin strings (`Ticket.kt:783-821`), whose words for
lock and unlock read as "close" and "open".

## What Changes

- Every control row button (lock, unlock, save and delete) acts for the ticket's staff only: a
  member with one of the staff roles of the panel button's entry, or Administrator, as save decides
  today (`ControlRow._staff_entry`, `tickets.is_staff`). Any other member, the ticket's member
  included, gets the existing `error.admin-only` text as an ephemeral reply, and nothing changes:
  no overwrite, no new row, no deletion.
- Lock and unlock look the entry up as save and delete do, so a row whose entry is gone answers the
  existing `error.not-found` text. They still acknowledge before any request to Discord (the
  member's fetch, the overwrite, the row's edit), reading only the store first, as save and delete
  do.
- Delete answers anyone but staff with `error.admin-only` instead of v3's silent acknowledgement.
  Save behaves as before.
- @everyone never counts as a staff role (found in the cross-review): discord.py lists it among
  every member's roles, where JDA's `getRoles` left it out, so an entry naming it made every member
  staff on save and delete.
- The control row's labels (`control.*` in `lang/zh-TW/text.yaml` and `lang/en-US/text.yaml`) are
  the owner's: `Click to lock`, `Click to unlock`, `Save conversation` and `Delete` in en-US, and
  the owner's zh-TW words. The row stays in the default locale (zh-TW) for everyone. Rows already
  posted show the new labels when they are rebuilt, at their next lock or unlock; exported lang
  files keep their text until they are renewed.

Kotlin sources (v3's rules and labels that change):
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:148-179` (lock and
  unlock, no check)
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:181-196` (delete, a
  silent acknowledgement for anyone but staff)
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:198-242` (save, the
  admin-only text)
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:783-821` (the row's
  labels)
- `XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-837` (who is staff)

Out of scope: the save select's checks (already staff-only, in v3's order); rights of the ticket's
member to close their own ticket; a confirmation before deletion; labels per reader (the row is a
public message); editing the rows already posted (decision B9: never mass re-send); a way for
staff to act on a row whose entry is gone; renewing operators' exported lang files; new wording
for `error.admin-only`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-ticket`: lock, unlock and delete are for the ticket's staff only, the control row's
  labels are the owner's, and v3's control rows follow the same rule (four requirements modified).

## Impact

`packages/xincord-plugins/src/xincord/plugins/ticket/`: `controls.py` (one check for the four
buttons, a member's roles without @everyone), `tickets.py` (a docstring) and both
`lang/*/text.yaml`; the Ticket tests and their golden data. No core change, no new dependency and
no stored data change. Operators see the new labels on rebuilt rows once their exported
`text.yaml` is renewed or edited.
