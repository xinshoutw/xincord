## Why

Decision B16 runs xincord on the owner's macOS host (Apple M4 Pro, F2) as an arm64 Docker image
under docker compose, with the SQLite file in a named volume; B15 needs `stdin_open` and `tty` so
`docker compose attach` reaches the console. v3 ran as `java -jar` from a shell script in
`Server/`, so there is no Kotlin source to port.

## What Changes

- `Dockerfile`: a two-stage build on `python:3.14.8-slim-trixie` (multi-arch, arm64 included)
  that installs both distributions from `uv.lock` with uv 0.12.24, without development
  dependencies, and runs `xincord` as a non-root user in `/bot`.
- `.dockerignore`: keeps the local virtual environment, git data, caches and runtime files out of
  the build context.
- `compose.yaml`: a `bot` service with `./bot` (config and plugin files, editable on the host)
  bind-mounted at `/bot`, the named volume `data` at `/bot/data` for the database, `stdin_open`,
  `tty`, an init process, a restart policy, a stop grace period and log rotation.
- README: how to run, attach, reload and stop the container.

Out of scope: Lavalink (with MusicPlayer), publishing images to a registry, and moving the v3 data
(Resolution 3).

## Capabilities

### New Capabilities

- `deployment`: the container image and the compose service.

### Modified Capabilities

None.

## Impact

New files `Dockerfile`, `.dockerignore` and `compose.yaml`; `.gitignore` ignores `bot/`. No code
or dependency changes.
