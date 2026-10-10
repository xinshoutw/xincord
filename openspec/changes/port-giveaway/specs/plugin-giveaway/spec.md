# Spec Delta

## Purpose

Administrators build a giveaway step by step in an ephemeral builder and post it; members join and
leave it with a button; the creator or an administrator draws the winners, administrators reroll
them, and giveaways whose end time has come are drawn automatically.

## ADDED Requirements

### Requirement: The plugin installs as Giveaway
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Giveaway`, pointing to `xincord.plugins.giveaway`, with no dependencies and no intents. It
SHALL bundle `config.yaml` and v3's en-US and zh-TW lang files (`register.yaml`, seven message and
six modal templates) with a `text.yaml` per locale, which its first load writes to
`plugins/Giveaway/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Giveaway` enabled
- **THEN** it returns `Giveaway` from `xincord.plugins.giveaway` with no dependencies and no
  intents

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/Giveaway/config.yaml` is the bundled file and the 30 lang files exist under
  `plugins/Giveaway/lang/`

### Requirement: The config keeps v3's keys
`config.yaml` SHALL hold v3's `defaultLocale`, `zh-TW` by default, a Discord locale whose lang files
serve users whose locale has none, and `autoDrawIntervalSeconds`, 60 by default, an integer clamped
to 5 to 3600 seconds, and add `timeZone`, the IANA zone of the end times, empty for the host's. v3's
files SHALL load, their `enabled` key only warning; an unknown locale or zone or a non-integer
interval SHALL stop the plugin from loading, with the key named.

#### Scenario: v3's file
- **WHEN** `plugins/Giveaway/config.yaml` is v3's, with `enabled: false`, `defaultLocale: "zh-TW"`
  and `autoDrawIntervalSeconds: 60`
- **THEN** the plugin loads with zh-TW, 60 seconds and the host's zone, and a warning names
  `enabled`

#### Scenario: Clamped interval
- **WHEN** `autoDrawIntervalSeconds` is 1, 0, -5 or 99999
- **THEN** the automatic draw runs every 5, 5, 5 or 3600 seconds

#### Scenario: Invalid values
- **WHEN** `defaultLocale` is `zh-tw`, `timeZone` is `Mars/Base` or `autoDrawIntervalSeconds` is
  `soon` or 1.5
- **THEN** the plugin does not load and the error names the key

#### Scenario: Locale without lang files
- **WHEN** `defaultLocale` is `ja`, which has no lang directory
- **THEN** the plugin does not load and the error names the locale

