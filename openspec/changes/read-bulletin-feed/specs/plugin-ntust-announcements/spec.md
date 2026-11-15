## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The config names the boards, the API keys and the prompt
**Reason**: The plugin reads bulletin's feed; it fetches no page and runs no model.
**Migration**: Use `api-url`, `poll-interval` and `rendition-wait`, and name each board by its
bulletin key in `board`.

### Requirement: Board pages list their announcements
**Reason**: bulletin polls the boards.
**Migration**: None; the feed lists the new announcements.

### Requirement: Article pages give their content as minified HTML
**Reason**: bulletin reads the articles.
**Migration**: None.

### Requirement: The prompt is filled in one pass
**Reason**: bulletin rewrites the articles with its own prompt.
**Migration**: None; `prompt` is ignored with a warning.

### Requirement: Gemini turns an article into Markdown
**Reason**: bulletin rewrites the articles.
**Migration**: None.

### Requirement: API keys stay within the rate limit and failed attempts are retried
**Reason**: The plugin calls no model.
**Migration**: Move the keys to bulletin's configuration.

### Requirement: New announcements are posted in board order
**Reason**: The feed says which announcements are new.
**Migration**: See "Notify-worthy announcements on a configured board wait for their rewrite".

### Requirement: Each board remembers what it posted
**Reason**: The feed's position replaces each board's posted list.
**Migration**: None; the old documents stay in the store, unread.

### Requirement: Boards are checked from READY until the plugin unloads
**Reason**: One loop reads the feed for every board.
**Migration**: See "The feed is read from READY until the plugin unloads".

### Requirement: Problems are logged without flooding or showing the keys
**Reason**: There are no keys or model endpoint to hide.
**Migration**: See "Problems are logged without flooding".

### Requirement: The model settings are config
**Reason**: The plugin calls no model.
**Migration**: None; the model keys are ignored with a warning.

### Requirement: An OpenAI-compatible API turns an article into Markdown
**Reason**: The plugin calls no model.
**Migration**: None.

### Requirement: Answers that hold a refused text are retried
**Reason**: The plugin calls no model.
**Migration**: None.

### Requirement: Posted messages are remembered
**Reason**: Only the redo read them.
**Migration**: None; the stored posts stay in the store, unread.

### Requirement: A reviewer's cross mark redoes a post
**Reason**: The plugin no longer converts articles; bulletin owns the rewrite.
**Migration**: None.

### Requirement: The review prompt
**Reason**: The redo is removed.
**Migration**: None.

### Requirement: A redo shows that it runs
**Reason**: The redo is removed.
**Migration**: None.
