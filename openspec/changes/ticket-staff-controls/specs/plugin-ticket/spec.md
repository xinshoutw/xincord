## MODIFIED Requirements

### Requirement: Texts follow the reader
The plugin SHALL take the texts that v3 wrote in its code from `text.yaml`: replies to one user
in that user's locale and public messages (the control row, the archive's markers) in the default
locale, zh-TW, a missing locale or key falling back to zh-TW. zh-TW SHALL hold v3's texts, en-US
English ones, except the control row's labels (`control.*`), which SHALL be the owner's in both;
values SHALL be inserted as written.

#### Scenario: A reply in the user's locale
- **WHEN** a member whose client is en-US, zh-TW or ja presses a panel button whose data is gone
- **THEN** the not-found reply is the en-US, zh-TW or zh-TW text

#### Scenario: Public texts in the default locale
- **WHEN** an en-US member opens a ticket
- **THEN** the control row's labels are the zh-TW ones

#### Scenario: The control row's labels
- **WHEN** the plugin loads its bundled lang files
- **THEN** `control.lock`, `control.unlock`, `control.save` and `control.delete` are the owner's
  labels in zh-TW, and `Click to lock`, `Click to unlock`, `Save conversation` and `Delete` in
  en-US

### Requirement: The control row locks and unlocks the ticket
Lock and unlock SHALL act only for the ticket's staff (a staff role of the entry named by the
row's message and index, or Administrator): acknowledged before any request to Discord, they SHALL
deny or allow the ticket's member View Channel, other permissions kept, and show the other row
(unlock: green `🔓`; lock: gray `🔒`; save: blue `💾`; delete: red `🗑`). Failures SHALL be told
ephemerally; any other member SHALL get the admin-only text, a row without its entry the not-found
text.

#### Scenario: Lock and unlock
- **WHEN** a staff member presses lock, then unlock
- **THEN** the member's overwrite denies, then allows View Channel, and the row shows unlock, then
  lock

#### Scenario: Not the ticket's staff
- **WHEN** the ticket's member, or another member without a staff role or Administrator, presses
  lock or unlock
- **THEN** the reply is the admin-only text, ephemerally, and no overwrite or row changes

#### Scenario: No entry
- **WHEN** the row's panel button is not stored
- **THEN** the reply is the not-found text, ephemerally, and no overwrite or row changes

#### Scenario: A member who left
- **WHEN** the ticket's member left the guild
- **THEN** the reply is the lock-failed text with the error and the row is unchanged

### Requirement: Administrators delete the ticket
Delete SHALL look the entry up by the row's message and index: without one, the not-found text; for
a member with one of its staff roles or Administrator, an acknowledgement and the channel's
deletion (a refusal reported); for any other member, the ticket's member too, the admin-only text,
ephemerally, the channel kept.

#### Scenario: Deletion
- **WHEN** a member with staff role 3 presses delete
- **THEN** the press is acknowledged and the channel deleted

#### Scenario: Not a staff member
- **WHEN** the ticket's member, or another member without a staff role or Administrator, presses
  delete
- **THEN** the reply is the admin-only text, ephemerally, and the channel stays

### Requirement: v3's panels and tickets keep working
The routes SHALL take v3's IDs (`ticket@` with v3's fields, the user ID in hex) for panel buttons,
reason modals, control rows and the save select, act as for new IDs, and leave the core to upgrade
the message.

#### Scenario: v3's panel button
- **WHEN** a member presses `ticket@a:press;f:0` on a stored panel
- **THEN** the reason modal opens, and the core rewrites the panel's IDs in the new format

#### Scenario: v3's control row
- **WHEN** a staff member presses `ticket@a:lock;d:<hex user ID>;e:<message ID>;f:0`
- **THEN** the member is locked out and the row shows new-format IDs

#### Scenario: v3's control row pressed by the ticket's member
- **WHEN** the ticket's member presses the same button
- **THEN** the reply is the admin-only text, and the core still rewrites the row's IDs
