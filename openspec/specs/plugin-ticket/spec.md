# plugin-ticket Specification

## Purpose
Administrators build ticket panels in an ephemeral builder, as a new message or as a button added
to one of the bot's messages; a member who presses a panel button gives a reason and gets a
private channel with the panel's staff roles, whose control row locks and unlocks the member, saves
the conversation into a thread of another channel and deletes the channel.

## Requirements

### Requirement: The plugin installs as Ticket
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Ticket`, pointing to `xincord.plugins.ticket`, with no dependencies, no intents and no
config. It SHALL bundle en-US and zh-TW lang files (`register.yaml`, seven message and seven
modal templates) with a `text.yaml` per locale, which its first load writes to
`plugins/Ticket/lang/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Ticket` enabled
- **THEN** it returns `Ticket` from `xincord.plugins.ticket` with no dependencies and no intents

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** the 32 lang files exist under `plugins/Ticket/lang/` and no `config.yaml` is written

### Requirement: Texts follow the reader
The plugin SHALL take its texts outside the templates from `text.yaml`: replies to one user
in that user's locale and public messages (the control row, the archive's markers) in the default
locale, zh-TW, a missing locale or key falling back to zh-TW. zh-TW SHALL hold Chinese texts, en-US
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

### Requirement: Panels are stored as documents
Each guild's panels SHALL be one document in the store's namespace `Ticket` under the guild ID:
the JSON `{"<message ID>": [{"reasonTitle", "adminIds", "categoryId"}, ...]}`, a button's index
in its message being its position in the list. Reads SHALL write nothing; a new button SHALL be
appended under the guild's lock, other entries kept as stored; an entry of another shape
SHALL raise for operations on it and never be overwritten.

#### Scenario: A stored document
- **WHEN** a guild's document is the example with two buttons on one message
- **THEN** the second button's entry reads with its reason title, staff role IDs and category ID,
  exact above 2^53

#### Scenario: Missing entries
- **WHEN** a panel's message, or the button's index, is not in the guild's document
- **THEN** the lookup finds nothing and nothing is written

#### Scenario: Appending keeps the others
- **WHEN** a button is added to a message that has one, in a document with an unknown field
- **THEN** the message's list has two entries, the new one in the stored field order, and the rest of the
  document is unchanged

#### Scenario: Broken entries
- **WHEN** an entry lacks `categoryId`, or its `adminIds` holds text or a boolean
- **THEN** reading it raises an error that names the guild and the message, and nothing is written

### Requirement: The commands are localized administrator guild commands
The plugin SHALL register the guild commands `create-ticket` (no options) and `add-ticket` with a
required string option `message_id`, with English base names and descriptions, the localizations of
`register.yaml` (`create_ticket.*`, `add_ticket.*`, `add_ticket.options.message_id.*`) and a default
permission of Administrator.

#### Scenario: Command payloads
- **WHEN** the plugin's guild commands are built
- **THEN** their payloads hold the names, descriptions, zh-TW and en-US localizations, the
  option and `default_member_permissions` 8

### Requirement: The create command opens the builder
`/create-ticket` SHALL replace the user's draft in the guild with a new one holding the defaults
from `text.yaml` in the user's locale (reason title, author, icon URL, title, description, button
text and emoji; color `0x00FFFF`, green button, no staff roles, the panel channel's category) and
edit the deferred response into the `create-ticket` builder.

#### Scenario: A new draft
- **WHEN** a zh-TW administrator runs `/create-ticket`
- **THEN** the response shows `create-ticket` with the preview of the defaults, and the draft is
  kept with the response's message ID

#### Scenario: A second command replaces the draft
- **WHEN** the administrator runs `/create-ticket` again
- **THEN** only the new builder message drives the new draft

### Requirement: The add command opens the builder for a message
`/add-ticket` SHALL fetch the message from the command's channel and edit the deferred response
into the `add-ticket` builder, the preview showing its first embed; it SHALL answer instead when
the ID is not a number (showing its first 100 characters), the message is not found, the bot did
not send it, its first action row holds five components or a select, or it has no embed.

#### Scenario: An added button's draft
- **WHEN** an administrator runs `/add-ticket` with the ID of the bot's panel, whose row has two
  buttons
- **THEN** the response shows `add-ticket` with the panel's embed, and the draft targets the
  message

#### Scenario: Refused messages
- **WHEN** the ID is `abc`, or names no message of the channel, another user's message, a message
  whose first row is full or holds a select, or one without an embed
- **THEN** the response is the matching error text and no draft is kept

#### Scenario: A long text
- **WHEN** the ID is a text of 6000 characters
- **THEN** the response is the invalid-ID text with the text's first 100 characters, within
  Discord's 2000

### Requirement: The preview shows the draft
The builder SHALL show a preview embed (the author with its icon, the title, the description and
the color, empty values left out; an added button's message's embed instead) and a preview button
with the draft's style, label and emoji, which opens the `preview-reason` modal titled with the
reason title; submitting that modal SHALL leave the draft.

#### Scenario: Preview of a draft
- **WHEN** the draft has the author `Shop`, no icon, the title `Help`, an empty description, the
  color `0x123456`, a red button labeled `Open` without emoji
- **THEN** the preview embed and button show exactly those values

#### Scenario: The preview button
- **WHEN** the administrator presses the preview button, then submits the modal
- **THEN** `preview-reason` opens with the reason title, and the builder shows the same draft

### Requirement: Only the latest builder of a draft works
Builder presses, selections and submissions SHALL act on the user's draft in the guild only when
they come from the builder message that shows it; otherwise the user SHALL get the session-expired
text ephemerally.

#### Scenario: No draft
- **WHEN** a user without a draft presses a builder button
- **THEN** the reply is the session-expired text

#### Scenario: An older builder
- **WHEN** the user presses a button of a builder message older than their newest
- **THEN** the reply is the session-expired text and the draft is unchanged

### Requirement: Builder buttons open pre-filled modals
`modify-author`, `modify-content`, `modify-color`, `modify-btn-text` and `modify-reason` SHALL open
the modals `modify-author`, `modify-content`, `modify-embed-color`, `modify-btn-text` and
`modify-reason-title` in the user's locale, pre-filled with the draft (the color as `#RRGGBB`, the
emoji as written) and the interaction's placeholder values.

