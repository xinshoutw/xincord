# Spec Delta

## Purpose

Guild messages are stored for a while, and the edits and deletions of stored messages are posted to
the listen channels whose settings detect the message's channel; administrators set each listen
channel up through an ephemeral menu.

## ADDED Requirements

### Requirement: The plugin installs as ChatLogger
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `ChatLogger`, pointing to `xincord.plugins.chat_logger`, with no dependencies and the
guild messages and message content intents. It SHALL bundle v3's en-US and zh-TW lang files and a
`config.yaml`, which its first load writes to `plugins/ChatLogger/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `ChatLogger` enabled
- **THEN** it returns `ChatLogger` from `xincord.plugins.chat_logger` with no dependencies and the
  guild messages and message content intents, and the bot requests both

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `config.yaml` and the en-US and zh-TW `register.yaml`, `placeholder.yaml` and six message
  templates of each exist under `plugins/ChatLogger/`

### Requirement: The config keeps v3's key and bounds the stored messages
`config.yaml` SHALL hold v3's `log_all`, true by default, and `retention_days`, the number of days a
message's text is kept, 30 by default and from 1 to 3650. v3's files SHALL load, their `enabled` key
only warning; any other value SHALL stop the plugin from loading, with the key named.

#### Scenario: v3's file
- **WHEN** `plugins/ChatLogger/config.yaml` is v3's, with `enabled: false` and `log_all: false`
- **THEN** the plugin loads with `log_all` false and 30 days, and a warning names `enabled`

#### Scenario: Invalid retention
- **WHEN** `retention_days` is 0, 3651 or a text
- **THEN** the plugin does not load and the error names `retention_days`

### Requirement: Listen channels detect message channels
A listen channel's settings SHALL detect a channel, in the allow mode, when the channel, its
category, or for a thread its parent channel or that channel's category is in the allow list, and,
in the block mode, unless one of them is in the block list. An event SHALL go to every listen
channel of the guild that detects the message's channel.

#### Scenario: Allow mode
- **WHEN** the allow list holds channel 30 and category 20
- **THEN** channel 30, channel 31 of category 20 and their threads are detected, and channel 32 of
  category 21, its thread 42 and channel 33 without a category are not

#### Scenario: Block mode
- **WHEN** the block list holds channel 30 and category 20
- **THEN** channel 30, channel 31 and their threads are not detected, and channels 32 and 33 and
  thread 42 are

#### Scenario: A thread on its own
- **WHEN** the allow list holds thread 42 only
- **THEN** thread 42 is detected and its channel 32 is not

### Requirement: The settings menu shows the channel's settings
`/chat-logger setting` SHALL edit the deferred response into v3's `chat-logger@setting` template
for the current channel, in the user's locale, with v3's values of the interaction,
`cl_channel_mode` (`ALLOW` or `BLOCK`) and each list in the locale's line format, or `empty` when it
has none. A list longer than 1024 characters SHALL end with `...` after the lines that fit. Nothing
SHALL be written.

#### Scenario: Menu
- **WHEN** an administrator with an en-US or a zh-TW client runs the command in channel 5, whose
  settings are the block mode, the allow list `[30]` and an empty block list
- **THEN** the response is v3's settings embed in that locale with `<BLOCK>`, the line of channel 30
  and the `empty` text, and v3's four buttons

#### Scenario: Channel without settings
- **WHEN** the command runs in a channel without settings
- **THEN** the menu shows `<ALLOW>` and `empty` for both lists, and nothing is written

#### Scenario: Long list
- **WHEN** the allow list holds 40 channels with 19-digit IDs
- **THEN** the field holds at most 1024 characters, made of whole lines and `...`

### Requirement: The settings components change the settings
The menu's buttons and select menus SHALL reach the plugin, in v3's `chat-logger@` format too:
`toggle_btn` flips the mode; `modify_allow_btn` and `modify_block_btn` show the list's select menu,
whose choice adds the channels to the list; these show the updated menu, and `delete_btn` deletes
the channel's settings and shows `delete`. Settings SHALL be kept under `ChatLogger` as v3's
documents. Other actions SHALL get no response.

#### Scenario: Toggle
- **WHEN** an administrator presses the toggle button of channel 5's menu
- **THEN** the stored mode flips and the message becomes the menu with `<BLOCK>`

#### Scenario: Modify a list
- **WHEN** an administrator with an en-US or a zh-TW client presses the allow list button, then
  chooses channel 30 and category 20 in the select menu
- **THEN** the message becomes v3's select menu alone, for v3's ten channel types, 1 to 25 of them,
  and then the menu listing 30 and 20, stored as `{"5": {"allow_mode": true, "allow": [30, 20],
  "block": []}}` under `ChatLogger` and the guild's ID

#### Scenario: Delete
- **WHEN** an administrator presses the delete button of channel 5's menu while channel 6 has
  settings too
- **THEN** channel 5's settings are deleted, channel 6's stay, and the message becomes v3's `delete`
  embed without components

#### Scenario: v3 IDs
- **WHEN** a button with v3's ID `chat-logger@a:toggle_btn` is pressed
- **THEN** it toggles the mode as the new ID `chat_logger:1:a=toggle_btn` does

#### Scenario: Other actions
- **WHEN** a button has an unknown action, or a button carries a select menu's action
- **THEN** there is no response and nothing is written

### Requirement: The command is a localized administrator guild command
The plugin SHALL register v3's guild command `chat-logger` with the subcommand `setting`, without
options, with v3's names, descriptions and en-US and zh-TW localizations, visible to administrators
by default. The tree SHALL defer it ephemerally.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** the command has v3's texts, localizations and subcommand, and the default member
  permissions are Administrator

#### Scenario: Command callback
- **WHEN** the `setting` subcommand is looked up
- **THEN** its callback is the cog's menu handler, bound to the cog

### Requirement: Guild messages are stored
The plugin SHALL store each guild message that the bot did not send, other bots' and webhooks'
included, with its guild, channel, author, the text it was sent with and a change count of 0: from
every channel when `log_all` is true, and only from detected channels when it is false. Direct
messages SHALL not be stored. A message's edits and deletions SHALL reach the store after it, also
when they arrive together with it.

#### Scenario: Stored message
- **WHEN** member 7 sends `hello` in channel 30 of guild 10
- **THEN** the message is stored with guild 10, channel 30, author 7, the text `hello` and 0 changes

#### Scenario: The bot's own message
- **WHEN** the bot sends a message in channel 30
- **THEN** nothing is stored

#### Scenario: Only detected channels
- **WHEN** `log_all` is false and listen channel 5 detects channel 30 only
- **THEN** a message in channel 30 is stored and one in channel 32 is not

#### Scenario: Direct message
- **WHEN** a user sends the bot a direct message
- **THEN** nothing is stored

### Requirement: A message's text is its content and its rich embeds
The stored text SHALL be the message's content, then, for a bot's or a webhook's message, each rich
embed's author name and title on consecutive lines, its description and each field's name and value
on two lines, the parts separated by blank lines and the missing ones left out. Other embeds, such
as link previews, and every embed of a member's message, which can only be a preview, SHALL be left
out.

#### Scenario: Plain message
- **WHEN** a message has the content `hello` and no embed
- **THEN** its text is `hello`

#### Scenario: Content and embeds
- **WHEN** a message has the content `see` and a rich embed with the author `A`, the title `T`, the
  description `D` and the field `n` = `v`
- **THEN** its text is `see`, a blank line, `A` and `T` on two lines, a blank line, `D`, a blank
  line, and `n` and `v` on two lines

#### Scenario: Missing parts
- **WHEN** a rich embed has a field only, and no content
- **THEN** the text is the field's name and value, without `null`

#### Scenario: Link preview
- **WHEN** a message has the content `https://example.com` and a link preview embed
- **THEN** its text is `https://example.com`

