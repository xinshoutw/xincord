# Spec Delta

## Purpose

New announcements on NTUST's boards are posted to Discord, articles converted by Gemini.

## ADDED Requirements

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

### Requirement: The config names the boards, the Gemini keys and the prompt
`config.yaml` SHALL keep v3's keys: `fetch-interval` (60 to 9223372036854775807 seconds, 3600 by
default), `api-keys` (not empty, no blank key, not v3's example key) and `prompt` (holding
`{{page_url}}`, `{{base_url}}`, `{{now}}` and `{{html}}`); and add `boards` (unique names, http(s)
URLs, a layout, a positive `channel-id`, an optional `title-prefix`) and `model`
(`gemini-2.5-flash` by default). Errors SHALL never show a key.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's (`enabled`, `fetch-interval`, two keys and v3's prompt) with
  `boards` added
- **THEN** the plugin loads with v3's values and `gemini-2.5-flash`, and logs a warning that names
  `enabled`

#### Scenario: Bundled config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it does not load, the error names `api-keys` and each board's `channel-id`, and the
  file lists v3's 18 boards with their URLs, layouts and the student main office's title prefix

#### Scenario: Invalid values
- **WHEN** `fetch-interval` is 59, a key is blank, the prompt lacks `{{html}}`, a layout is
  unknown, two boards share a name, or a board's URL has no host
- **THEN** the plugin does not load, and the error names the key

#### Scenario: Keys stay hidden
- **WHEN** a config with keys fails to load
- **THEN** neither the error nor its chained validation error shows a key

### Requirement: Board pages list their announcements
A board's first page SHALL give its entries as v3 parsed them: `student-affairs` takes the first
link of each `table.listTB.table` body row's first cell, `academic-affairs` of its second cell
(rows with fewer than two cells skipped), `language-center` each `div.row.listBS` row's title link.
Titles are the links' text with whitespace collapsed, links resolve against the page, and a
`title-prefix` keeps the titles that start with it.

#### Scenario: Student Affairs board
- **WHEN** a copy of the dormitory board's page is read
- **THEN** its entries are the golden list, in page order, the Google Docs link included

#### Scenario: Academic Affairs board
- **WHEN** a copy of the course board's page is read
- **THEN** its entries are the golden list, titled from each row's second cell

#### Scenario: Language Center board
- **WHEN** a copy of the recruitment board's page is read
- **THEN** its entries are the golden list

#### Scenario: Title prefix
- **WHEN** a copy of the student main office's page is read with the bundled title prefix
- **THEN** only the entries whose titles start with it remain

#### Scenario: Links
- **WHEN** entries link to `https://...`, `/p/x.php`, `//host/x`, `x.php` and `http://...`
- **THEN** the first and the last stay as written, `/p/x.php` takes the page's scheme and host,
  `//host/x` becomes `https://host/x` and `x.php` resolves against the page

#### Scenario: No list
- **WHEN** a Student Affairs page has no `table.listTB.table`, or rows without a link
- **THEN** the board, or those rows, give no entries

#### Scenario: Redirects
- **WHEN** a board's page redirects
- **THEN** it is read where the redirect leads, and its links resolve against that page

#### Scenario: NTUST's certificates
- **WHEN** a page is fetched over HTTPS
- **THEN** its certificate and host name are verified without Python's strict X.509 checks, which
  NTUST's certificate chains fail, and with TWCA's intermediate certificate, which
  `www.academic.ntust.edu.tw` does not send

### Requirement: Article pages give their content as minified HTML
A link SHALL count as an NTUST article when it matches v3's pattern
(`https://<host>.ntust.edu.tw/p/<digits, -, comma, r>.php...`). Its page SHALL give the outer HTML
of its first `div#Dyn_2_3.M23`, else of its first `div.M23`, minified with v3's steps (comments
removed, ASCII whitespace collapsed); a page without either gives none.

#### Scenario: Container
- **WHEN** a copy of a student article's page is read
- **THEN** its HTML is the `div#Dyn_2_3.M23` container's, without comments or indentation

#### Scenario: Fallback container
- **WHEN** a copy of an academic article's page, whose container is `div#Dyn_2_2.M23`, is read
- **THEN** its HTML is that `div.M23`'s

#### Scenario: No container
- **WHEN** a page has neither container
- **THEN** it gives no HTML

