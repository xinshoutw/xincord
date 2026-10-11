# Spec Delta

## Purpose

Members register NTUST course codes in a channel and hear there when a course has seats.

## ADDED Requirements

### Requirement: The plugin installs as NtustCourseWatch
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `NtustCourseWatch`, pointing to `xincord.plugins.ntust_course_watch`, with no dependencies
and no intents beyond discord.py's defaults. Its first load SHALL write the bundled `config.yaml`
and the `lang/` files of en-US, its default locale, and zh-TW to `plugins/NtustCourseWatch/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `NtustCourseWatch` enabled
- **THEN** it returns `NtustCourseWatch` from `xincord.plugins.ntust_course_watch` with no
  dependencies and no intents

#### Scenario: First load writes the config and the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** it loads, and `plugins/NtustCourseWatch/` holds the bundled `config.yaml` and the en-US
  and zh-TW lang files

### Requirement: The config names the semester, the start and the intervals
`config.yaml` SHALL hold `semester` (letters and digits, v3's `1142` by default, numbers read as
text), `start` (a time with its offset, v3's 2025-12-26 09:00 at +08:00 by default), `interval`
(seconds between two requests, 1 to 86400, v3's 1.5 by default) and `alert-interval` (10 to 86400
seconds, 60 by default). v3's file SHALL load with these defaults; invalid values SHALL keep the
plugin from loading with the key named.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's (`enabled: false` only)
- **THEN** the plugin loads with semester `1142`, start 2025-12-26 09:00 +08:00, interval 1.5 and
  alert interval 60, and logs a warning that names `enabled`

#### Scenario: Bundled config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it loads with the same values

#### Scenario: Numbers as text
- **WHEN** `semester` is an unquoted `1151`, or `114H`
- **THEN** the semester is the text `1151`, or `114H`

#### Scenario: Invalid values
- **WHEN** `semester` holds a space, `start` has no offset, `interval` is 0.5 or `alert-interval`
  is 5
- **THEN** the plugin does not load, and the error names the key

### Requirement: Members register courses in a channel
`/course-add id` SHALL read the code as NFKC text without surrounding whitespace in upper case,
refuse a code that is not 9 to 20 letters and digits with `invalid-code` (NTUST matches a code as a
prefix), add the member once to the course's members in the command's channel, and reply
`registered`.

#### Scenario: Register
- **WHEN** a member runs `/course-add id:CE162A001` in channel 5
- **THEN** the member is registered for `CE162A001` in channel 5 and the reply is `registered`

#### Scenario: Register twice
- **WHEN** the member runs the same command again
- **THEN** the member is registered once and the reply is `registered`

#### Scenario: Typed loosely
- **WHEN** the code is ` ce162a001 ` or written in full-width letters and digits
- **THEN** the member is registered for `CE162A001`

#### Scenario: Invalid code
- **WHEN** the code is `CE 162A001`, `CE-162A001`, `C`, `CE162A00` or 21 characters long
- **THEN** nothing is registered and the reply is `invalid-code`

### Requirement: Members unregister their own courses
`/course-remove id` SHALL read the code as `/course-add` does, refuse an invalid one with
`invalid-code`, remove only the member from the course's members in the command's channel, drop a
course or a channel left without members, and reply `unregistered`, also when the member was not
registered.

#### Scenario: Unregister
- **WHEN** two members registered `CE162A001` in channel 5 and one runs `/course-remove id:ce162a001`
  there
- **THEN** only the other member stays registered and the reply is `unregistered`

#### Scenario: Not registered
- **WHEN** a member who did not register a course runs `/course-remove` for it
- **THEN** nothing changes and the reply is `unregistered`

#### Scenario: Last registration
- **WHEN** the last registered member unregisters
- **THEN** the store holds no registrations document

### Requirement: Members list their courses in the channel
`/course-list` SHALL reply `list` with the codes that the member registered in the command's
channel, each once, sorted and separated by `, `, comparing member IDs exactly; a list too long for
one message SHALL end with `...` within 2000 characters.

#### Scenario: List
- **WHEN** a member registered `CE162A002` and `CE162A001` in channel 5 and `CE162A003` in channel 6
- **THEN** `/course-list` in channel 5 lists `CE162A001, CE162A002`

#### Scenario: Similar IDs
- **WHEN** another member, whose ID contains the member's, registered a course in channel 5
- **THEN** the member's list leaves that course out

#### Scenario: Nothing registered
- **WHEN** the member registered nothing in the channel
- **THEN** the reply is `list` with no courses, as v3's

#### Scenario: Long list
- **WHEN** the member registered 100 courses in the channel
- **THEN** the reply fits in 2000 characters and ends with `...`

### Requirement: Commands keep v3's names and answer in the member's locale
The plugin SHALL register guild commands `course-add` and `course-remove`, each with a required
string option `id`, and `course-list`, for every member, with v3's English descriptions and zh-TW
translations. The command tree's ephemeral deferral SHALL be edited into the reply, in the member's
locale when the plugin has its files, else in en-US.

#### Scenario: Command payload
- **WHEN** the guild payload is built
- **THEN** it holds the three commands with the golden names, descriptions, options and zh-TW
  descriptions, without default member permissions

#### Scenario: Replies by locale
- **WHEN** a member whose locale is zh-TW, en-US or ja runs the commands
- **THEN** the replies are the golden zh-TW texts, or v3's English ones for en-US and ja

### Requirement: Registrations are kept as v3's document
Registrations SHALL be one document in the store (namespace `NtustCourseWatch`, key
`user_record_map`): `{"<code>": {"<channel ID>": ["<user ID>", ...]}}`, IDs as decimal text, as
v3's MongoDB value, read with v3's duplicates. A document of another shape SHALL raise and never be
overwritten. Changes SHALL run under the document's lock and write only when they change it.

#### Scenario: v3's document
- **WHEN** the store holds v3's document with a member listed twice
- **THEN** the member is registered once, and `/course-list` lists the course once

#### Scenario: Broken document
- **WHEN** the document is not v3's shape (a list, a channel key that is not a number, a user that
  is not text)
- **THEN** reading it raises, a registration leaves it unchanged, and no course is checked

#### Scenario: Stored codes
- **WHEN** the document holds `ce162a001 ` and `CE162A001`, an empty code and a one-letter code
- **THEN** both read as `CE162A001`, whose registrations are merged, and the others are left out
  and never asked about

#### Scenario: Concurrent registrations
- **WHEN** two members register at the same time
- **THEN** both are registered

### Requirement: Course seats come from NTUST's course query
A course's state SHALL come from one `POST https://querycourse.ntust.edu.tw/QueryCourse/api//courses`
with the semester and the code in the course query site's body, over TLS without Python's strict
X.509 checks: the last entry of the answer whose `CourseNo` is the code. It has seats when
`ChooseStudent` is below `Restrict2` read as v3's `toIntOrNull()`, a missing number counting as 0.