#### Scenario: Pre-filled modals
- **WHEN** the administrator presses each of the five buttons on a draft
- **THEN** each modal opens with the draft's values in its inputs

### Requirement: Builder buttons switch screens
`modify-category`, `modify-admin` and `modify-btn-color` SHALL replace the builder with the
`modify-category`, `modify-admin-role` and `modify-btn-color` screens, and `back` with the main
screen, each through the press.

#### Scenario: Screens
- **WHEN** the administrator presses `modify-category`, then `back`
- **THEN** the builder shows the category select with the preview, then the main screen

### Requirement: Submitted modals change the draft
Submissions SHALL set the author and icon URL, the title and description, the reason title (an
empty one ignored), the color (`#RRGGBB`, `0xRRGGBB` or `RRGGBB` with one to six hex digits) and the
button's text and emoji (both empty refused), then show the main screen. A bad color SHALL be
refused with an error; a zh-TW `modify-btn-content` SHALL count as `modify-btn-text`.

#### Scenario: Values set
- **WHEN** the administrator submits the author `Shop` with an empty icon, the color `0x00ff00`,
  and the button text `Help` with the emoji `🎫`
- **THEN** the draft holds them and the builder shows the main screen

#### Scenario: Refused values
- **WHEN** the color is `green`, `#1234567` or empty, or the button text and emoji are both empty
- **THEN** the reply is the matching error and the draft is unchanged

