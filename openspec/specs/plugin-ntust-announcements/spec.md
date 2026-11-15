# plugin-ntust-announcements Specification

## Purpose
New announcements on NTUST's boards are posted to Discord from the events feed of bulletin, which
polls the boards and rewrites the announcements.

## Requirements

### Requirement: The plugin installs as NtustAnnouncements
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `NtustAnnouncements`, pointing to `xincord.plugins.ntust_announcements`, with no
dependencies and no intents beyond discord.py's defaults. Its first load SHALL write the bundled
`config.yaml` to `plugins/NtustAnnouncements/`, and no lang files, even while the config waits for
the operator.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `NtustAnnouncements` enabled
- **THEN** it returns `NtustAnnouncements` from `xincord.plugins.ntust_announcements` with no
  dependencies and no intents

#### Scenario: First load writes the config
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/NtustAnnouncements/` holds the bundled `config.yaml` and no `lang/` directory

### Requirement: Announcements become messages within Discord's limits
Content SHALL be posted in UTF-16 code units: a header of 15 U+FF3F, a line break and the trimmed
content in one message up to 1975 units, else in parts of at most 1980 units split at its
structure, the header on the first. A title link SHALL be the header and `# [title](url)`, `\[]`
escaped, the title cut to fit.

#### Scenario: One message
- **WHEN** the trimmed content is 1975 units long
- **THEN** one message holds the header, a line break and the content

#### Scenario: Split at a line break
- **WHEN** the content is longer and has plain line breaks only, no heading, blank line or list
  item
- **THEN** each part ends before the last line break that fits in 1980 units, which no part keeps

#### Scenario: Split without a line break
- **WHEN** 4000 units of content have no line break, or a character outside the BMP straddles a
  limit
- **THEN** the parts are cut at 1980 units, or before that character

#### Scenario: Blank parts
- **WHEN** a cut leaves a part of only whitespace
- **THEN** that part is left out and the others are posted

#### Scenario: Title link
- **WHEN** a title holds `]` or is 3000 characters long
- **THEN** the message escapes it, or cuts it with an ellipsis, keeps the whole URL and fits in
  2000 units

### Requirement: Channels are checked when the bot is ready
When the bot is ready, and when the plugin loads into a ready bot, a warning SHALL name each board
whose channel the bot cannot see or that takes no messages.

#### Scenario: Missing channel
- **WHEN** a board's channel is not in the bot's cache at READY
- **THEN** a warning names the board and the channel

#### Scenario: Channel without messages
- **WHEN** a board's channel is a category or a forum
- **THEN** a warning names the board and the channel

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads into a ready bot
- **THEN** the boards' channels are checked at once

### Requirement: Long content is split at its structure
A part SHALL end before a heading (a `#` line or a line wholly in bold), at a blank line, before a
list item or at a line break, preferring them in that order among the breaks past half the limit,
else at the last break that fits, else at the limit, never inside a character. A part SHALL NOT end
right after a heading. The line breaks at a cut SHALL be left out.

#### Scenario: Before a heading
- **WHEN** a heading and a blank line both fit past half the limit
- **THEN** the part ends before the heading

#### Scenario: At a blank line
- **WHEN** no heading but a blank line fits past half the limit
- **THEN** the part ends at that blank line

#### Scenario: Before a list item
- **WHEN** neither fits past half the limit, but a list item starts there
- **THEN** the part ends before the last such list item, not at a later plain line break

#### Scenario: No short parts
- **WHEN** the only heading and blank lines that fit are in the first half of the limit
- **THEN** the part ends at a later break, not at them

#### Scenario: Heading kept with its text
- **WHEN** the last break that fits follows a heading
- **THEN** the part ends before that heading, which starts the next part

