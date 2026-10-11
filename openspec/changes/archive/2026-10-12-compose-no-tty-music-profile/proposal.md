## Why

Two costs of `compose.yaml`, seen in production on 2026-10-12. The `bot` service keeps stdin open
with a TTY for the console, so the console's prompt redraws its escape sequences into the
container's log between the log lines; the console only offers `reload [plugin]` and `stop`, which
`/xincord reload`, SIGHUP and `docker compose stop` already do. And every deployment runs the
Lavalink node, a JVM, although only MusicPlayer uses it: the shop's bot runs one for nothing.

## What Changes

- The `bot` service has no TTY and no open stdin: the console stays off under compose (it runs
  only when stdin and stdout are terminals) and the log holds log lines only. `docker compose
  attach bot` goes from the README and the comments.
- Log lines are coloured only when stderr is a terminal: discord.py colours them inside any
  Docker container, terminal or not, so the container's log held escape sequences still.
- The `lavalink` service belongs to the compose profile `music`: it runs when `.env` sets
  `COMPOSE_PROFILES=music`. The bot depends on it only when it runs (`required: false`).
  **Breaking for deployments with MusicPlayer**: add `COMPOSE_PROFILES=music` to `.env`.
- `.env.example` and the README say so; MusicPlayer's config comment names the profile.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: the compose service (no TTY, the optional node) and the Lavalink service (the
  `music` profile).
- `core-runtime`: plain log lines off a terminal.

## Impact

`compose.yaml`, `.env.example`, README, MusicPlayer's bundled `config.yaml` (a comment),
`xincord.core.cli`, `tests/test_container.py`, `tests/core/test_cli.py`,
`tests/core/test_console.py`. The plain log lines reach production with the next release. Deployments with MusicPlayer add `COMPOSE_PROFILES=music` to `.env`;
the others stop their node once.
