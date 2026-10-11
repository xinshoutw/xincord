## 1. Resources

- [x] 1.1 Add lavalink.py 5.11.1 to `xincord-plugins` (pinned in `uv.lock`) and bundle
      `config.yaml` and `lang/` (v3's register files and templates, the four button emoji IDs as
      placeholders, final newlines; `text.yaml` with v3's zh-TW texts and en-US translations);
      add `golden.yaml` under `tests/fixtures/plugins/music_player/`

## 2. Installation and config

- [x] 2.1 xfail tests for "The plugin installs as MusicPlayer" and "The config names the node, the
      player's defaults, the errors and the emojis", loading the plugin through its entry point
- [x] 2.2 Add the package, its `setup`, the config model and the `MusicPlayer` entry point; remove
      the markers

## 3. Pure logic

- [x] 3.1 xfail tests for "Queries become Lavalink identifiers as in v3", "Panels show v3's track
      layout" and "The queue view fits Discord's limits" against stubs in `display.py`
- [x] 3.2 Implement the identifier rule, the times, the bar, the thumbnails, the panel values and
      the queue embed; remove the markers
- [x] 3.3 xfail tests for "The history keeps v3's order of play" against stubs in `history.py`
- [x] 3.4 Implement the history; remove the markers

## 4. Session

- [x] 4.1 xfail tests for "Playback follows the node's events" against stubs in `session.py`, with
      a fake player
- [x] 4.2 Implement the session; remove the markers

## 5. Node

- [x] 5.1 Add the local fake Lavalink node (`tests/support/lavalink_fakes.py`) and xfail tests for
      "Songs load and play through a Lavalink node" against stubs in `node.py`
- [x] 5.2 Implement the lavalink.py adapter and the voice protocol; remove the markers

## 6. Commands

- [x] 6.1 xfail tests for "Commands keep v3's names, options and localizations", "Members bring
      the bot into voice and send it away" and "Play queues songs and starts them"
- [ ] 6.2 Build the commands, the voice checks and `/play`; remove the markers
- [ ] 6.3 xfail tests for "Members control playback with v3's replies" and "Volume, queue, shuffle
      and now playing keep v3's replies"
- [ ] 6.4 Implement the eight other commands; remove the markers
- [ ] 6.5 xfail tests for "Autocomplete suggests songs and the current volume" and "Errors are
      reported as v3 did"
- [ ] 6.6 Implement the autocompletes and the error replies; remove the markers

## 7. Panels and buttons

- [ ] 7.1 xfail tests for "Panels refresh themselves and expire"
- [ ] 7.2 Implement the panels; remove the markers
- [ ] 7.3 xfail tests for "Panel buttons control the guild's player"
- [ ] 7.4 Implement the buttons and their route; remove the markers

## 8. Voice lifecycle

- [ ] 8.1 xfail tests for "The bot leaves when idle, disconnected or removed" and "The node and the
      emojis load from READY, and unloading leaves voice"
- [ ] 8.2 Implement the idle leave, the disconnections, the startup task, the emojis and the
      unload; remove the markers

## 9. Deployment

- [ ] 9.1 xfail tests for "Lavalink service", "Container image" and "Compose service"
- [ ] 9.2 Add the `lavalink` service, `lavalink/application.yml`, `.env.example` and the ignores;
      remove the markers; check with Docker that the node starts healthy on this Mac and that the
      bot image loads every plugin with `--no-online`, then clean up

## 10. Conventions and docs

- [ ] 10.1 Check that the built wheel ships `config.yaml` and `lang/`, that `xincord --no-online`
      loads the plugin, and drive the plugin once through discord.py's own objects with HTTP
      recorded
- [ ] 10.2 Porting guide rows and pitfalls, and skill corrections
- [ ] 10.3 Audit the inventory against the scenarios and the design

## 11. Review

- [ ] 11.1 Gate passes, push, CI green (before the review)
- [ ] 11.2 Cross-review the change (other paths into a panel or a song, repeated or concurrent
      presses and commands, state left behind) and fix its findings xfail-first

## 12. Close

- [ ] 12.1 Gate passes, push, CI green
- [ ] 12.2 Archive the change and run `openspec validate --all --strict`
- [ ] 12.3 Update `HANDOFF.md`, `docs/porting/owner-review.md` and the skill; push; CI green