#### Scenario: Minify
- **WHEN** HTML holds comments, whitespace between tags, indented lines, no-break spaces and
  ideographic spaces
- **THEN** the comments and the runs of ASCII whitespace go, and the other spaces stay

#### Scenario: Article links
- **WHEN** links are an NTUST article, a Google Docs document, an NTUST file under `/var/file/`
  and an NTUST list page with a query
- **THEN** only the article and the list page count as NTUST articles, as in v3

#### Scenario: Other hosts
- **WHEN** a link's host is not under `ntust.edu.tw`, though its path, query or fragment holds
  `.ntust.edu.tw/p/<n>.php`
- **THEN** it counts as no NTUST article (v3's pattern took it)

### Requirement: The prompt is filled in one pass
The `prompt` SHALL be filled in one pass: `{{page_title}}` with the link's title, `{{page_url}}`
with its URL, `{{base_url}}` with `https://` and the URL's host (`ntust.edu.tw` when it has none),
`{{now}}` with the local time as `yyyy-MM-dd HH:mm:ss` and `{{html}}` with the article's HTML;
values are inserted as they are.

#### Scenario: Tokens
- **WHEN** the prompt holds every token and is filled for an article at 2026-10-11 09:05:03
- **THEN** each token is replaced with its value

#### Scenario: Values as they are
- **WHEN** a title holds `{{html}}`
- **THEN** the filled prompt shows `{{html}}` in place of the title, not the article's HTML

### Requirement: Gemini turns an article into Markdown
Each attempt SHALL POST the filled prompt to Gemini's `v1beta/models/<model>:generateContent` with
temperature 0.1 and the key in the `x-goog-api-key` header, never in the URL, and take the text of
the first candidate's parts, trimmed. An answer that is not 200, has no text or is blank SHALL be a
failed attempt.

#### Scenario: Request
- **WHEN** an attempt runs against a local server standing for Gemini
- **THEN** the server receives that POST with the key in the header, the prompt as the only text
  part and temperature 0.1, and no key in the URL

#### Scenario: Answer
- **WHEN** Gemini answers two text parts with whitespace around them
- **THEN** the attempt gives the parts joined and trimmed

#### Scenario: Failed answers
- **WHEN** Gemini answers 429 with an error, 200 without candidates, or blank text
- **THEN** the attempt fails, naming the status and Gemini's message when there is one

### Requirement: Gemini keys stay within the rate limit and failed attempts are retried
Keys SHALL be used in turn, from the one after the last used, each for at most 10 attempts started
in 60 seconds; when every key is at its limit, the conversion SHALL wait until the oldest of their
attempts is 60 seconds old, without using an attempt. A conversion SHALL make at most 10 attempts,
waiting 60, 300, 900, then 1800 seconds after each failed one, and give none after the tenth.

#### Scenario: Keys in turn
- **WHEN** two keys convert three articles
- **THEN** the attempts use the first key, the second, then the first

#### Scenario: Rate limit
- **WHEN** the only key started 10 attempts in the last 60 seconds
- **THEN** the next attempt waits until the oldest of them is 60 seconds old

#### Scenario: Retries
- **WHEN** every attempt fails
- **THEN** the conversion makes 10 attempts, waiting 60, 300, 900, then 1800 seconds, and gives
  none

#### Scenario: Success after failures
- **WHEN** the third attempt works
- **THEN** the conversion gives its text after waiting 60 and 300 seconds

### Requirement: Announcements become messages within Discord's limits
Content SHALL be posted as v3 split it, in UTF-16 code units: a header of 15 U+FF3F, a line break
and the trimmed content in one message up to 1975 units, else parts of at most 1980 units, cut
after the last line break that fits or at the limit (never inside a character), the header on the
first. A title link SHALL be the header and `# [title](url)`, `\[]` escaped, the title cut to fit.

#### Scenario: One message
- **WHEN** the trimmed content is 1975 units long
- **THEN** one message holds the header, a line break and the content

#### Scenario: Split at a line break
- **WHEN** the content is longer and has line breaks
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

### Requirement: New announcements are posted in board order
Each pass SHALL post, in page order and once per link, the board's entries with a title and a link
that the board has not posted: an NTUST article's converted content, or its title link when its
page has no container or Gemini failed every attempt, and other links' title links. Posts SHALL go
to the board's channel by ID, without the cache, and SHALL ping nobody.

#### Scenario: First pass
- **WHEN** the dormitory board is read and nothing was posted
- **THEN** each entry is posted in page order, articles as Gemini's Markdown and the Google Docs
  entry as its title link

#### Scenario: Posted links
- **WHEN** the board posted some of the page's links before
- **THEN** only the others are posted

#### Scenario: Duplicates and blank entries
- **WHEN** a link appears twice on the page, and an entry has a blank title
- **THEN** the link is posted once, and the blank entry not at all

#### Scenario: Content that cannot be converted
- **WHEN** an article's page has no container, or Gemini fails every attempt
- **THEN** the article is posted as its title link

#### Scenario: No pings
- **WHEN** Gemini's Markdown holds `@everyone`
- **THEN** the post allows no mentions

### Requirement: Each board remembers what it posted
A board's posted links SHALL be stored in namespace `NtustAnnouncements` under its name as v3's
document `{"items": [{"type", "url", "title"}]}` (v3's `itemTypeName` read and ignored), a link
added once posted. Failed article pages and refused posts SHALL be retried at the next pass; a
failed board page SHALL change nothing; links that left the page SHALL be kept, up to 100; a broken
document SHALL stop its board and stay.

#### Scenario: Stored once posted
- **WHEN** an announcement is posted
- **THEN** the board's document holds its item, in v3's shape, before the next one is converted

#### Scenario: v3 document
- **WHEN** the store holds v3's document with `itemTypeName`
- **THEN** its links count as posted

#### Scenario: Retried
- **WHEN** an article's page answers 500, or the channel refuses the post
- **THEN** nothing is stored for it and the next pass posts it

#### Scenario: Refused posts
- **WHEN** the channel refuses the posts at three passes, then takes them
- **THEN** each article is fetched and converted once, and posted when the channel takes it

#### Scenario: Store refusing a write
- **WHEN** the store refuses to save the board's document after a post
- **THEN** the announcement is not posted again while the plugin runs, and is stored later

#### Scenario: Links that leave the page
- **WHEN** a pass sees the page without some posted links and a later pass sees them again
- **THEN** they are not posted again

#### Scenario: Failed board page
- **WHEN** the board's page answers 404 or has no entries
- **THEN** nothing is posted and the document is unchanged

#### Scenario: Bounded
- **WHEN** 150 posted links have left the page
- **THEN** the document keeps the page's links and the 100 that left last

#### Scenario: Broken document
- **WHEN** the board's document is not v3's shape
- **THEN** the board posts nothing and the document stays as it was

### Requirement: Boards are checked from READY until the plugin unloads
After READY, or at once when the plugin loads into a ready bot, each board SHALL be read at once,
then `fetch-interval` seconds after each of its passes, on its own: a board waiting for Gemini
SHALL not hold up the others. At most 5 NTUST pages SHALL be fetched at a time. Unloading or
reloading SHALL cancel the loops; nothing SHALL be fetched before READY.

#### Scenario: Start at READY
- **WHEN** the plugin loads into a bot that is not ready
- **THEN** nothing is fetched until READY, then each board's page is fetched

#### Scenario: Interval
- **WHEN** a board's pass ends
- **THEN** its next pass starts `fetch-interval` seconds later

#### Scenario: Boards on their own
- **WHEN** one board waits between Gemini attempts
- **THEN** the other boards' passes go on

#### Scenario: Fetches at a time
- **WHEN** eight boards start together
- **THEN** at most five page fetches are under way at once

#### Scenario: Unload
- **WHEN** the plugin unloads while its boards wait
- **THEN** the loops end and nothing more is fetched

### Requirement: Problems are logged without flooding or showing the keys
Failed board pages, empty pages, failed article pages, failed Gemini attempts and refused posts
SHALL be logged once per kind (a status code, an error type) and failure episode, per board (for
Gemini, for all boards), the rest at debug level, with one info line once it has worked three times
in a row. Lines SHALL name the board, and a key by its position, never by its text.

#### Scenario: Repeated failure
- **WHEN** a board's page answers 503 at three passes
- **THEN** one warning names the board and the status, and the other two are debug lines

#### Scenario: Recovery
- **WHEN** the page then works at three passes
- **THEN** one info line says that the board's page works again

#### Scenario: Keys hidden
- **WHEN** a Gemini attempt fails with an error whose text holds the key
- **THEN** no log line holds the key, and the line names the key's position

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
