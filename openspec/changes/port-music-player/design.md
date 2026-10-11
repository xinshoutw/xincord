## Context

v3's MusicPlayer (`docs/porting/analysis/inventory/MusicPlayer.md`) plays music in voice channels
with lavaplayer, youtube-source and LavaSrc inside the JVM, JDA's audio manager and JDAVE for DAVE.
Python has no lavaplayer: decision B14 runs a Lavalink 4.2+ node (lavaplayer, youtube-source and
LavaSrc as a service, DAVE since 4.2.0) and drives it with lavalink.py; B16 runs it under docker
compose on the owner's arm64 Mac (F2). The plugin keeps v3's commands, texts, templates, panels,
buttons and history model; only the audio moves to the node.

Facts checked on 2026-10-11:

- lavalink.py 5.11.1 (2026-10-06, MIT, sdist only, `aiohttp>=3.9,<4`) sends the voice state's
  `channelId` that Lavalink 4.2 requires for DAVE (since 5.10.0). Its `DefaultPlayer` starts the
  next song of its own queue at each end event; the plugin's player class replaces that handling.
  It keeps `current` after a song ends, stops reconnecting after a 401, and runs event hooks as
  unawaited tasks; the player's `handle_event` runs in the WebSocket message's task, in order.
  pyright strict reports only `reportMissingTypeStubs` for it.
- Lavalink 4.2.2 (2026-03-06) is the latest release; its Ubuntu image (`eclipse-temurin:18-jre-
  jammy`, glibc 2.35, which libdave needs; the Alpine variant has musl) ships arm64, amd64 and
  armv7 and has `curl`. On this Mac (OrbStack, arm64) it started in about 10 seconds with
  youtube-source 1.18.2 and LavaSrc 4.8.3 (the latest releases) downloaded at start; `/version`
  needs the password (401 without); a `ytsearch:` load answered a `search` with YouTube's songs
  (`artworkUrl` null), and with Spotify and HTTP off a Spotify link and an `http://` link loaded
  `empty`.
- discord.py 2.7.1 checks for davey only in its own `VoiceClient`: a `VoiceProtocol` subclass that
  hands the voice updates to Lavalink needs neither davey nor PyNaCl in the bot.

## Goals / Non-Goals

**Goals:**

- v3's eleven commands, replies, panels, buttons (v3's IDs too), autocompletes and history model,
  with its defects fixed (see "v3 behaved differently").
- Audio through a Lavalink node with DAVE, behind narrow Protocols so that the cog's tests use
  fakes and the adapter is tested against a local fake node through the real lavalink.py.
- A `lavalink` service in compose that starts on the owner's Mac, with its secrets out of git.

**Non-Goals:**

- v3's in-process audio stack and its unused config keys (proposal, "Out of scope").
- Keeping playback across a plugin reload (the node's session resume), uploading application
  emojis, a DJ role, seeking, a queue loop or autoplay (v3 had none).

## Decisions

### Package and bundled files

`xincord.plugins.music_player`, entry point `MusicPlayer`, `INTENTS =
discord.Intents(voice_states=True)` (v3's `GUILD_VOICE_STATES`; discord.py's default, declared):
`member.voice` comes from the guild's voice states, which need no member cache. No dependency: v3's
AudioAPI only gated loading (B12). `DEFAULT_LOCALE = "zh-TW"`, v3's template default; commands
keep v3's English base texts with en-US and zh-TW localizations.

Modules: `audio.py` (the value types and Protocols), `history.py` (pure history), `display.py`
(pure values of the panels: times, the bar, thumbnails, the queue embed, the identifier rule),
`emojis.py` (names to emojis, fallbacks), `session.py` (one guild's history on its player),
`panels.py` (the refresh loops), `node.py` (the lavalink.py adapter and the voice protocol),
`texts.py`, `config.py` and `cog.py` (commands, buttons, autocompletes, listeners).

`lang/<locale>/`: v3's `register.yaml` and seven templates (final newlines added; the four emoji
IDs that v3 hard-coded in the buttons replaced by placeholders, see "Emojis") and a new `text.yaml`
with every text v3 hard-coded: zh-TW holds v3's, en-US English translations (Ticket's convention).
v3's `images/` are not shipped: the operator uploads them as application emojis, as for v3.