### Requirement: Each message uses one language
The plugin SHALL take a message's texts and templates from one locale: the plugin's own files for
the locale when it has them, else zh-TW for a Chinese locale and en-US for any other, each text
falling back to `defaultLocale`. The builder and its replies SHALL follow the user's locale; the
post, its replies and the announcement the creator's, stored with the giveaway; `Giveaway not
found.` the user's.

#### Scenario: Locales with files
- **WHEN** the locale is en-US or zh-TW
- **THEN** that locale's texts and templates are used

#### Scenario: Other Chinese locale
- **WHEN** the locale is zh-CN
- **THEN** the zh-TW texts and templates are used

#### Scenario: Other locale
- **WHEN** the locale is en-GB or ja
- **THEN** the en-US texts and templates are used, where v3 showed English texts with zh-TW
  buttons

### Requirement: End times are read and shown in the configured zone
An end time SHALL be `yyyy-MM-dd HH:mm` in ASCII digits with a year from 0001 to 9999, read in
`timeZone` as v3's Java pattern did: a day past the month's last day is clamped to it, and `24:00`
is the start of the next day. The plugin SHALL show end times in the same pattern and zone.

#### Scenario: Accepted
- **WHEN** `2026-03-01 10:00` is read in Asia/Taipei
- **THEN** it is the epoch second 1772330400

#### Scenario: Clamped day
- **WHEN** `2026-02-30 10:00`, `2025-02-29 10:00` or `2026-04-31 10:00` is read
- **THEN** it is February 28 or April 30 at 10:00

#### Scenario: End of day
- **WHEN** `2026-12-31 24:00` or `2026-02-30 24:00` is read
- **THEN** it is 2027-01-01 00:00 or 2026-03-01 00:00

#### Scenario: Rejected
- **WHEN** the text is `2026-01-05 24:01`, `2026-01-05 23:60`, `2026-1-05 10:00`, `2026-01-05 9:00`,
  `2026-01-05T10:00`, `2026-01-05 10:00:00`, `2026/01/05 10:00`, `26-01-05 10:00`,
  `0000-01-05 10:00`, `2026-01-05  10:00`, `+2026-01-05 10:00`, full-width digits, month `00` or
  `13`, day `00` or `32`, or `+12026-01-05 10:00`
- **THEN** it is not an end time

#### Scenario: Shown
- **WHEN** the epoch second 1772330400 is shown in Asia/Taipei
- **THEN** it reads `2026-03-01 10:00`

#### Scenario: Host's zone
- **WHEN** `timeZone` is empty and the host's zone is Asia/Taipei
- **THEN** `2026-03-01 10:00` is the epoch second 1772330400

### Requirement: Builder inputs are checked as in v3
The plugin SHALL trim modal values of Kotlin's whitespace, which is Python's without U+0085. A winner
count SHALL be an optional sign and decimal digits, Unicode digits included, from 1 to 50. A
thumbnail SHALL be a URL whose scheme is http or https in any case and whose host is a valid host
name, IPv4 or bracketed IPv6 address, as Java's `URI` read it.

#### Scenario: Trimmed values
- **WHEN** a value is surrounded by spaces, tabs, U+3000 or U+0085
- **THEN** the spaces, tabs and U+3000 are removed and U+0085 stays

#### Scenario: Winner counts
- **WHEN** the count is `1`, `50`, `+5`, `05` or full-width `5`
- **THEN** it is accepted as 1, 50, 5, 5 or 5, and `0`, `51`, `-1`, `1_0`, `1e1`, `x` and an empty
  value are refused

#### Scenario: Thumbnail URLs
- **WHEN** the URL is `https://example.com/a.png`, `HTTPS://EXAMPLE.COM/a.png`, `http://x`,
  `https://user@host:8080/p?q#f`, `https://1.2.3.4/x`, `https://[::1]/x` or
  `https://xn--fsqu00a.xn--0zwm56d/a.png`
- **THEN** it is accepted, and `https://`, `https:///path`, `ftp://x.com`, `https://exa mple.com`,
  a non-ASCII host, `https://host_name.com/x`, `https://1.2.3.400/x`, `//host/p` and
  `javascript:alert(1)` are refused

### Requirement: Winners are drawn per prize
For each prize in order, the plugin SHALL draw the smaller of its winner count (at least 1) and the
pool's size as distinct winners, uniformly at random: from every participant when duplicates are
allowed, and from those no earlier prize drew under unique winners across prizes. Without prizes
there SHALL be no result. Production draws SHALL use `random.SystemRandom`.

#### Scenario: Duplicates allowed
- **WHEN** three participants join a giveaway with prizes of 2 and 2 winners and duplicates allowed
- **THEN** each prize gets 2 distinct participants, and one participant may win both

#### Scenario: Unique winners across prizes
- **WHEN** three participants join a giveaway with prizes of 2, 2 and 1 winners and unique winners
- **THEN** the first prize gets 2, the second the remaining 1 and the third none, all distinct

#### Scenario: No participants
- **WHEN** nobody joined
- **THEN** every prize has an empty result, in prize order

#### Scenario: Uniform draw
- **WHEN** one winner of four participants is drawn many times with a seeded generator
- **THEN** each participant wins about a quarter of the draws

#### Scenario: System random
- **WHEN** the plugin loads
- **THEN** it draws with a `random.SystemRandom`