#### Scenario: Request
- **WHEN** the plugin asks about `CE162A001` in semester `1151`
- **THEN** the request is the golden JSON body with `content-type: application/json; charset=utf-8`
  and follows no redirect

#### Scenario: Answer
- **WHEN** the answer is a copy of NTUST's answer, which lists the course twice and other courses
- **THEN** the course is the last entry with its code, with its name, its count and its limit

#### Scenario: Limits
- **WHEN** `Restrict2` is `"60"`, `"0"`, `""`, `"abc"`, `"99999999999"`, 60 in digits outside the
  BMP, the number 60 or 60.0
- **THEN** the limit is 60, 0, 0, 0, 0, 0, 60 or 0, and a course without seats is full

#### Scenario: Course missing from the answer
- **WHEN** no entry has the code
- **THEN** the course is unknown

#### Scenario: Refused answers
- **WHEN** NTUST answers with status 500 or a redirect, text that is not JSON or not a list, or the
  course's entry without a count
- **THEN** asking raises an error that names the status or the answer

#### Scenario: NTUST's certificates
- **WHEN** the plugin asks over HTTPS
- **THEN** the certificate and the host name are verified, without Python's strict X.509 checks and
  with TWCA's intermediate certificate, through the context shared with NtustAnnouncements

### Requirement: Registered courses are checked in turn from READY
From READY until the plugin unloads, a task SHALL check one registered course per step, the codes
in turn in sorted order, reading the registrations at each step, a step starting `interval` seconds
after the previous one started and at least 0.1 seconds after it ended. Before `start`, or while
nothing is registered, no course SHALL be asked about. A reload SHALL replace the task.

