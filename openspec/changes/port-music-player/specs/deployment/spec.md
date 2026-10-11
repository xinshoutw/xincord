# Spec Delta

## MODIFIED Requirements

### Requirement: Container image
The repository SHALL build an image from `python:3.14.8-slim-trixie` that installs both
distributions with uv 0.12.24 from `uv.lock`, without development dependencies and not editable,
and that runs `xincord` with the container's arguments as a non-root user in `/bot`. The build
context SHALL exclude the local virtual environment, git data, caches, the bot's runtime files, the
secrets file `.env` and the Lavalink node's config.

#### Scenario: Image definition
- **WHEN** the Dockerfile is read
- **THEN** it builds from the pinned base and uv images, runs
  `uv sync --locked --no-dev --all-packages --no-editable`, switches to a non-root user, works in
  `/bot` and has the entry point `xincord`

#### Scenario: Build context
- **WHEN** the `.dockerignore` file is read
- **THEN** it excludes `.venv`, `.git`, the tool caches, `bot/`, `.env` and `lavalink/`

### Requirement: Compose service
`compose.yaml` SHALL define a `bot` service built from the repository that bind-mounts the host
directory `./bot` at `/bot` for the config and plugin files, mounts the named volume `data` at
`/bot/data` for the database, keeps stdin open with a TTY for the console, runs an init process,
restarts unless stopped, allows 30 seconds to stop, rotates its logs and starts after the
`lavalink` service without waiting for its health.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `bot` service has those settings, depends on `lavalink` being started, and the
  `data` volume is declared

## ADDED Requirements

### Requirement: Lavalink service
`compose.yaml` SHALL define a `lavalink` service for MusicPlayer from
`ghcr.io/lavalink-devs/lavalink:4.2.2` (Ubuntu, arm64, DAVE) with `lavalink/application.yml`
mounted read-only, its password from `LAVALINK_PASSWORD` of an untracked `.env`, a healthcheck that
sends the password, restart unless stopped, rotated logs and no published port. The node config
SHALL pin its plugins and keep the HTTP, local and built-in YouTube sources off.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service uses the pinned image, mounts the config read-only, takes its
  password from `LAVALINK_PASSWORD`, checks its health with the password, restarts unless stopped,
  rotates its logs and publishes no port

#### Scenario: Node config
- **WHEN** `lavalink/application.yml` is read
- **THEN** youtube-source and LavaSrc have exact versions, the HTTP, local and built-in YouTube
  sources are off, request logging is off, and LavaSrc's Spotify source follows `SPOTIFY_ENABLED`,
  off by default

#### Scenario: Secrets stay untracked
- **WHEN** `.gitignore`, `.dockerignore` and `.env.example` are read
- **THEN** git and the build context ignore `.env`, and `.env.example` holds example values only