#### Scenario: Rich preview of a member's link
- **WHEN** Discord adds a rich embed to a member's message `https://x.example/status/1`
- **THEN** the text stays the link, and no edit is logged

### Requirement: Edits of stored messages are logged
When a stored message's text changes, the plugin SHALL store the new text, count the change and
post `on-msg-update` to the detecting listen channels with the author's values,
`cl_msg_after_url`, `cl_channel_mention`, `cl_category_mention` (`-` without a category),
`cl_change_count`, `cl_msg_before` and `cl_msg_after`. An update that keeps the text, or of a
message that is not stored, SHALL change and post nothing.

#### Scenario: Edit
- **WHEN** member 7 edits the stored `hello` in channel 30 of category 20 into `hi`, in an en-US or
  a zh-TW guild where listen channel 5 detects channel 30
- **THEN** listen channel 5 gets v3's update embed in that locale with the member, the category, the
  channel, 1 change, `hello` before, `hi` after and the message's URL

#### Scenario: Second edit
- **WHEN** the message is edited again into `hey`
- **THEN** the embed shows 2 changes, `hi` before and `hey` after

#### Scenario: Same text
- **WHEN** an update keeps the text, such as a pin or a link preview
- **THEN** nothing is posted and the count stays

#### Scenario: Not stored
- **WHEN** a message that is not stored is edited
- **THEN** nothing is stored or posted