#### Scenario: A zh-TW button modal of operators' files
- **WHEN** the submission comes from a zh-TW modal whose ID says `modify-btn-content`
- **THEN** the button's text and emoji change

### Requirement: Selections change the draft
The role select SHALL replace the staff roles; the category select SHALL set the category, or
answer the category-not-found error for a channel the guild does not know as a category; a color
button SHALL set the style 1 to 4 (blue, gray, green, red). Each SHALL show the main screen.

#### Scenario: Roles, category and style
- **WHEN** the administrator selects roles 3 and 4, the category 30 and the red button
- **THEN** the draft holds them and the builder shows the main screen

#### Scenario: Unknown category
- **WHEN** the selected category is not in the guild's cache
- **THEN** the reply is the category-not-found text and the draft is unchanged

### Requirement: A change that Discord refuses keeps the draft
When Discord refuses the builder that shows a changed draft, the draft SHALL stay as it was and the
user SHALL get the refused text with Discord's error ephemerally.

#### Scenario: Invalid emoji
- **WHEN** the button emoji is `abc` and Discord refuses the edit
- **THEN** the reply is the refused text with the error, and the draft keeps its emoji

### Requirement: Confirming posts a new panel
`confirm-create` on a new panel's builder SHALL take the draft before its first await, post the
`confirm-create` (the preview embed and the panel button, index 0) in the builder's channel, store
the button's entry as a new list under the posted message's ID and delete the builder.

#### Scenario: A posted panel
- **WHEN** the administrator confirms a draft with staff role 3 and category 30
- **THEN** the channel gets the panel, the store holds `[{"reasonTitle", "adminIds": [3],
  "categoryId": 30}]` under its ID, and the builder is deleted

### Requirement: Confirming adds a button to the message
`confirm-create` on an added button's builder SHALL, under the guild's lock, fetch the message
again, append the panel button to its first action row (a new row when it has none), keeping its
content, embeds and other rows, with the index of its stored list's length, store the entry at the
end of that list and delete the builder.

#### Scenario: A button added to a panel
- **WHEN** the administrator confirms an added button for a panel with one stored button and two
  rows
- **THEN** the panel's first row ends with the new button of index 1, the second row stays, and the
  stored list has two entries

### Requirement: A panel that cannot be posted keeps the builder
When the panel cannot be posted, edited or stored, or the message has since filled its row, the
draft SHALL come back, the builder SHALL stay and the user SHALL get the create-failed text with the
error ephemerally; a panel posted or a button added whose entry cannot be stored SHALL go again,
and a second confirmation while the first runs SHALL get the session-expired text.

#### Scenario: Refused post
- **WHEN** the channel refuses the panel
- **THEN** the reply is the create-failed text with the error, the builder stays and the draft is
  kept

#### Scenario: Unstored entry
- **WHEN** the store fails after the panel was posted, or after the button was added to the message
- **THEN** the panel is deleted, or the message gets its earlier buttons back, and the reply is the
  create-failed text with the error

#### Scenario: Double confirmation
- **WHEN** the administrator presses `confirm-create` twice while the panel is being posted
- **THEN** one panel is posted and the second press gets the session-expired text

