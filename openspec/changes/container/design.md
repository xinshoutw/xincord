## Context

The bot reads `config.yaml`, keeps each plugin's files in `plugins/<Name>/` and its database in
`data/xincord.db`, all relative to the working directory (`core-startup`). The console appears
only when stdin and stdout are terminals (`core-console`). SIGTERM stops the bot and SIGHUP reloads
it (`core-startup`, `core-reload`). The host is an Apple M4 Pro running OrbStack or Docker Desktop
(F2).

## Goals / Non-Goals

**Goals:** a reproducible arm64 image built from the lock file, files the owner can edit on the
host, a database in a named volume (B16), and the console through `docker compose attach`.

**Non-Goals:** Lavalink (added with MusicPlayer), images in a registry, CI image builds, data
migration from v3.

## Decisions

- **Base.** `python:3.14.8-slim-trixie`, the Python the project uses, multi-arch, so the build on
  the M4 host is native arm64 without a `platform` setting. uv comes from
  `ghcr.io/astral-sh/uv:0.12.24`, the version in use.
- **Two stages.** The builder syncs the dependencies first (only `pyproject.toml` files and
  `uv.lock`, so code changes reuse that layer), then the project with
  `uv sync --locked --no-dev --all-packages --no-editable`: both workspace members are installed
  into `/app/.venv` as regular packages. The runtime stage copies only the virtual environment,
  so no source tree, uv or build cache ships.
- **User.** `xincord` (uid 1000) owns `/bot` and `/bot/data` in the image, so a new named volume
  starts with that owner; the process never runs as root.
- **Files.** The compose service bind-mounts `./bot` at `/bot`: the bot writes `config.yaml` and
  `plugins/<Name>/` there on the first start, where the owner edits them. The named volume `data`
  is mounted over `/bot/data`, so the database stays out of the host directory (B16).
- **Console.** `stdin_open: true` and `tty: true` make stdin and stdout terminals, so the console
  runs; `docker compose attach bot` opens it and Ctrl-P Ctrl-Q detaches. The trade-off: the log
  stream carries the prompt's terminal codes.
- **Signals.** `init: true` runs Docker's init as PID 1 to forward signals and reap processes;
  `stop_grace_period: 30s` leaves time to unload plugins and close the store on SIGTERM.
  `docker compose kill -s HUP bot` reloads.
- **Logs.** Logs go to stderr only (owner's choice in `core-startup`), so the json-file driver
  rotates them at 10 MB, keeping 3 files.
- **Tests.** Static checks read the Dockerfile, `.dockerignore` and `compose.yaml`; building and
  running the image is a manual step listed below, because CI does not build images.

## Risks / Trade-offs

- On a Linux host, `./bot` must be writable by uid 1000; OrbStack and Docker Desktop on macOS map
  ownership for bind mounts.
- `docker compose logs` shows the console's terminal codes while the console runs.

## Manual check

1. `docker compose build` succeeds and `docker image inspect` reports `arm64`.
2. `docker compose run --rm bot --no-online` creates `bot/config.yaml` and exits with status 0.
3. With a token in `bot/config.yaml`: `docker compose up -d`, `docker compose attach bot` shows
   `console > `, `reload` logs a summary, Ctrl-P Ctrl-Q detaches, `docker compose kill -s HUP bot`
   reloads, `docker compose stop` exits within the grace period, and the database is in the
   `xincord_data` volume.

## User-visible changes

For the operator:

1. Run with `docker compose up -d --build`; edit `bot/config.yaml` and `bot/plugins/<Name>/` on
   the host; the database lives in the `xincord_data` volume.
2. `docker compose attach bot` opens the console (Ctrl-P Ctrl-Q detaches);
   `docker compose kill -s HUP bot` reloads; `docker compose stop` stops.
3. `docker compose logs -f bot` shows the logs, rotated at 10 MB with 3 files kept.