### Config

```yaml
lavalink: {host: lavalink, port: 2333, password: ""}   # new; the password is required
player: {default_volume: 40, auto_leave_timeout: 600000}
messages: {show_detailed_errors: true}
emojis: {<v3's nine names>, media_previous, media_pause_resume, media_next, media_disconnect}
```

Kept: the keys that had an effect in v3 (`player.default_volume`, `messages.show_detailed_errors`,
`emojis`) and `player.auto_leave_timeout`, which v3 declared for an idle leave that never ran (bug
B10, now built; 0 means never). `lavalink.password` is required and the bundled file leaves it
empty, so the plugin waits for the operator (Economy's `admin_id`); the models hide their input in
validation errors. Not fields: every key v3 never read (`command_message_acknowledges`,
`engines.youtube`, `engines.soundcloud`, `player.max_queue_size`, `player.search_timeout`,
`player.playback`, `player.cache`, `messages.announce_new_track`, `messages.use_enhanced_embeds`,
`messages.embeds`, `features`, `performance`, `cache`, `developer`) and `engines.spotify`, which
moves to the node (below); v3's files load and the core warns about each.

### The node, lavalink.py and the Protocols

`audio.py` holds the plugin's own types: `Track` (encoded string, title, author, link, identifier,
length, seekable, stream, artwork), `Loaded` (kind, songs, error), `EndReason` and the Protocols
`Link` (load an identifier, a guild's `Player`, the voice protocol factory, close) and `Player`
(play a song with a start number and the volume, pause, set the volume, stop, position). The cog
and the session only see these; tests give fakes.

`node.py` implements them with lavalink.py: `open_link(bot, config, listener)` creates the
`lavalink.Client` after READY with the bot's ID and adds the configured node (region `default`);
`load` turns `LoadResult` into `Loaded` and `ClientError` (no node) into `NodeUnavailable`; the
player class subclasses `DefaultPlayer`, keeps lavalink.py's position and pause state, and replaces
`handle_event`, which reports the end, exception, stuck and voice-closed events to the plugin with
the start number that `play` stored in the song's `extra`. Each event is handled in the message's
order under the guild's lock; a number that is not the current start is stale and ignored, which
also settles a skip that crosses a natural end.

`LavalinkVoice(discord.VoiceProtocol)`: `connect` creates the guild's player and sends the voice
state (not deafened or muted, as v3); voice state and server updates go to
`Client.voice_update_handler`; a state update without a channel destroys the player, removes the
protocol from discord.py's cache and tells the plugin once; a move to another channel drops the
cached session ID first, so that lavalink.py sends the new `channelId` (it otherwise sends it only
when the session changes). `disconnect` leaves and does the same.

The lavalink.py client lives from READY to the unload; a wrong password stops lavalink.py's
reconnects until a reload (its warning says so); commands answer `node-unavailable` while no node
is connected.

### History and session

`history.History` is v3's `HistoryIndexManager` as a pure state machine over entries (a song and
its requester: ID, display name, username and avatar URL, kept by the plugin instead of the node's
`userData`): `add` returns the entry to start when nothing plays (v3 only started a first song,
bug B1), `skip`, `previous(position)` with v3's 5000 ms, `shuffle(random)` of the upcoming entries,
`finished(mode)` and `failed()` (the next entry, the same in single loop, never the same after a
failure, bug B9), and the cap of 240 that drops played entries first and refuses the rest, counted
(bug B8). Loop mode toggles sequential and single-song loop, as v3's button.

