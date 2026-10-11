## MODIFIED Requirements

### Requirement: Container image
The repository SHALL build an image from an exact `python:3.14.N-slim-trixie` tag that installs
both distributions with an exact uv image version from `uv.lock`, without development dependencies
and not editable, and that runs `xincord` with the container's arguments as a non-root user in
`/bot`. The build context SHALL exclude the local virtual environment, git data, caches, the bot's
runtime files, the secrets file `.env` and the Lavalink node's config.

#### Scenario: Image definition
- **WHEN** the Dockerfile is read
- **THEN** it builds from an exact Python 3.14 slim trixie tag and an exact uv image version, runs
  `uv sync --locked --no-dev --all-packages --no-editable`, switches to a non-root user, works in
  `/bot` and has the entry point `xincord`

#### Scenario: Build context
- **WHEN** the `.dockerignore` file is read
- **THEN** it excludes `.venv`, `.git`, the tool caches, `bot/`, `.env` and `lavalink/`

### Requirement: Lavalink service
`compose.yaml` SHALL define a `lavalink` service for MusicPlayer from an exact
`ghcr.io/lavalink-devs/lavalink` 4.x tag, 4.2.0 or later (Ubuntu, arm64, DAVE), with
`lavalink/application.yml` mounted read-only, its password from `LAVALINK_PASSWORD` of an untracked
`.env`, a healthcheck that sends the password, restart unless stopped, rotated logs and no
published port. The node config SHALL pin its plugins, keep the HTTP, local and built-in YouTube
sources off, and log no member's query.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service uses an exact 4.x tag from 4.2.0, mounts the config read-only,
  takes its password from `LAVALINK_PASSWORD`, checks its health with the password, restarts unless
  stopped, rotates its logs and publishes no port

#### Scenario: Node config
- **WHEN** `lavalink/application.yml` is read
- **THEN** youtube-source and LavaSrc have exact versions, the HTTP, local and built-in YouTube
  sources are off, request logging is off, and LavaSrc's Spotify source follows `SPOTIFY_ENABLED`,
  off by default

#### Scenario: No queries in the node's logs
- **WHEN** `lavalink/application.yml` is read
- **THEN** request logging is off and the load handler, whose INFO lines name each identifier, logs
  warnings only

#### Scenario: Secrets stay untracked
- **WHEN** `.gitignore`, `.dockerignore` and `.env.example` are read
- **THEN** git and the build context ignore `.env`, and `.env.example` holds example values only
