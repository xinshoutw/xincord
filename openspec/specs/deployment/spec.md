# deployment Specification

## Purpose
Packages xincord as a container image and runs it with docker compose on the owner's host.

## Requirements

### Requirement: Container image
The repository SHALL build an image from an exact `python:3.14.N-slim-trixie` tag that installs
both distributions with an exact uv image version from `uv.lock`, without development dependencies
and not editable, and that runs `xincord` with the container's arguments as a non-root user in
`/bot`. The build context SHALL exclude the local virtual environment, git data, caches, the bot's
runtime files and the secrets file `.env`.

#### Scenario: Image definition
- **WHEN** the Dockerfile is read
- **THEN** it builds from an exact Python 3.14 slim trixie tag and an exact uv image version, runs
  `uv sync --locked --no-dev --all-packages --no-editable`, switches to a non-root user, works in
  `/bot` and has the entry point `xincord`

#### Scenario: Build context
- **WHEN** the `.dockerignore` file is read
- **THEN** it excludes `.venv`, `.git`, the tool caches, `config.yaml`, `plugins`, `data` and `.env`

### Requirement: Compose service
`compose.yaml` SHALL run the `bot` service from `ghcr.io/xinshoutw/xincord`, tagged
`XINCORD_VERSION` (`latest` by default), bind-mount its own directory at `/bot` for `config.yaml`
and `plugins/`, mount the named volume `data` at `/bot/data`, keep stdin open with a TTY, run an
init process, restart unless stopped, allow 30 seconds to stop, rotate its logs and start after
`lavalink` without waiting for its health. `compose.build.yaml` SHALL build the image from a clone.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `bot` service has those settings, no build section, depends on `lavalink` being
  started, and the `data` volume is declared

#### Scenario: Building from a clone
- **WHEN** `compose.build.yaml` is read
- **THEN** it gives the `bot` service a build from the repository and the local image name

### Requirement: Lavalink service
`compose.yaml` SHALL define a `lavalink` service for MusicPlayer from an exact
`ghcr.io/lavalink-devs/lavalink` 4.x tag, 4.2.0 or later (Ubuntu, arm64, DAVE), its config inline
as the compose config `lavalink`, its password from `LAVALINK_PASSWORD` of an untracked `.env`, a
healthcheck that sends the password, restart unless stopped, rotated logs and no published port.
The node config SHALL pin its plugins, keep the HTTP, local and built-in YouTube sources off, and
log no member's query.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service uses an exact 4.x tag from 4.2.0, mounts the `lavalink` config at
  `/opt/Lavalink/application.yml`, takes its password from `LAVALINK_PASSWORD`, checks its health
  with the password, restarts unless stopped, rotates its logs and publishes no port

#### Scenario: Node config
- **WHEN** the `lavalink` config's content is read
- **THEN** LavaSrc has an exact release and youtube-source an exact release or a snapshot's
  40-character commit, the HTTP, local and built-in YouTube sources are off, request logging is
  off, and LavaSrc's Spotify source follows `SPOTIFY_ENABLED`, off by default

#### Scenario: No queries in the node's logs
- **WHEN** the `lavalink` config's content is read
- **THEN** request logging is off and the load handler, whose INFO lines name each identifier, logs
  warnings only

#### Scenario: Secrets stay untracked
- **WHEN** `.gitignore`, `.dockerignore` and `.env.example` are read
- **THEN** git and the build context ignore `.env`, and `.env.example` holds example values only

### Requirement: No cursor position requests
The image SHALL set `PROMPT_TOOLKIT_NO_CPR=1`, so the console never asks a terminal that nobody
attached for the cursor position.

#### Scenario: Image environment
- **WHEN** the Dockerfile is read
- **THEN** its runtime stage sets `PROMPT_TOOLKIT_NO_CPR=1`

### Requirement: Time zone from .env
The `bot` service SHALL take its `TZ` from `.env`, `UTC` when unset, so that the plugins that use
the host's local time (Giveaway's typed end times, Ticket's archive times, NtustAnnouncements'
`{{now}}`) follow the operator's zone. `.env.example` SHALL show `TZ` as a commented example.

#### Scenario: Compose and the example
- **WHEN** `compose.yaml` and `.env.example` are read
- **THEN** the `bot` service's environment sets `TZ` to `${TZ:-UTC}`, and `.env.example` holds a
  commented `TZ=` line

### Requirement: YouTube OAuth for the node
The node SHALL list youtube-source's default clients and then TV, the client that uses an OAuth
account, and take `oauth.enabled` and `oauth.refreshToken` from `YOUTUBE_OAUTH_ENABLED` (false by
default) and `YOUTUBE_OAUTH_REFRESH_TOKEN` (empty by default), which compose fills in from `.env`.
`.env.example` SHALL show both commented.

#### Scenario: Compose passes the settings
- **WHEN** the `lavalink` config's content is read
- **THEN** its OAuth settings are `${YOUTUBE_OAUTH_ENABLED:-false}` and
  `${YOUTUBE_OAUTH_REFRESH_TOKEN:-}`, which compose interpolates

#### Scenario: Node config
- **WHEN** the `lavalink` config's content is read
- **THEN** youtube-source's clients are MUSIC, ANDROID_VR, WEB, WEBEMBEDDED and TV in that order

#### Scenario: Example
- **WHEN** `.env.example` is read
- **THEN** it holds `YOUTUBE_OAUTH_ENABLED` and `YOUTUBE_OAUTH_REFRESH_TOKEN` as comments only

### Requirement: Remote cipher for the node
The node SHALL send youtube-source's signature work to the remote cipher server at
`YOUTUBE_CIPHER_URL`, by default the public `https://cipher.kikkia.dev/`, with the password
`YOUTUBE_CIPHER_PASSWORD`, empty by default, which compose fills in from `.env`. `.env.example`
SHALL show both commented.

#### Scenario: Node config and compose
- **WHEN** the `lavalink` config's content is read
- **THEN** youtube-source's `remoteCipher` is `${YOUTUBE_CIPHER_URL:-https://cipher.kikkia.dev/}`
  with the password `${YOUTUBE_CIPHER_PASSWORD:-}`, which compose interpolates

#### Scenario: Example
- **WHEN** `.env.example` is read
- **THEN** it holds `YOUTUBE_CIPHER_URL` and `YOUTUBE_CIPHER_PASSWORD` as comments only
