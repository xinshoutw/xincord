## Why

Decision C1 ports MusicPlayer last, F3 lists it as in use, and B14 and B16 run its audio on a
Lavalink 4.2+ node (DAVE, the end-to-end encryption that Discord has required for voice since
2026-03-02) under docker compose, driven by lavalink.py; B12 folds v3's AudioAPI into the plugin's
declared requirements. v3's MusicPlayer (`Plugins/MusicPlayer`, 11 Kotlin files, 2,721 lines) is a
per-guild music player: eleven guild commands join or leave voice, play YouTube and SoundCloud (and
Spotify when enabled) through lavaplayer inside the JVM, and answer with an ephemeral "player panel"
that refreshes itself every five seconds and carries five control buttons.

## What Changes

- New plugin package `xincord.plugins.music_player`, registered as `MusicPlayer`, with the voice
  states intent, a bundled `config.yaml` and `lang/` (en-US and zh-TW, v3's register files and
  templates, and a new `text.yaml` with the texts v3 hard-coded in zh-TW, translated for en-US).
- v3's eleven guild commands with v3's names, options, limits, localizations and autocompletes:
  `/join`, `/disconnect`, `/play query`, `/pause`, `/resume`, `/stop`, `/skip [count]`,
  `/volume level`, `/queue`, `/shuffle` and `/now-playing`, for every member, answered ephemerally.
- The panels (`play`, `pause`, `resume`, `skip`, `volume`, `queue`, `now-playing`) keep v3's layout:
  the track's embed with the progress bar of application emojis, the colours, the requester and
  the five buttons (previous, pause or resume, skip, loop mode, disconnect). Their v3 IDs
  (`musicplayer@a:<action>`) keep working; new panels carry `music_player:1:a=<action>`.
- Audio goes through a Lavalink node: lavalink.py 5.11.1 (pinned in `uv.lock`, DAVE-capable since
  5.10.0) behind narrow Protocols, so that tests use fakes and a local fake node. The plugin keeps
  v3's history model (previous, skip, shuffle of the upcoming songs, sequential and single-song
  loop) on its side and plays one song at a time on the node.
- `compose.yaml` gains a `lavalink` service: `ghcr.io/lavalink-devs/lavalink:4.2.2` (Ubuntu
  variant, arm64, glibc 2.35 for DAVE) with `lavalink/application.yml` (youtube-source 1.18.2 and
  LavaSrc 4.8.3 pinned, LavaSrc's Spotify off unless `.env` enables it, the HTTP and local sources
  off), its password from `LAVALINK_PASSWORD` in an untracked `.env` (`.env.example` holds an
  example), a healthcheck, no port published, and the bot depending on it.
- `config.yaml` gains `lavalink` (host, port and password, the password required and hidden in
  errors) and keeps v3's keys that had an effect: `player.default_volume`,
  `messages.show_detailed_errors` and `emojis` (four new names for the buttons whose emoji IDs v3
  hard-coded in its templates); `player.auto_leave_timeout` now takes effect.
- v3's defects are fixed (see `design.md`): a song added while the player is idle plays (v3 queued
  it forever), the paused state ends with `/stop` and every new song, button errors are shown,
  presses extend a panel's life, refresh loops stop, the queue panel refreshes, autocomplete answers
  only its commands within Discord's three seconds, the history no longer drops songs silently, a
  failing song is not looped forever, the bot leaves after `auto_leave_timeout` idle, unloading
  leaves voice, and missing emojis fall back to Unicode ones instead of breaking every panel.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-140`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:47-957`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/command/Register.kt:11-154`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/command/CmdFileSerializer.kt:8-56`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/config/ConfigSerializer.kt:7-297`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:21-342`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/HistoryIndexManager.kt:10-252`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/TrackSchedulerCompat.kt:16-127`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:21-312`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/model/TrackInfo.kt:1-26`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/config.yaml:1-102`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/info.yaml:1-19`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/lang/en-US/register.yaml:1-44`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/lang/zh-TW/register.yaml:1-56`
- `XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/lang/en-US/message/play.yaml:1-57`

Out of scope: v3's in-process audio stack (lavaplayer, JDA's audio manager, JDAVE and
`AudioPlayerSendHandler`), which the Lavalink node replaces; v3's dead code and unused config keys
(about 35: `command_message_acknowledges`, `engines.youtube` and `engines.soundcloud`, the lyrics,
artwork, cache, performance and developer settings, the dead idle scheduler, `MusicStats`,
`getSourceName`, `processSearchQuery`, `getEnabledSources`), which v3's files keep and the core
names in warnings; uploading the application emojis (v3's `images/` stay in v3's repository, and
the operator uploads them, as for v3); a real voice test, which needs a token and a guild (the
manual smoke checklist); the Web Dashboard's reload path (B13).

## Capabilities

### New Capabilities
- `plugin-music-player`: the MusicPlayer plugin: its commands, panels, buttons, autocompletes,
  history, Lavalink node and voice lifecycle.

### Modified Capabilities
- `deployment`: compose runs a Lavalink node beside the bot, and the build context leaves out the
  secrets file and the node's config.

## Impact

- New package `packages/xincord-plugins/src/xincord/plugins/music_player/` and the `MusicPlayer`
  entry point; `xincord-plugins` depends on `lavalink` (lavalink.py, MIT, sdist only, built by uv).
- `compose.yaml`, `.dockerignore`, `.gitignore`, new `lavalink/application.yml` and `.env.example`.
- Tests under `tests/plugins/music_player/`, `tests/support/lavalink_fakes.py` (a local fake
  Lavalink node), fixtures under `tests/fixtures/plugins/music_player/`, `tests/test_container.py`.
- No core API change.