### Requirement: The config names the feed and the boards
`config.yaml` SHALL hold `api-url` (an http or https URL with a host and no user info, query or
fragment; `https://bulletin.ntust.org/api/v1` by default), `poll-interval` (30 to
9223372036854775807 seconds, 60 by default), `rendition-wait` (0 to 86400 seconds, 3600 by
default) and `boards`: unique names, a `board` key (`<site>-<board>`, or `<site>` for all of a
site's boards), a `channel-id` (0 for none yet) and an optional `title-prefix`.

#### Scenario: An operator's config file
- **WHEN** `config.yaml` holds `enabled`, `api-url`, `poll-interval`, `rendition-wait` and
  `boards`
- **THEN** the plugin loads with those values, and logs a warning that names `enabled`

#### Scenario: An older file
- **WHEN** `config.yaml` holds the scraper's keys and boards with `url` and `layout`
- **THEN** the plugin does not load, and the error names each board's `board`

#### Scenario: Bundled config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it loads and requests nothing, and the file lists the 18 scraped boards with their
  keys and the student main office's title prefix, every channel 0

#### Scenario: Invalid values
- **WHEN** `poll-interval` is 29, `rendition-wait` is 86401, `api-url` has a query or no host, a
  board key is `1053-`, a `channel-id` is -1, or two boards share a name
- **THEN** the plugin does not load, and the error names the key

#### Scenario: No channel yet
- **WHEN** a board's `channel-id` is 0
- **THEN** its announcements are posted nowhere, and an info line at READY names it

### Requirement: The feed is read from READY until the plugin unloads
After READY, or at once when the plugin loads into a ready bot, the plugin SHALL read the feed at
once, then `poll-interval` seconds after each pass ends. Unloading or reloading SHALL cancel the
loop; nothing SHALL be requested before READY.

#### Scenario: Start at READY
- **WHEN** the plugin loads into a bot that is not ready
- **THEN** nothing is requested until READY, then the feed is read

#### Scenario: Interval
- **WHEN** a pass ends
- **THEN** the next pass starts `poll-interval` seconds later

#### Scenario: Unload
- **WHEN** the plugin unloads while it waits between passes
- **THEN** the loop ends and nothing more is requested

### Requirement: The first read starts at the feed's end
When no position is stored, the first pass SHALL read the feed from its start to its end, posting
nothing, and store the last event's ID as the position. Each later pass SHALL read the events
after the stored position in ID order, 500 at a time, until a read returns fewer.

#### Scenario: First pass
- **WHEN** nothing is stored and the feed holds 1,200 events, notify-worthy ones among them
- **THEN** nothing is posted, and the stored position is the last event's ID

#### Scenario: Several reads
- **WHEN** 700 events follow the stored position
- **THEN** one read asks for 500 events after the position, a second for those after the 500th,
  and the events are handled in ID order

### Requirement: Notify-worthy announcements on a configured board wait for their rewrite
A `published` event marked notify-worthy SHALL put its announcement in waiting when its boards
match a configured board that has a channel and whose `title-prefix` starts its title. It SHALL
wait until its
`rendered` event, or until `rendition-wait` seconds after the event; a link entry SHALL not wait,
and a `withdrawn` event SHALL drop it. Other events and announcements SHALL post nothing.

#### Scenario: Rewrite in time
- **WHEN** a notify-worthy announcement on the dormitory board is rendered ten minutes after it
  is published
- **THEN** it is posted at the pass that reads its `rendered` event

#### Scenario: No rewrite in time
- **WHEN** no `rendered` event comes within `rendition-wait` seconds
- **THEN** it is posted at the first pass after the wait, as the API then gives it

#### Scenario: Link entry
- **WHEN** the announcement is a link entry
- **THEN** it is posted at the pass that reads its `published` event

#### Scenario: Not notify-worthy
- **WHEN** a `published` event is not notify-worthy, as for a late discovery, a backfill or a
  cross-post
- **THEN** nothing is posted

#### Scenario: A whole site
- **WHEN** a configured board's key is `1053` and the announcement is on board `1053-1439`
- **THEN** it waits, and is posted to that board's channel

#### Scenario: Other boards and titles
- **WHEN** the announcement is on no configured board, or its title lacks the board's title
  prefix
- **THEN** nothing is posted

#### Scenario: Withdrawn
- **WHEN** the announcement is withdrawn while it waits
- **THEN** it is not posted

### Requirement: Waiting announcements are posted to their boards' channels
A due announcement SHALL be read from the API and posted to the channel of each configured board
it is on, once per channel, in config order, by ID without the cache and pinging nobody. A failed
read or a refused post SHALL be retried at each pass until a day after it was due, then dropped
with an error. An announcement the API no longer has SHALL be dropped with a warning.

#### Scenario: Two boards, one channel
- **WHEN** the announcement is on two configured boards that share a channel
- **THEN** that channel gets it once

#### Scenario: Two channels
- **WHEN** it is on two configured boards with their own channels
- **THEN** each channel gets it, in config order

#### Scenario: Refused post
- **WHEN** one of two channels refuses the post at two passes, then takes it
- **THEN** the other channel gets it once, and the refusing channel gets it at the third pass

#### Scenario: Refused for a day
- **WHEN** a channel still refuses it a day after it was due
- **THEN** it is dropped, and an error names the announcement and the channel

#### Scenario: Failed read
- **WHEN** the API answers 503 for the announcement
- **THEN** nothing is posted, and the next pass reads it again

#### Scenario: Gone
- **WHEN** the API answers 404 for the announcement
- **THEN** it is dropped, and a warning names it

#### Scenario: No pings
- **WHEN** the rewrite holds `@everyone`
- **THEN** the post allows no mentions

### Requirement: The feed's position and the waiting announcements are stored
The position and the waiting announcements SHALL be stored in namespace
`NtustAnnouncements.feed` under `state` as `{"after", "waiting": [{"id", "due", "posted"}]}`,
saved after each read and each post, so that a restart resumes them. A document of another shape
SHALL stop the plugin's reads and stay; a refused write SHALL be logged and retried, the plugin
going on from what it holds.

#### Scenario: Restart
- **WHEN** the plugin restarts with an announcement waiting and a stored position
- **THEN** it reads the events after that position, and posts the waiting announcement when it is
  due

#### Scenario: Posted channels
- **WHEN** a restart comes after one of two channels got the announcement
- **THEN** only the other channel gets it

#### Scenario: Broken document
- **WHEN** the stored document is of another shape
- **THEN** nothing is read or posted, an error is logged, and the document stays

#### Scenario: Store refusing a write
- **WHEN** the store refuses the write after a post
- **THEN** the announcement is not posted again while the plugin runs, and the next write stores
  the state

### Requirement: Problems are logged without flooding
Failed feed reads, failed announcement reads, refused posts, a broken document and refused writes
SHALL be logged once per kind (a status code, an error type, an unexpected answer) and failure
episode, the rest at debug level, with one info line once the step has worked three times in a
row. Lines SHALL show `api-url` only as its origin.

#### Scenario: Repeated failure
- **WHEN** the feed answers 503 at three passes
- **THEN** one warning names the status, and the other two are debug lines

#### Scenario: Recovery
- **WHEN** the feed then works at three passes
- **THEN** one info line says that the feed works again

#### Scenario: Unexpected answer
- **WHEN** the feed answers 200 with a body that is not the feed's JSON
- **THEN** a warning says so, and no event is handled

#### Scenario: Origin only
- **WHEN** `api-url` has a path and a read fails
- **THEN** the line shows its scheme, host and port, and not its path

### Requirement: A rewritten announcement becomes its title link, its rewrite and its attachments
An announcement with a rewrite SHALL be posted as content: `# [title](url)` built as the title
link is, a blank line, the rewrite's Markdown and, when it has attachments, a blank line and one
`- [name](url)` line each, names escaped and URLs encoded as in the title link. An announcement
without a rewrite SHALL be posted as its title link.

#### Scenario: Rewrite
- **WHEN** an announcement has a rewrite and two attachments
- **THEN** one message holds the header, the title link, the rewrite and the two attachment lines

#### Scenario: Long rewrite
- **WHEN** the rewrite with its title link is longer than 1975 units
- **THEN** it is split at its structure, the header on the first part

#### Scenario: No rewrite
- **WHEN** the announcement has no rewrite
- **THEN** it is posted as its title link