### Requirement: Giveaways are stored as v3's documents
Each guild's giveaways SHALL be one document in the store, namespace `Giveaway`, key the guild ID,
value v3's JSON `{"<id>": {...}}` in Moshi's field order with `endedAtEpochSecond` left out while
unset. Missing optional fields SHALL read as v3's defaults (`createdAtEpochSecond` as 0). An entry
that is not v3's shape SHALL raise and never be overwritten, and the guild's other entries SHALL
keep working.

#### Scenario: v3's documents
- **WHEN** the store holds v3's example document of a running and a drawn giveaway
- **THEN** both read with their fields, and writing them back gives the same JSON

#### Scenario: Defaults
- **WHEN** an entry has only `id`, the IDs and `config`
- **THEN** it reads with the locale zh-TW, no participants, no results, not drawn and created at 0

#### Scenario: Not v3's shape
- **WHEN** an entry lacks `creatorId`, has the policy `RANDOM`, or a text or a fraction as an ID
- **THEN** reading it raises, a change to it raises, the stored document stays as it was, and a
  join to another giveaway of the guild is stored

### Requirement: The command opens the builder
`/create-giveaway` SHALL edit the response that the tree deferred ephemerally into v3's
`create-giveaway` template in the user's language, showing an empty draft's preview, and keep that
draft for the user in the guild, replacing a draft they had there.

#### Scenario: Builder
- **WHEN** an administrator with an en-US or a zh-TW client runs the command
- **THEN** the response shows the empty draft's preview and v3's ten buttons in four rows, whose
  IDs are `giveaway:1:a=create;b=<sub-action>`

#### Scenario: New draft
- **WHEN** a user with a draft titled `Old` runs the command again in the same guild
- **THEN** the new builder shows an empty draft and only it drives the user's draft

### Requirement: The preview shows the draft
The preview SHALL be v3's green embed: `🎁` and the title, or v3's draft title; the description,
the end time as `<t:END:F>` and in the zone, the prizes as `N. name (count ...)`, the winner
policy, the total winner slots and the sponsor, unset ones `Not set`; the thumbnail when its URL is
http or https in any case; v3's footer. A field longer than 1024 characters SHALL end with `...`.

#### Scenario: Empty draft
- **WHEN** the draft is empty, in en-US or zh-TW
- **THEN** the preview is v3's embed with the draft title, `Not set`, `No prize yet`, duplicates
  allowed and 0 slots

#### Scenario: Full draft
- **WHEN** the draft has a title, a description, an end time, two prizes of 2 and 0 winners, unique
  winners, a sponsor and an `HTTPS://` thumbnail
- **THEN** the preview is v3's embed with those values, 3 slots and the thumbnail

#### Scenario: Long texts
- **WHEN** the description has 4000 characters and the prizes take more than 1024
- **THEN** both fields hold 1024 characters ending with `...`, and the builder still updates