### Requirement: Pressing a panel button asks for the reason
A panel button SHALL look its entry up by the pressed message (or the ID's message) and the
button's index, then open the `press-ticket` modal in the user's locale, its input labeled with the
reason title (at most 45 characters) and its ID naming the message and the index; without an entry
the user SHALL get the not-found text.

#### Scenario: The reason modal
- **WHEN** a member presses button 1 of a stored panel
- **THEN** `press-ticket` opens with the entry's reason title and an ID for that message and index

#### Scenario: No entry
- **WHEN** the panel or the button is not stored
- **THEN** the reply is the not-found text

### Requirement: Submitting the reason opens a ticket channel
A reason SHALL be deferred ephemerally, then the bot SHALL create a text channel named after the
member's username in the entry's category (category 0: the panel channel's), send the staff role
mentions, two line breaks and the reason (split at 2000 characters, the last part with the
unlocked control row, pinging those roles only) and reply with the go-to-channel text; a missing
entry or category SHALL get its error.

#### Scenario: A ticket
- **WHEN** member 8 (`bob`) submits `help me` for an entry with staff roles 3 and 4 and category 0
- **THEN** channel `bob` is created in the panel channel's category, its first message is
  `<@&3> <@&4> \n\nhelp me` with the control row, and the reply links it

#### Scenario: Missing entry or category
- **WHEN** the entry is gone, or the category is unknown or the panel channel has none
- **THEN** the reply is the not-found or category text and no channel is created

#### Scenario: A long reason
- **WHEN** the opener would exceed 2000 characters
- **THEN** it is sent in parts of at most 2000, the control row on the last

#### Scenario: Refused creation
- **WHEN** Discord refuses the channel, or its first message (the channel is then deleted)
- **THEN** the reply is the ticket-failed text with the error

### Requirement: Ticket channels get the category's permissions and the bot's
The channel's overwrites SHALL be the category's (when the bot holds every permission they set, or
Administrator), then @everyone denied View Channel, the member and each existing staff role allowed
it, and the bot allowed it on top of its own copied overwrite.

#### Scenario: Overwrites
- **WHEN** the category has an overwrite for role 5 and for @everyone, and the bot can set them
- **THEN** the channel keeps role 5's, @everyone is denied View Channel only, and the member,
  staff roles 3 and 4 and the bot are allowed it

#### Scenario: Overwrites the bot cannot copy
- **WHEN** a category overwrite sets a permission the bot lacks, and the bot is no administrator
- **THEN** none of the category's overwrites is copied

### Requirement: The control row locks and unlocks the ticket
Lock and unlock SHALL act only for the ticket's staff (a staff role of the row's entry but
@everyone, or Administrator): acknowledged before any request to Discord, they SHALL deny or allow
the ticket's member View Channel, other permissions kept, and show the other row (unlock: green
`🔓`; lock: gray `🔒`; save: blue `💾`; delete: red `🗑`) with the same fields. Failures SHALL be
told ephemerally; any other member SHALL get the admin-only text, a row without its entry the
not-found text.

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

#### Scenario: @everyone among the staff roles
- **WHEN** the entry's staff roles hold @everyone, whose ID is the guild's, and the ticket's
  member, holding no other staff role, presses lock or unlock
- **THEN** the reply is the admin-only text, ephemerally, and no overwrite or row changes

#### Scenario: A member who left
- **WHEN** the ticket's member left the guild
- **THEN** the reply is the lock-failed text with the error and the row is unchanged

### Requirement: Administrators delete the ticket
Delete SHALL look the entry up by the row's message and index: without one, the not-found text; for
a member with one of its staff roles but @everyone, or Administrator, an acknowledgement and the
channel's deletion (a refusal reported); for any other member, the ticket's member too, the
admin-only text, ephemerally, the channel kept.

#### Scenario: Deletion
- **WHEN** a member with staff role 3 presses delete
- **THEN** the press is acknowledged and the channel deleted

#### Scenario: Not a staff member
- **WHEN** the ticket's member, or another member without a staff role or Administrator, presses
  delete
- **THEN** the reply is the admin-only text, ephemerally, and the channel stays

### Requirement: Administrators choose where to save the conversation
Save SHALL answer the not-found or admin-only text, or ephemerally offer a text channel select.
The selection SHALL check, in this order, the member, the entry, staff, a text source channel, a
text target and the bot's permissions (View Channel and Read Message History in the source; View
Channel, Send Messages, Send Messages in Threads, Create Public Threads and Manage Webhooks in the
target), each failure answering its text.

