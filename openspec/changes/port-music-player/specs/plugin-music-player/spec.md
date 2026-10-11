# Spec Delta

## Purpose

A per-guild music player: members bring the bot into voice, queue songs and control them from
ephemeral panels, while a Lavalink node plays the audio.

## ADDED Requirements

### Requirement: The plugin installs as MusicPlayer
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `MusicPlayer`, pointing to `xincord.plugins.music_player`, with no dependencies (v3's
AudioAPI folds into the plugin's requirements) and the voice states intent. Loading SHALL write the
bundled `config.yaml` and the zh-TW (default) and en-US `lang/` files to `plugins/MusicPlayer/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `MusicPlayer` enabled
- **THEN** it returns `MusicPlayer` from `xincord.plugins.music_player` with no dependencies and
  the voice states intent

#### Scenario: First load writes the config and the lang files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/MusicPlayer/` holds the bundled `config.yaml` and the zh-TW and en-US lang files

### Requirement: The config names the node, the player's defaults, the errors and the emojis
`config.yaml` SHALL hold `lavalink` (`host`, `port` 1 to 65535, a required non-blank `password`),
`player.default_volume` (0 to 100, v3's 40), `player.auto_leave_timeout` (milliseconds idle before
leaving, at least 0, v3's 600000, 0 for never), `messages.show_detailed_errors` (v3's true) and
`emojis` (v3's nine application emoji names and four for the buttons). Invalid values SHALL keep
the plugin from loading with the key named, the password never shown.

#### Scenario: v3 config file with a node
- **WHEN** `config.yaml` is v3's with a `lavalink` section added
- **THEN** the plugin loads with v3's volume, timeout, error setting and emoji names, and warns
  about each key that v3 never used, `engines` included

#### Scenario: Bundled config waits for the password
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it does not load, and the error names `lavalink.password`

#### Scenario: Invalid values
- **WHEN** `player.default_volume` is 101, `player.auto_leave_timeout` is -1, `lavalink.port` is 0
  or an emoji name has a space
- **THEN** the plugin does not load, and the error names the key

#### Scenario: The password stays hidden
- **WHEN** the `lavalink` section is invalid and holds a password
- **THEN** the error does not contain the password

### Requirement: Queries become Lavalink identifiers as in v3
A query SHALL be passed to the node as written when it starts with `http` or contains
`youtube.com`, `youtu.be`, `soundcloud.com` or `spotify.com`, and SHALL otherwise be searched on
YouTube as `ytsearch:<query>`, as v3 did.

#### Scenario: Searches and links
- **WHEN** the queries are `never gonna`, `https://youtu.be/x`, `youtu.be/x`,
  `www.youtube.com/watch?v=x`, `soundcloud.com/a/b`, `open.spotify.com/track/x`, `httpfoo` and
  `scsearch:foo`
- **THEN** the identifiers are `ytsearch:never gonna`, the five links and `httpfoo` as written,
  and `ytsearch:scsearch:foo`

### Requirement: The history keeps v3's order of play
Each guild SHALL keep v3's history: the songs in order with the index of the current one. A song
added while nothing plays SHALL start (v3 only started a first song); skip SHALL go forward;
previous SHALL restart the current song after 5 seconds or without a previous one, and else go
back one; shuffle SHALL reorder the upcoming songs only; the history SHALL hold 240 songs at most,
dropping played songs first and refusing the rest.

#### Scenario: First and later songs
- **WHEN** a song is added to an empty history, then another while the first plays
- **THEN** the first starts at index 0 and the second waits after it

#### Scenario: A song added after the end
- **WHEN** the last song ended and a song is added
- **THEN** the new song starts and the ended ones stay behind it

#### Scenario: Skip
- **WHEN** skip runs with an upcoming song, then at the last song
- **THEN** the next song starts, then skip reports that there is none

#### Scenario: Previous
- **WHEN** previous runs at 5000 ms or later, at index 0, and before 5000 ms after another song
- **THEN** the current song restarts twice, then the previous song starts and the index goes back

#### Scenario: Shuffle
- **WHEN** shuffle runs with one upcoming song, then with several
- **THEN** it refuses, then reorders the upcoming songs and leaves the played ones and the current
  one in place

#### Scenario: Full history
- **WHEN** songs are added past 240
- **THEN** played songs leave first with the index following, and the songs that do not fit are
  refused and counted

### Requirement: Playback follows the node's events
When the node ends the current song as finished, the song SHALL play again in single-song loop
mode, and otherwise the next song SHALL start, or the player SHALL go idle at the end. A song that
failed to load or got stuck SHALL be followed by the next one in either mode and logged. An end
event of a song that is no longer the current one, or a stopped or replaced song, SHALL change
nothing.

#### Scenario: Sequential and loop
- **WHEN** the current song finishes in sequential mode, then in single-song loop mode
- **THEN** the next song starts, then the same song starts again

#### Scenario: End of the list
- **WHEN** the last song finishes
- **THEN** nothing starts and the player is idle

#### Scenario: Failed and stuck songs
- **WHEN** a song fails to load or gets stuck, in either mode
- **THEN** the next song starts, and a warning names the song

#### Scenario: Stale events
- **WHEN** an end event names a song that a skip already replaced, or reports a stopped song
- **THEN** nothing changes

### Requirement: Panels show v3's track layout
Panels SHALL render v3's templates with v3's values: the title, author, link and thumbnail (the
node's artwork, else YouTube's image for a YouTube link, else v3's default), the requester's
username and avatar, the progress bar (play or pause emoji, elapsed time, 15 emojis, length;
`live` for streams), the colour (green while playing, gold otherwise) and the loop mode's emoji.
Times SHALL read as v3's `mm:ss` or `hh:mm:ss`.

#### Scenario: Times
- **WHEN** times of 0, 59999, 60000, 3599999, 3600000 and 360000000 ms are shown
- **THEN** they read `00:00`, `00:59`, `01:00`, `59:59`, `01:00:00` and `100:00:00`

#### Scenario: Progress bar
- **WHEN** the position is 0, half the length, the length and past the length
- **THEN** the bar shows 0, 7, 13 and 13 white segments between its ends, the last two with the
  white end

#### Scenario: Streams
- **WHEN** the song is a stream
- **THEN** the bar is the play or pause emoji and `live`

#### Scenario: Thumbnails
- **WHEN** a song has the node's artwork, is a YouTube link without artwork, or neither
- **THEN** the thumbnail is the artwork, `https://img.youtube.com/vi/<id>/maxresdefault.jpg`, or
  v3's default image

#### Scenario: Golden panels
- **WHEN** the `play` and `volume` templates render in en-US and zh-TW
- **THEN** the footer and the title are v3's text in each locale, with v3's colours and buttons

### Requirement: The queue view fits Discord's limits
The `queue` panel SHALL list the upcoming songs as v3 did, numbered from 1, ten lines per field
named `—`, each line `n. **title** | author` with the length in brackets (`live-length` for
streams), in colour `0x9bd9d5`, and SHALL stop at Discord's limits (1024 characters per field, 25
fields, 4000 characters in all) with a last line counting the songs left out.

#### Scenario: Short queue
- **WHEN** three songs are upcoming
- **THEN** one field lists them numbered 1 to 3 in v3's format

#### Scenario: Long queue
- **WHEN** 500 songs with long titles are upcoming
- **THEN** every field stays within 1024 characters, there are at most 25 fields, the embed stays
  within 4000 characters, and the last line counts the songs not shown

### Requirement: Songs load and play through a Lavalink node
The plugin SHALL connect to the configured node with lavalink.py from READY, load identifiers
there (a song, a playlist, a search, nothing, or the node's error), play one song at a time on each
guild's player with the guild's volume, pause, resume, change the volume and stop it, and forward
the bot's voice updates to the node with the voice channel's ID, also after the bot moved. A
request that the node does not answer within 15 seconds SHALL fail as unavailable.

#### Scenario: Load results
- **WHEN** the node answers a song, a playlist, a search, nothing and an error
- **THEN** the plugin reads each as that kind, with the songs' titles, authors, links, lengths and
  artwork, and the error's message

#### Scenario: No node
- **WHEN** a song is loaded while no node is connected
- **THEN** the load fails as unavailable

#### Scenario: Player updates
- **WHEN** a guild's player plays a song, pauses, changes the volume and stops
- **THEN** the node receives each update for that guild, and the song's end event names that start

#### Scenario: Voice updates
- **WHEN** the bot joins a channel, then moves to another
- **THEN** the node receives the session, the voice server and each channel's ID

#### Scenario: Refused voice states
- **WHEN** the gateway refuses the voice state of a new connection, or of a leave while the link
  closes
- **THEN** the connection is released all the same, and the other guilds still leave before the
  client closes

#### Scenario: A leave answered late or deleted slowly
- **WHEN** Discord answers a leave after the bot began connecting again, or the node is slow to
  delete the left guild's player while the bot connects again
- **THEN** the new connection keeps its player, and the plugin hears of the leave once, before the
  new connection

#### Scenario: Connections that a new gateway session dropped
- **WHEN** READY came again and discord.py no longer holds a guild's connection
- **THEN** the link leaves that guild's voice and releases its player, and the other guilds stay

#### Scenario: A node that does not answer
- **WHEN** the node takes a load and answers nothing for 15 seconds
- **THEN** the load fails as unavailable and the node's connection stays

### Requirement: Commands keep v3's names, options and localizations
The plugin SHALL register v3's eleven guild commands for every member, with v3's English
descriptions and the en-US and zh-TW names and descriptions of `register.yaml`: `play` with the
required `query` (at most 500 characters, autocompleted), `skip` with the optional `count` (1 to
50) and `volume` with the required `level` (0 to 100, autocompleted). The command tree SHALL defer
them ephemerally.

#### Scenario: Command payloads
- **WHEN** the guild payload is built
- **THEN** it holds the eleven commands with v3's names, descriptions, options, limits and
  localizations, and no default permissions

### Requirement: Members bring the bot into voice and send it away
`/join` SHALL connect the bot to the member's voice channel, or move it there, and delete the
response; a member outside voice gets `join-voice-first`, one in a stage channel
`voice-channel-not-found`, and a channel the bot cannot join (no Connect, or full without Move
Members) `cannot-connect`. `/disconnect` SHALL stop the player, leave and delete the response, or
answer `not-connected`.

#### Scenario: Join
- **WHEN** a member in a voice channel runs `/join`, the bot elsewhere or not connected
- **THEN** the bot connects to or moves to that channel and the response is deleted

#### Scenario: Join refused
- **WHEN** the member is outside voice, in a stage channel, or in a channel the bot cannot join
- **THEN** the reply is `join-voice-first`, `voice-channel-not-found` or `cannot-connect`

#### Scenario: Disconnect
- **WHEN** `/disconnect` runs while connected, then while not connected
- **THEN** the history is cleared, the bot leaves and the response is deleted, then the reply is
  `not-connected`

### Requirement: Play queues songs and starts them
`/play query` SHALL check the member's voice channel (`play-join-voice-first`,
`voice-channel-not-found`), the bot's Connect permission when it must connect
(`no-connect-permission`) and a blank query (`empty-query`), connect, load the identifier and add
the song, a search's first song or a playlist's songs, then show the `play` panel of the first one;
nothing found, an error, an empty playlist, a full history, no node or a bot that left voice
meanwhile get their reply.

#### Scenario: Play a search
- **WHEN** a member in voice runs `/play query:never gonna` and the bot is not connected
- **THEN** the bot connects, the search's first song starts, and the response is its `play` panel

#### Scenario: Play a playlist
- **WHEN** the query is a playlist link while a song plays
- **THEN** all its songs are queued after it and the panel shows the playlist's first song

#### Scenario: Another channel
- **WHEN** the bot is connected to another channel
- **THEN** the song joins that session and the bot does not move

#### Scenario: The bot left during the load
- **WHEN** the bot leaves voice while the query loads, or while its songs wait for the player
- **THEN** the reply is `not-connected` and nothing is added

#### Scenario: Refusals
- **WHEN** the member is outside voice or in a stage channel, the bot cannot connect, the query is
  blank, the node finds nothing, fails, answers an empty playlist, the history is full, or no node
  is connected
- **THEN** the reply is `play-join-voice-first`, `voice-channel-not-found`,
  `no-connect-permission`, `empty-query`, `no-matches`, `load-failed`, `empty-playlist`,
  `queue-full` or `node-unavailable`

### Requirement: Members control playback with v3's replies
`/pause` and `/resume` SHALL pause or resume the current song and show the `pause` or `resume`
panel, or answer `nothing-playing`, `already-paused` or `already-playing`. `/stop` SHALL clear the
history, unpause, leave and delete the response, or answer `nothing-playing`. `/skip count` SHALL
skip that many songs and show the `skip` panel, end the list when it skips past the last song
(`skipped-to-end`), or answer `nothing-playing` or `skip-too-many`.

#### Scenario: Pause and resume
- **WHEN** `/pause` runs twice and `/resume` twice while a song plays
- **THEN** the replies are the `pause` panel, `already-paused`, the `resume` panel and
  `already-playing`

#### Scenario: Songs gone during a command
- **WHEN** `/pause` and `/resume` wait for the player, or the node answers a pause, while the bot
  leaves voice
- **THEN** the replies are `nothing-playing`

#### Scenario: Stop
- **WHEN** `/stop` runs while a paused song plays, then while nothing plays
- **THEN** the history is cleared, the player unpaused, the bot leaves and the response is deleted,
  then the reply is `nothing-playing`

#### Scenario: Skip
- **WHEN** `/skip count:2` runs with four songs from the first, then `count:5`, then `count:2` at
  the third song of four
- **THEN** the third song plays in the `skip` panel, then `skip-too-many` names 4, then the list
  ends with `skipped-to-end`

### Requirement: Volume, queue, shuffle and now playing keep v3's replies
`/volume level` SHALL set the guild's volume, kept until the plugin unloads and used by every song,
and show the `volume` panel with the levels before and after. `/queue` SHALL show the `queue` panel,
or `empty-playlist` without upcoming songs. `/shuffle` SHALL reorder the upcoming songs and answer
`shuffled` with their count, or `shuffle-join-voice` or `shuffle-too-few`. `/now-playing` SHALL show
the `now-playing` panel, or `nothing-playing`.

#### Scenario: Volume
- **WHEN** `/volume level:70` runs at the default volume, with and without a connected player
- **THEN** the panel shows 40 and 70, the player's volume is 70 when connected, and the next song
  plays at 70

#### Scenario: Queue
- **WHEN** `/queue` runs with two upcoming songs, then with none
- **THEN** the reply is the `queue` panel with both songs, then `empty-playlist`

#### Scenario: Shuffle
- **WHEN** `/shuffle` runs outside voice, with one upcoming song, and with three
- **THEN** the replies are `shuffle-join-voice`, `shuffle-too-few` and `shuffled` with 3

#### Scenario: Now playing
- **WHEN** `/now-playing` runs while a song plays, then while nothing plays
- **THEN** the reply is the `now-playing` panel, then `nothing-playing`

### Requirement: Autocomplete suggests songs and the current volume
The `query` option SHALL suggest nothing under two characters and otherwise up to ten songs of a
YouTube search through the node, named `title | author` within 100 characters and valued by their
link (links over 100 characters left out), cached per input (the 100 latest) and answered within
2.5 seconds or empty. The `level` option SHALL suggest the guild's volume as `current-volume`.

#### Scenario: Song suggestions
- **WHEN** the member types `n`, then `never gonna` twice
- **THEN** nothing is suggested, then the search's songs, the second time from the cache without
  asking the node

#### Scenario: Slow or missing node
- **WHEN** the search takes longer than 2.5 seconds, fails, or no node is connected
- **THEN** nothing is suggested

#### Scenario: Volume suggestion
- **WHEN** the member types in `level`
- **THEN** the only suggestion is `current-volume` with the guild's volume

### Requirement: Panels refresh themselves and expire
A panel SHALL be edited every 5 seconds with the current song in its template while a song plays
(the queue panel with the current queue), and deleted once 60 seconds passed since its last
interaction; a press SHALL restart the 60 seconds. A member SHALL have one panel: a new one deletes
the previous one. Panels of a guild whose player stops SHALL be deleted; a refused edit, a deletion
or an unload SHALL end the refreshes.

#### Scenario: Refresh and expiry
- **WHEN** a panel is shown and a song plays for 70 seconds
- **THEN** it is edited every 5 seconds with the current song and deleted after 60 seconds

#### Scenario: A press extends the panel
- **WHEN** a button of the panel is pressed after 50 seconds
- **THEN** the panel stays until 60 seconds after the press

#### Scenario: One panel per member
- **WHEN** the member opens a second panel
- **THEN** the first one is deleted and only the second refreshes

#### Scenario: Idle and stopped players
- **WHEN** nothing plays, then the bot leaves
- **THEN** the panel is not edited, then it is deleted and its refresh ends

#### Scenario: Refused edits and unload
- **WHEN** Discord refuses a refresh, or the plugin unloads
- **THEN** the panel's refresh ends

#### Scenario: Queue panel refresh
- **WHEN** a queue panel refreshes after a skip
- **THEN** it shows the new song and the shorter queue

#### Scenario: Panels at once and after the unload
- **WHEN** a member's command opens a panel while their previous one is still being deleted, or a
  command opens one after the unload
- **THEN** the newest panel is the member's only refreshing one, and one opened after the unload is
  not tracked

### Requirement: Panel buttons control the guild's player
Presses of v3's IDs (`musicplayer@a:<action>`) and new IDs SHALL be acknowledged at once and act on
the guild's player: a member outside voice gets `button-join-voice` in the panel; `previous`,
`pause-resume`, `skip` and `loop` show the `now-playing` panel, or `previous-no-song`,
`previous-idle`, `nothing-playing` or `no-more-songs`; `disconnect` stops, leaves and deletes the
panel, or shows `not-connected`. Other actions get no response.

#### Scenario: v3 and new IDs
- **WHEN** `musicplayer@a:skip` and `music_player:1:a=skip` are pressed
- **THEN** both skip to the next song and show it in the panel

#### Scenario: Member outside voice
- **WHEN** a member outside voice presses a button
- **THEN** the panel says `button-join-voice` and the player does not change

#### Scenario: Previous, pause and loop
- **WHEN** `previous` is pressed at 7 seconds, `pause-resume` twice and `loop` twice
- **THEN** the song restarts unpaused, pauses and resumes, and the loop emoji changes to single and
  back, each shown in the panel

#### Scenario: Nothing to do
- **WHEN** `pause-resume` is pressed while nothing plays, `skip` at the last song, `previous` with no
  song or while idle, and `disconnect` while not connected
- **THEN** the panel says `nothing-playing`, `no-more-songs`, `previous-no-song`, `previous-idle`
  and `not-connected`

#### Scenario: Two quick presses
- **WHEN** `pause-resume` is pressed twice while the node answers the first press
- **THEN** the song pauses, then resumes

#### Scenario: Songs gone during a press
- **WHEN** `pause-resume` and `previous` wait for the player while the bot leaves voice
- **THEN** the panels say `nothing-playing` and `previous-no-song`, and no error is logged

#### Scenario: Disconnect
- **WHEN** `disconnect` is pressed while connected
- **THEN** the history is cleared, the bot leaves and the panel is deleted

#### Scenario: Unknown action
- **WHEN** an ID with another action is pressed
- **THEN** nothing is sent

### Requirement: The bot leaves when idle, disconnected or removed
The bot SHALL leave voice once nothing played for `player.auto_leave_timeout` milliseconds (never
when 0), unless a song starts first. When Discord disconnects the bot, the guild's history SHALL be
cleared and its panels deleted; when the bot leaves a guild, its state SHALL be forgotten. At READY
the bot SHALL leave the voice connections that a new gateway session made discord.py forget.

#### Scenario: Idle timeout
- **WHEN** the last song ends and 600000 ms pass, or a song starts before
- **THEN** the bot leaves and the panels are deleted, or stays

#### Scenario: No timeout
- **WHEN** `player.auto_leave_timeout` is 0
- **THEN** the bot stays while idle

#### Scenario: Disconnected by someone else
- **WHEN** a moderator disconnects the bot
- **THEN** the history is cleared, the player is destroyed and the panels are deleted

#### Scenario: Guild removed
- **WHEN** the bot leaves the guild
- **THEN** the guild's player, history, volume and panels are forgotten

#### Scenario: A new gateway session
- **WHEN** READY comes again after discord.py forgot the bot's voice connections, also while an
  idle leave is due
- **THEN** the bot leaves them as after a disconnection, and the idle leave ends without an error

### Requirement: The node and the emojis load from READY, and unloading leaves voice
Nothing SHALL connect before READY. At READY the plugin SHALL connect to the node and read the
application's emojis: a configured name found becomes that emoji, a missing one a Unicode emoji,
with one warning naming the missing names (or the failed request). Unloading SHALL stop every
player, leave voice, delete the panels and close the node's client; commands before the node
connects answer `node-unavailable`.

#### Scenario: Offline load
- **WHEN** the plugin loads and unloads without READY
- **THEN** no node client is created and nothing is requested

#### Scenario: Emojis
- **WHEN** READY comes and the application has some of the configured emojis
- **THEN** panels use them, Unicode emojis stand for the others, and one warning names the missing
  ones

#### Scenario: Unload
- **WHEN** the plugin unloads while the bot plays in a guild
- **THEN** the bot leaves, the panels are deleted and the node's client is closed

### Requirement: Errors are reported as v3 did
An unexpected error in a command or a press SHALL be logged with its traceback, URLs cut to their
origin, and answered with `command-error` or `button-error` and the error's text, or with
`command-error-hidden` or `button-error-hidden` when `messages.show_detailed_errors` is false.

#### Scenario: Detailed errors
- **WHEN** a command fails with an unexpected error
- **THEN** the reply is `command-error` with the error's text and the log has the traceback

#### Scenario: Hidden details
- **WHEN** `messages.show_detailed_errors` is false and a press fails
- **THEN** the panel says `button-error-hidden`