#### Scenario: Not detected
- **WHEN** no listen channel detects the channel
- **THEN** the new text and the count are stored and nothing is posted

#### Scenario: Thread
- **WHEN** a stored message in thread 41 of channel 30 is edited
- **THEN** the embed shows thread 41 as the channel and category 20

#### Scenario: Channel without a category
- **WHEN** a stored message in channel 33, which has no category, is edited
- **THEN** the embed shows `-` as the category

#### Scenario: Webhook
- **WHEN** a webhook's stored message is edited
- **THEN** the embed shows the webhook's mention and no thumbnail

#### Scenario: Edited at once
- **WHEN** a message `Loading...` and its edit into `result` reach the plugin together, before it
  handled the message
- **THEN** the edit is logged with 1 change, `Loading...` before and `result` after

### Requirement: Deletions of stored messages are logged
When a stored message is deleted, alone or in a bulk deletion, the plugin SHALL remove it from the
store and post `on-msg-delete` to the detecting listen channels with the author's values,
`cl_channel_mention`, `cl_category_mention` (`-` without a category), `cl_change_count` and
`cl_msg_before`. An author who is no longer a member SHALL show as a mention of the stored ID, with
`-` for the names and no thumbnail.

#### Scenario: Delete
- **WHEN** the stored `hi`, edited once, by member 7 in channel 30 of category 20 is deleted, in an
  en-US or a zh-TW guild where listen channel 5 detects channel 30
- **THEN** listen channel 5 gets v3's delete embed in that locale with the member, the category, the
  channel, 1 change and `hi`, and the message is no longer stored

#### Scenario: Author gone
- **WHEN** the author is no longer a member of the guild
- **THEN** the embed shows the mention of the stored author ID and no thumbnail

#### Scenario: Not stored
- **WHEN** a message that is not stored is deleted
- **THEN** nothing is posted and no member is fetched

#### Scenario: Not detected
- **WHEN** no listen channel detects the channel
- **THEN** the message is no longer stored, nothing is posted and no member is fetched

#### Scenario: Deleted at once
- **WHEN** `log_all` is false and a message and its deletion reach the plugin together
- **THEN** the deletion is logged and the message is not stored

#### Scenario: Bulk deletion
- **WHEN** three stored messages of one author and one message that is not stored are deleted at
  once
- **THEN** the three are posted oldest first, the author is fetched once, and none is stored

### Requirement: Logged texts are shown as written and fit an embed field
`cl_msg_before` and `cl_msg_after` SHALL hold the texts as written, without expanding `%...%`. A
text longer than 1024 characters, counted in UTF-16 code units, SHALL be cut to the characters that
fit before `...`.