#### Scenario: The select
- **WHEN** a staff member presses save
- **THEN** the reply holds the select for text channels with the row's fields

#### Scenario: Refused saves
- **WHEN** the presser is no staff member, or the bot lacks Manage Webhooks in the target
- **THEN** the reply is the admin-only or the permission text and nothing is archived

### Requirement: The archive copies the conversation into a thread
After the checks, the bot SHALL answer with a new ephemeral saving text, create a public thread
in the target named after the channel (cut to 80 UTF-16 units at a character boundary) and
`-yyyy-MM-dd_HH:mm:ss` in the host's zone, and a webhook named `ticket-save-content-<base36 ms>-<n>`,
send each message with text or attachments oldest first under its author's name and avatar,
pinging nobody, delete the webhook and edit the answer into the saved text.

#### Scenario: Forwarded messages
- **WHEN** the channel holds a text message, an embed-only message and a message with a file
- **THEN** the thread gets the text and the file under their authors' names, and the embed-only
  message is skipped

#### Scenario: Long messages and large files
- **WHEN** a message holds 4000 characters and a file larger than the guild's upload limit
- **THEN** it is sent in two parts, the file's URL in place of the file

#### Scenario: Names Discord refuses
- **WHEN** an author's display name contains `discord`
- **THEN** the message is sent under the author's username, or else the author's ID

### Requirement: Threads started in the ticket are flattened
A message that started a thread SHALL be followed, once per thread, by the start marker, the
thread's messages forwarded oldest first and the end marker with the last message's time (or the
no-message text); a failure in the thread SHALL send the error marker and the end marker without a
time and the archive SHALL go on.

#### Scenario: A started thread
- **WHEN** a message started a thread holding two messages
- **THEN** the archive holds the message, the start marker, both messages and the end marker with
  the second message's time

#### Scenario: A thread that fails
- **WHEN** reading the thread's history fails
- **THEN** the archive holds the error marker and the end marker with the no-message text, then
  the next messages

### Requirement: A failed archive is reported and cleans up
Any failure outside a thread SHALL stop the archive, delete the webhook (and the thread when the
webhook could not be made), and edit the answer into the save-failed text with the error, its
URLs cut to their origin and at most 200 characters.

#### Scenario: Refused send
- **WHEN** a message cannot be sent
- **THEN** the webhook is deleted, the thread keeps what was sent, and the answer is the
  save-failed text with the error

#### Scenario: No webhook
- **WHEN** the webhook cannot be created
- **THEN** the thread is deleted and the answer is the save-failed text

### Requirement: Legacy panels and tickets keep working
The routes SHALL take legacy IDs (`ticket@` with the legacy fields, the user ID in hex) for panel buttons,
reason modals, control rows and the save select, act as for new IDs, and leave the core to upgrade
the message.

#### Scenario: A legacy panel button
- **WHEN** a member presses `ticket@a:press;f:0` on a stored panel
- **THEN** the reason modal opens, and the core rewrites the panel's IDs in the new format

#### Scenario: A legacy control row
- **WHEN** a staff member presses `ticket@a:lock;d:<hex user ID>;e:<message ID>;f:0`
- **THEN** the member is locked out and the row shows new-format IDs

#### Scenario: A legacy control row pressed by the ticket's member
- **WHEN** the ticket's member presses the same button
- **THEN** the reply is the admin-only text, and the core still rewrites the row's IDs

### Requirement: Leaving a guild forgets its panels
When the bot leaves a guild, the plugin SHALL delete the guild's panels and its
drafts; when the bot is ready, or the plugin loads into a ready bot, it SHALL delete the panels of
guilds the bot is no longer in.

#### Scenario: Leaving
- **WHEN** the bot leaves guild 10
- **THEN** guild 10's document and drafts are gone and other guilds' stay

#### Scenario: Left while offline
- **WHEN** the bot becomes ready without guild 11, which has panels
- **THEN** guild 11's document is deleted