`session.Session` (one per guild, kept until the plugin unloads or the guild is removed) holds the
history, the loop mode, the volume (v3's per-guild volume, kept across `/stop`) and the current
start; each change runs under its `asyncio.Lock`, starts songs unpaused at the session's volume
(bugs B2 and B22), and tells the cog when it becomes idle or busy (the idle leave).

### Commands and replies

Eleven guild commands built in `setup` from `COMMANDS` with the cog's bound methods, v3's base
English descriptions, `rename`/`describe` from `register.yaml` (`now_playing` is the YAML key) and
no default permissions. The tree defers them ephemerally (v3's core); replies edit the deferral or
delete it, as v3's `editOriginal` and `deleteOriginal`. Texts come from `text.yaml` in the
member's locale, falling back to zh-TW (v3's for everyone); templates fall back to zh-TW, as v3's
`MessageCreator`. A panel's values are the member's `actor_values` and the music keys of v3
(`music_player@song_*`, `player_*`, the misspelt `player_currnet_loop_mode_emoji` kept), rendered
once per edit.

v3's checks, in v3's order: `/join` and `/play` need a voice channel that is not a stage channel;
`/play` checks Connect only when the bot must connect (v3 also checked it when connected elsewhere,
bug B27); `/join` checks Connect and a full channel without Move Members, which JDA checked;
`/shuffle` and the buttons need any voice channel; the others need nothing (P3). `/play` while the
bot is elsewhere joins that session (P4).

### Panels

`panels.Panels` keeps one panel per member (v3's per user), each a task: every 5 seconds it renders
the panel's template with the guild's current song when one plays (the queue panel with the
current queue, bug B6; the volume panel with its two levels) and edits it through the latest
interaction of the panel; once 60 seconds passed since that interaction it deletes the panel. A
press switches the panel to the press's interaction, which restarts the 60 seconds and renews the
15-minute token (bug B4). A new panel of the member deletes the old one first (bug B24); a guild
whose player stops (`/stop`, `/disconnect`, the disconnect button, the idle leave, a disconnection
by someone else) deletes its panels; a refused edit (the member dismissed it, or the token
expired) ends the panel; unloading cancels the tasks (they never outlived the panel, bug B5).
`sleep` and `clock` are cog attributes that tests replace.

### Buttons

`IDS = ComponentIds("music_player", ("action",), legacy_prefix="musicplayer@")` (v3's derived
prefix and its only field); `handle` acknowledges each press at once (`response.defer()`, a
deferred update) and answers by editing the panel (`edit_original_response`): v3 edited it without
acknowledging, so its errors never showed (bug B3). Errors replace only the content, as v3's
`editOriginal(text)`; a full render clears it. The panel is ephemeral, so the core never upgrades a
v3 panel's IDs (it skips ephemeral messages).

### Autocomplete

discord.py routes autocompletes per option, so other commands' autocompletes are untouched (v3
answered them all with no choices, bug B7). Songs: v3's two characters, ten results, `title |
author` within 100 characters, the link as value (Discord refuses longer values), v3's cache of 100
inputs (oldest out), within 2.5 seconds (v3 waited 10, past Discord's 3, bug B26).

### Emojis

At READY the cog reads the application's emojis (`fetch_application_emojis`) and maps the 13
configured names to their mentions; a missing name, or every name when the request fails, takes a
Unicode emoji (the bar's `▰`/`▱`, `▶️`, `⏸️`, `➡️`, `🔂`, `⏮️`, `⏯️`, `⏭️`, `⏏️`), with one warning,
instead of v3's uninitialized property that broke every panel. v3's templates named four button
emojis by the author's application IDs, which no other application may use (Discord refuses the
message): they become placeholders (`music_player@media_previous_emoji`,
`music_player@media_pause_resume_emoji`, `music_player@media_next_emoji`,
`music_player@media_disconnect_emoji`) resolved like the others from four new `emojis` keys whose
defaults are v3's names. An operator's v3 templates with the IDs keep working for v3's application.

### Idle leave, disconnections and unload

The session reports idle (no current song) and busy; the cog starts a task per idle episode that
waits `auto_leave_timeout` and leaves if the same episode still holds (v3's dead check: no song
playing and none queued; a paused song counts as playing). A disconnection by Discord or a
moderator clears the history and deletes the panels (v3 kept a stale session, which led into bug
B1); a move keeps playing. `on_guild_remove` forgets the guild's session. `cog_unload` sets
`closed`, cancels the startup and idle tasks, disconnects every guild (the node's players stop),
deletes the panels and closes the client: a reload stops the music, where v3 kept playing and
leaked its threads (bug B23).

### Compose and the node's config

`compose.yaml` gains `lavalink` (`ghcr.io/lavalink-devs/lavalink:4.2.2`, `restart:
unless-stopped`, `./lavalink/application.yml` read-only, `LAVALINK_SERVER_PASSWORD:
${LAVALINK_PASSWORD:?...}` and the Spotify variables with defaults, a `curl` healthcheck of
`/version` with the password, json-file logs, `expose: 2333` and no `ports`); the bot `depends_on`
it with `condition: service_started`, so that the other plugins run while the node starts or
fails. `.env` (untracked, also in `.dockerignore`) holds the secrets; `.env.example` holds example
values. Plugins download at each container creation (a named volume would be root-owned and the
node runs as uid 322).

`lavalink/application.yml`: youtube-source 1.18.2 (search, video and playlist IDs, as v3's
`YoutubeAudioSourceManager(true, true, true)`) and LavaSrc 4.8.3 with v3's providers, Spotify's
source `${SPOTIFY_ENABLED:false}` and its credentials and country (v3's `TW`) from the environment;
Lavalink's sources: the deprecated YouTube one, HTTP and local off (bug B15), SoundCloud, Bandcamp,
Twitch, Vimeo and Niconico on (v3's remote sources still in Lavalink); request logging off, since it
would log every member's search.

### Tests

Pure modules alone; the session against a fake player; the cog through the loaded plugin with a
fake link, fake voice channels and members (`tests/plugins/music_player/conftest.py`'s `scene`: a
`Clock` for the panels and the idle leave, the guild's voice state); `node.py` against
`tests/support/lavalink_fakes.py`, a local Lavalink v4 node (WebSocket `ready` and events, REST
loads and player updates) through the real lavalink.py; compose and the node's config in
`tests/test_container.py`. No test reaches the network or sleeps in real time.

## v3 behaved differently

- v3 behaved differently: a song added while the player was idle with a history (after the last
  song ended, a lavaplayer cleanup or a failed last song) was queued and never played, while the
  panel showed it (B1). It starts now.
- v3 behaved differently: the paused state survived `/stop` and `/disconnect`, so the next song
  started paused (B2), and the previous button kept it while skip cleared it (B22). Every song
  starts unpaused.
- v3 behaved differently: button errors edited the panel without acknowledging the press, so
  members saw "This interaction failed" and never the text (B3), and the loop button with nothing
  playing did not answer. Each press is acknowledged at once.
- v3 behaved differently: presses never extended a panel, which died about 60 seconds after its
  command (B4); every panel's refresh task ran forever (B5); the queue panel's refreshes always
  failed (B6); replacing a panel could drop the newer one's record (B24).
- v3 behaved differently: its autocomplete answered every command of the bot with no choices (B7)
  and waited up to 10 seconds, past Discord's 3 (B26).
- v3 behaved differently: the history silently dropped songs past 240 while `/play` reported them
  (B8). Played songs leave first, and the rest is refused with `queue-full` or counted in the
  panel's `queue-truncated` line.
- v3 behaved differently: a failing song in single-song loop restarted forever (B9), and a stuck
  song played silence until skipped. Both move on to the next song.
- v3 behaved differently: `player.auto_leave_timeout` did nothing (B10): the bot stayed in voice
  forever. It leaves after that time idle.
- v3 behaved differently: placeholders went into the member's shared substitutor, where they leaked
  into other plugins and could be expanded again (B11, B12); values are made per render now (core).
- v3 behaved differently: SoundCloud and Spotify songs never had artwork (B13), and the requester's
  data in lavaplayer's `userData` made youtube-source log a parse error (B14). The node's artwork
  comes first, and the plugin keeps the requester.
- v3 behaved differently: any `http(s)` URL and local files could be loaded (B15) and SoundCloud was
  registered twice; the node's HTTP and local sources are off.
- v3 behaved differently: `/skip` past the last song re-showed the current one, and its
  `skipped-to-end` text never showed (B17); now the list ends there with that text. The skip
  button at the last song keeps v3's `no-more-songs`.
- v3 behaved differently: a failed emoji request or a missing emoji broke every panel until a
  restart, after blocking an event thread for seconds (B18); errors inside load callbacks left the
  response "thinking" (B19); the queue embed had no size limits (B20); a position past the length
  overflowed the bar (B21).
- v3 behaved differently: unloading left players, voice connections and threads running (B23); a
  reload stopped nothing. Unloading leaves voice and a reload stops the music.
- v3 behaved differently: `/play` checked Connect even when the bot stayed in another channel
  (B27), and nothing reacted to the bot being disconnected (the session stayed until a lavaplayer
  cleanup).
- v3 behaved differently: every text but the templates was zh-TW for every member; en-US members
  get English now.

## User-visible changes

- The plugin needs a Lavalink node: `docker compose up` runs it; `LAVALINK_PASSWORD` in `.env` and
  `lavalink.password` in `plugins/MusicPlayer/config.yaml` must match, and the plugin does not load
  until the password is set.
- Spotify moves to the node: `SPOTIFY_ENABLED`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and
  `SPOTIFY_COUNTRY_CODE` in `.env` replace v3's `engines.spotify` (which now only warns).
- en-US members get English texts (`text.yaml`); zh-TW members and others keep v3's.
- New texts: `node-unavailable`, `queue-full`, `queue-truncated` and the queue's `queue-more` line.
- Button errors show in the panel; presses keep a panel alive; the queue panel refreshes; a song
  added after the end plays; `/skip` past the last song ends the list; the bot leaves after 10
  minutes idle and when the plugin reloads; panels are deleted when the bot leaves.
- Four button emojis come from new `emojis` keys (v3's names by default); missing emojis show as
  Unicode ones instead of breaking the panels.
- Arbitrary `http(s)` links and local files no longer load; Yandex Music, Beam and Getyarn are gone
  (not in Lavalink 4, or need a token).

## Risks / Trade-offs

- [YouTube blocks or changes its clients] -> youtube-source on the node is updated by changing one
  version in `lavalink/application.yml`; the plugin does not change.
- [The node is down or the password differs] -> the other plugins keep running (`service_started`);
  commands answer `node-unavailable`; lavalink.py's warnings name the cause.
- [lavalink.py's private voice state for moves] -> pinned version; a test drives the real class.
- [DAVE needs a real voice connection] -> the manual smoke checklist.
- [Panels edit every 5 seconds per member] -> v3's rate; webhook edits of an interaction are not
  channel rate limits, and each panel ends after 60 seconds without a press.

## Manual smoke checklist

On a test guild, with a bot token, `plugins: [MusicPlayer]` and `docker compose up -d --build`
(`.env` with `LAVALINK_PASSWORD`, the same password in `bot/plugins/MusicPlayer/config.yaml`); the
application's emojis uploaded from v3's `images/` with v3's names; the bot needs View Channel,
Connect and Speak in the voice channel:

1. `docker compose ps`: `lavalink` is healthy; the bot's log shows MusicPlayer loaded and
   lavalink.py's "WebSocket connection established".
2. Join a voice channel, `/play query:never gonna give you up`: the bot joins, the song plays
   (audible: DAVE works), the ephemeral panel shows the song, the bar and the five buttons with the
   application's emojis, and refreshes every 5 seconds.
3. Type in `query`: suggestions appear within about 2 seconds.
4. Press pause, skip (with a second song queued), previous, loop, then wait 60 seconds without a
   press: the panel follows each press and is deleted 60 seconds after the last one.
5. `/queue` with three songs queued, `/shuffle`, `/volume level:80` (audibly louder),
   `/now-playing`, `/skip count:2`, `/stop`: v3's replies; the bot leaves at `/stop`.
6. A zh-TW client sees zh-TW commands and texts; an en-US client English texts.
7. Disconnect the bot from voice with a moderator's menu: its panels are deleted, and `/play`
   starts again.
8. Leave the bot idle for 10 minutes after the last song: it leaves.
9. Press a button on a panel left from v3 (if any): it acts.
10. Stop the node (`docker compose stop lavalink`): `/play` answers `node-unavailable`; start it:
    `/play` works again without a restart.
11. With Spotify credentials in `.env` and `SPOTIFY_ENABLED=true`, recreate the node: a Spotify
    track link plays (mirrored from YouTube).