#### Scenario: Start at READY
- **WHEN** the plugin loads before READY with a course registered
- **THEN** nothing is asked until READY, then the course is asked about at once

#### Scenario: Before the start
- **WHEN** `start` has not passed
- **THEN** no course is asked about, until it passes

#### Scenario: Nothing registered
- **WHEN** no course is registered
- **THEN** nothing is asked, until a member registers a course

#### Scenario: Courses in turn
- **WHEN** `CE162A002` and `CE162A001` are registered
- **THEN** the steps ask about `CE162A001`, `CE162A002`, `CE162A001`, each 1.5 seconds after the
  previous one started

#### Scenario: Slow answers
- **WHEN** an answer takes 2 seconds
- **THEN** the next step starts 0.1 seconds after it

#### Scenario: Unload and reload
- **WHEN** the plugin unloads, or reloads
- **THEN** its task ends and nothing more is asked or posted by it; a reload starts a new task

### Requirement: Channels hear about courses with seats
When a checked course has seats, each channel that registered it SHALL get the default locale's
`alert.available`, with v3's second of the minute, its members' mentions and the course's name and
code, pinging those members only, at most once per `alert-interval` for the channel and the course.
A post too long for 2000 characters SHALL be split between its mentions.

#### Scenario: Seats
- **WHEN** `CE162A001` has seats and two members registered it in channel 5
- **THEN** channel 5 gets the golden alert, pinging those two members and nobody else

#### Scenario: Seats again
- **WHEN** the course still has seats at the next steps
- **THEN** the channel hears about it again only once `alert-interval` has passed since its last
  alert

#### Scenario: Many members
- **WHEN** 120 members registered the course in the channel
- **THEN** the alert comes in several posts of at most 2000 characters, each pinging its own
  members, every member once

#### Scenario: Brackets in a name
- **WHEN** the course's name holds `[`, `]` or `\`
- **THEN** they are escaped, so the link keeps its text

### Requirement: Channels hear once when a course fills
When a course that had seats at its previous check is full, each channel that registered it and got
an available alert since its last full alert SHALL get the default locale's `alert.full` with the
course's name and code, pinging nobody.

#### Scenario: Became full
- **WHEN** a course that had seats, about which channel 5 got an alert, is full at its next check
- **THEN** channel 5 gets the golden full alert, which pings nobody

#### Scenario: Seats come and go
- **WHEN** the course alternates between seats and full faster than `alert-interval`
- **THEN** each available alert is followed by at most one full alert

#### Scenario: Missing from one answer
- **WHEN** a course that had seats is missing from the next answer and full at the one after
- **THEN** the channels that heard about its seats get the full alert

#### Scenario: Full at the first check
- **WHEN** a course is full at its first check
- **THEN** no channel hears about it

### Requirement: Failures are logged without flooding
Failed requests (per course code), refused posts (per channel), a broken registrations document and
other errors of a step SHALL be logged once per kind of failure and episode, with one line when it
works again, the first unexpected error of an episode with its traceback; the next step comes as
usual. An error that ends the loop SHALL be logged. A channel that Discord no longer knows (404)
SHALL have its registrations forgotten, logged once; other refusals keep them.

#### Scenario: Failing course query
- **WHEN** NTUST answers 500 at several steps, then answers again
- **THEN** one warning names the status and the code, and an info line says that the course query
  works again

#### Scenario: Failing codes among several
- **WHEN** one or two of four registered codes fail at every step
- **THEN** one warning names each failing code, and the others' answers end no episode

#### Scenario: Deleted channel
- **WHEN** Discord answers an alert's posts with 404
- **THEN** the channel's registrations are forgotten and one info line names the channel

#### Scenario: Refused posts
- **WHEN** Discord refuses a channel's alerts with 403 several times, then takes them again
- **THEN** one warning names the channel, its registrations stay, and an info line says that it
  takes the alerts again

#### Scenario: Unexpected errors
- **WHEN** a step raises an unexpected error once, or at every step
- **THEN** the error is logged with its traceback once per episode, and the next step comes

#### Scenario: The loop ends
- **WHEN** an error ends the loop, as a session that cannot open
- **THEN** the error is logged with its traceback