#### Scenario: Long text
- **WHEN** a stored message of 2000 characters is deleted
- **THEN** the content field holds at most 1024 characters, its start and `...`

#### Scenario: Typed placeholders
- **WHEN** a message `%bot_id% %cl_msg_after%` is edited into `%user_mention%`
- **THEN** the embed shows both texts as written

### Requirement: Logs reach every listen channel
Each log SHALL be rendered in the guild's locale, falling back to zh-TW, and sent to each detecting
listen channel on its own. A listen channel that Discord no longer has SHALL be forgotten with a log
line, and one that refuses the message SHALL get a warning naming the guild and the channel, while
the other listen channels still get theirs; a bulk deletion SHALL not try either again.

#### Scenario: Locale without templates
- **WHEN** the guild's locale is French
- **THEN** the log uses the zh-TW templates

#### Scenario: Deleted listen channel
- **WHEN** Discord answers that listen channel 5 does not exist, while 6 also detects the channel
- **THEN** channel 5's settings are deleted with a log line and channel 6 gets the log

#### Scenario: Refused listen channel
- **WHEN** listen channel 5 refuses the message
- **THEN** a warning names the guild and the channel, 5's settings stay, and channel 6 gets the log

#### Scenario: Bulk deletion
- **WHEN** three stored messages are deleted at once while listen channel 5 is gone, 6 refuses and
  7 takes messages
- **THEN** channels 5 and 6 are tried once each, and channel 7 gets the three logs

### Requirement: Stored messages are kept for the retention period
When the bot is ready, and every hour after, the plugin SHALL delete the stored messages created
more than `retention_days` days ago, as their IDs tell. A failure SHALL be logged and the next hour
SHALL try again; unloading the plugin SHALL stop this, and a load that fails SHALL not start it.

#### Scenario: Old messages
- **WHEN** with 30 days, messages created 31 and 29 days ago are stored and the bot becomes ready
- **THEN** the first is deleted and the second stays

#### Scenario: Every hour
- **WHEN** an hour passes after READY
- **THEN** the old messages are deleted again

#### Scenario: Failure
- **WHEN** a deletion fails
- **THEN** an error is logged and the next hour deletes again

#### Scenario: Unload
- **WHEN** the plugin unloads
- **THEN** the hourly deletion stops

#### Scenario: Failed load
- **WHEN** the plugin loads into a ready bot and its checks of the guilds fail
- **THEN** the plugin is not loaded and no hourly deletion runs

### Requirement: Data is forgotten with the guild
When the bot leaves a guild, the plugin SHALL delete the guild's settings, and its stored messages
when `log_all` is false. When the bot is ready, and when the plugin loads into a ready bot, it SHALL
do the same for every guild the bot is no longer in.

#### Scenario: The bot leaves
- **WHEN** the bot leaves guild 10 while guild 20 has settings and stored messages too
- **THEN** guild 10's settings are deleted, its messages are deleted when `log_all` is false and
  kept when it is true, and guild 20's data stays

#### Scenario: Left while offline
- **WHEN** the bot becomes ready, or the plugin loads into a ready bot, and guild 20 is not among
  the bot's guilds
- **THEN** guild 20's settings are deleted with a log line, and its stored messages when `log_all`
  is false

### Requirement: Settings are checked when the bot is ready
When the bot is ready, and when the plugin loads into a ready bot, the plugin SHALL remove from the
allow and block lists of each available guild the channels that Discord no longer has, as v3's
startup did, and write nothing when none is gone. A listed channel or thread that discord.py has
not cached, such as an archived thread, SHALL be removed only when Discord answers that it does not
exist.

#### Scenario: Deleted channels
- **WHEN** the allow list holds channel 30, thread 41 and the deleted channel 31, and the block list
  the deleted category 22
- **THEN** the lists become `[30, 41]` and `[]`, with a log line

#### Scenario: Archived threads
- **WHEN** the lists hold the archived thread 42, the deleted thread 43 and the private thread 44,
  which Discord refuses to show
- **THEN** only thread 43 is removed