### Requirement: Builder buttons open pre-filled modals
The buttons set-title, set-description, set-end-time, set-sponsor, set-thumbnail and add-prize SHALL
open v3's modal of the same name in the user's language with the interaction's values and the
draft's `ga@title`, `ga@description`, `ga@end-time` (empty when unset), `ga@sponsor`,
`ga@thumbnail` and `ga@prize-name` (`Prize N`, N the next prize's number), inserted as written.

#### Scenario: Title modal
- **WHEN** a user whose draft is titled `Nitro` presses set-title
- **THEN** the modal `giveaway:1:a=create;b=set-title` opens with v3's title, label and placeholder
  and the input `title` pre-filled with `Nitro`, at most 100 characters

#### Scenario: End time modal
- **WHEN** the draft ends at the epoch second 1772330400 in Asia/Taipei, or has no end time
- **THEN** the input `end-time` is pre-filled with `2026-03-01 10:00`, or empty

#### Scenario: Prize modal
- **WHEN** a draft with two prizes gets add-prize in en-US or zh-TW
- **THEN** `prize-name` is pre-filled with v3's third prize name and `winner-count` with `1`

#### Scenario: Typed placeholders
- **WHEN** the title is `%bot_name%`
- **THEN** the modal shows `%bot_name%` as written

### Requirement: Submitted modals change the draft
A valid submission SHALL change the draft and replace the builder message with its preview; an
invalid one SHALL get v3's error ephemerally and leave the draft. The title SHALL not be blank; an
empty description, sponsor or thumbnail SHALL clear it; the end time SHALL be given, valid and in
the future; a prize SHALL have a name and a winner count, and be appended; a thumbnail SHALL be a
valid URL.

#### Scenario: Title
- **WHEN** ` Nitro ` is submitted in set-title
- **THEN** the draft's title is `Nitro` and the builder shows it

#### Scenario: Errors
- **WHEN** a blank title, a blank, invalid or past end time, a blank prize name, a winner count of
  51 or the thumbnail `ftp://x.com` is submitted
- **THEN** the user gets v3's error for it in their language and the draft stays

#### Scenario: Prizes
- **WHEN** prizes are submitted one after another
- **THEN** each is appended to the list, without a limit on their number

#### Scenario: Cleared
- **WHEN** an empty description, sponsor or thumbnail is submitted
- **THEN** the field is cleared and the preview shows `Not set` or no thumbnail

### Requirement: The builder removes prizes and switches the winner policy
remove-prize SHALL remove the last prize and update the builder, or answer `No prize to remove.`
ephemerally when there is none; toggle-duplicate-policy SHALL switch between duplicates allowed and
unique winners across prizes and update the builder.

#### Scenario: Remove
- **WHEN** a draft with two prizes gets remove-prize
- **THEN** the first prize remains and the builder shows it

#### Scenario: Nothing to remove
- **WHEN** a draft without prizes gets remove-prize
- **THEN** the user gets v3's text ephemerally and the builder stays

#### Scenario: Switch
- **WHEN** toggle-duplicate-policy is pressed twice
- **THEN** the policy becomes unique winners, then duplicates allowed, and the builder shows each

### Requirement: Only the latest builder of a draft works
A builder press or submission SHALL get v3's session-expired text ephemerally when the user has no
draft in the guild, or when it comes from a builder message other than the one that shows their
draft. A builder press with an unknown sub-action SHALL get no response.

#### Scenario: No draft
- **WHEN** a user without a draft, as after a restart, presses a builder button or submits a modal
- **THEN** they get v3's session-expired text ephemerally in their language

#### Scenario: Older builder
- **WHEN** a user presses a button of their first builder after running the command again
- **THEN** they get the session-expired text and the new draft is unchanged

#### Scenario: Unknown sub-action
- **WHEN** a user with a draft presses a builder button with the sub-action `other`
- **THEN** nothing is sent

### Requirement: Confirming checks the draft and the administrator
confirm-create SHALL answer ephemerally with v3's text, in v3's order, when the title is blank, the
end time has come or is unset, or no prize was added, and then when the user lacks the
Administrator permission; nothing SHALL be posted and the draft SHALL stay.

#### Scenario: Incomplete draft
- **WHEN** the draft lacks a title, a future end time or a prize
- **THEN** the user gets the text for the first missing one and nothing is posted

#### Scenario: Not an administrator
- **WHEN** a complete draft is confirmed by a user without Administrator
- **THEN** the user gets v3's text and nothing is posted

### Requirement: Confirming posts the giveaway
Otherwise the plugin SHALL take the draft, acknowledge the press, post `giveaway-post` in the
builder's channel in the user's language with a new ID of 16 hexadecimal characters unused in the
guild, store the giveaway with the post's message, the creator and the user's locale, and replace
the builder with `create-finished` and the post's link. A press while the giveaway is posted SHALL
get the session-expired text.

#### Scenario: Posted
- **WHEN** an administrator confirms a complete draft in channel 5
- **THEN** channel 5 gets the post, the store holds the giveaway with its message, and the builder
  becomes v3's `create-finished` text with the post's link, without embeds or buttons

#### Scenario: Double press
- **WHEN** confirm-create is pressed twice before the post is made
- **THEN** one giveaway is posted and stored, and the second press gets the session-expired text

### Requirement: A giveaway that cannot be posted keeps the builder
When the builder's channel takes no messages or refuses the post, or the giveaway cannot be stored,
in which case the post is deleted, the plugin SHALL give the draft back, keep the builder and send
v3's `create-failed` with the error as an ephemeral follow-up.

#### Scenario: Channel refuses
- **WHEN** the channel refuses the post
- **THEN** nothing is stored, the builder stays, the user gets `create-failed` with the error, and
  a later confirmation can post

#### Scenario: Store fails
- **WHEN** the giveaway cannot be stored after the post was made
- **THEN** the post is deleted and the user gets `create-failed`

#### Scenario: Acknowledgement fails
- **WHEN** Discord refuses the acknowledgement of the press, before anything is posted
- **THEN** the draft stays, so that a later press can post it

### Requirement: Cancelling ends the draft
cancel SHALL drop the user's draft and replace the builder message with v3's `create-cancelled`,
without embeds or buttons.

#### Scenario: Cancelled
- **WHEN** a user with a draft presses cancel
- **THEN** the builder shows v3's cancelled text alone and a later press gets the session-expired
  text

### Requirement: The post shows the giveaway
The post SHALL be v3's embed and buttons in the creator's language: `🎉` and the title as written;
the description or v3's default; gold while running, gray once drawn; status with `<t:END:R>`,
participants, policy, prizes, winner results and the sponsor when set; the thumbnail; the ID in the
footer. Join SHALL be disabled once closed, Draw once drawn, Reroll until drawn. Fields SHALL fit
1024 characters and the embed 6000.

#### Scenario: Running
- **WHEN** a running giveaway with two participants is shown in en-US or zh-TW
- **THEN** the post is v3's gold embed with `Running`, 2, `Not drawn yet` and the enabled join and
  draw buttons

#### Scenario: Drawn
- **WHEN** a drawn giveaway with a prize that drew nobody is shown
- **THEN** the post is v3's gray embed with `Drawn`, each prize's winners as mentions or v3's not
  enough text, and only Reroll enabled

#### Scenario: Long texts
- **WHEN** the description has 4000 characters and the prizes and winners take more than 1024
  each
- **THEN** each field holds at most 1024 characters and the embed at most 6000

### Requirement: Members join and leave
Join / Leave SHALL add the user to the participants or remove them, update the post through the
press and tell the user ephemerally, in the giveaway's language, that they joined or left. A
giveaway that is drawn or whose end time has come SHALL answer that it is closed; a press on a
message other than the giveaway's post SHALL be acknowledged without change; an unknown giveaway
SHALL answer `Giveaway not found.`.

#### Scenario: Join and leave
- **WHEN** user 7 presses Join / Leave twice
- **THEN** they are stored as a participant, then not, the post shows 1 then 0, and they get v3's
  joined and left texts

#### Scenario: Closed
- **WHEN** the giveaway is drawn, or its end time has come
- **THEN** the user gets v3's closed text and nothing changes

#### Scenario: Another message
- **WHEN** the press comes from a message that is not the giveaway's post
- **THEN** it is acknowledged and nothing changes

#### Scenario: Unknown giveaway
- **WHEN** the button names a giveaway that the guild does not have
- **THEN** the user gets v3's not found text in their language

#### Scenario: Joins at once
- **WHEN** two users press Join / Leave at the same time
- **THEN** both are stored as participants

### Requirement: The creator or an administrator draws and administrators reroll
Draw Winners SHALL be allowed to the creator and administrators once the end time has come, Reroll
to administrators once drawn. Each SHALL draw every prize from the participants, mark the giveaway
drawn at that time and store it before updating the post through the press, then send v3's
`draw-result` ephemerally. Refusals SHALL get v3's texts in the giveaway's language.

#### Scenario: Draw
- **WHEN** the creator, or an administrator, presses Draw Winners after the end time
- **THEN** the stored giveaway is drawn, the post shows the winners, and they get v3's draw result

#### Scenario: Not allowed
- **WHEN** a member who is neither the creator nor an administrator presses Draw Winners, or the
  creator without Administrator presses Reroll
- **THEN** they get v3's not allowed text and nothing changes

#### Scenario: Wrong time
- **WHEN** Draw Winners is pressed before the end time or after the draw, or Reroll before it
- **THEN** the user gets v3's too early text with `<t:END:R>`, already drawn or not drawn text

#### Scenario: Reroll
- **WHEN** an administrator presses Reroll on a drawn giveaway
- **THEN** every prize is drawn again from the participants and the result's header is v3's
  reroll text

#### Scenario: No participants
- **WHEN** a giveaway without participants is drawn
- **THEN** the result's body is v3's no participants text

### Requirement: Due giveaways are drawn automatically
Five seconds after READY, then each `autoDrawIntervalSeconds` after a pass, the plugin SHALL draw
each undrawn giveaway whose end time has come, in guilds the bot is in and that are available,
store it, then update its post and send `auto-draw-result` to its channel of any kind, in the
creator's language. A failure SHALL be logged and the other giveaways still handled.

#### Scenario: First pass
- **WHEN** the bot becomes ready with a giveaway whose end time passed while it was offline
- **THEN** five seconds later it is drawn and stored, its post is updated and its channel gets the
  announcement

#### Scenario: Later passes
- **WHEN** a giveaway's end time comes between two passes
- **THEN** the next pass draws it, and a pass draws each giveaway only once

#### Scenario: Skipped guilds
- **WHEN** the bot is not in the giveaway's guild or the guild is unavailable
- **THEN** the giveaway is not drawn until the guild is back

#### Scenario: Post gone
- **WHEN** the post or its channel was deleted, or the channel refuses the announcement
- **THEN** the giveaway stays drawn, warnings name it, and the other giveaways are handled

#### Scenario: Failed pass
- **WHEN** the store fails during a pass
- **THEN** the error is logged and the next pass runs

#### Scenario: Failed announcement
- **WHEN** posting one drawn giveaway fails unexpectedly
- **THEN** the error is logged and the pass posts the other drawn giveaways

#### Scenario: Unload
- **WHEN** the plugin unloads
- **THEN** the automatic draw stops

### Requirement: v3's posts keep working
The plugin SHALL route the IDs of `ComponentIds("giveaway", ("action", "sub_action",
"giveaway_id"), legacy_prefix="giveaway@")`: buttons with the actions `create`, `participate`,
`draw` and `reroll` and modals with `create`, in v3's format too, after which the core upgrades a
post's IDs. Other actions and select menus SHALL get no response.

#### Scenario: v3's post
- **WHEN** user 7 presses `giveaway@a:participate;c:3f2a9c1b7e4d4a60` on a v3 post
- **THEN** they join the giveaway and the post's buttons get IDs such as
  `giveaway:1:a=participate;c=3f2a9c1b7e4d4a60`

#### Scenario: v3's builder
- **WHEN** a v3 builder button `giveaway@a:create;b:set-title` is pressed after the switch
- **THEN** the user gets the session-expired text

#### Scenario: Other actions
- **WHEN** a button with the action `other`, a select menu or a modal with the action `draw` arrives
- **THEN** nothing is sent

### Requirement: The command is a localized administrator guild command
The plugin SHALL register `create-giveaway` as a guild command without options, with v3's
description and localizations and the default member permission Administrator. The command tree
SHALL defer it ephemerally before its callback runs.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** `create-giveaway` has v3's description, its en-US and zh-TW localizations, no options
  and the default member permissions 8

#### Scenario: Command callback
- **WHEN** the command runs
- **THEN** its callback, bound to the plugin's cog, answers in the response that the tree deferred
  ephemerally

### Requirement: Leaving a guild drops its drafts
When the bot leaves a guild, the plugin SHALL drop the drafts of that guild and keep its giveaways.

#### Scenario: Left guild
- **WHEN** the bot leaves guild 10, where a user has a draft and a giveaway is stored
- **THEN** the user's builder answers that the session expired, and the giveaway is still stored
